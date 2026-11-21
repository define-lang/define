"""How closely each test depends on each source file."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from collections.abc import Mapping


class NoDependentTestError(Exception):
    """None of the tests depends on a source file."""


@final
class DependencyGraph:
    """The targets and source files that the area's tests depend on."""

    def __init__(
        self,
        labels: Mapping[str, str],
        dependents: Mapping[str, frozenset[str]],
        pyright_sources: Mapping[str, str],
    ):
        """Create the graph.

        Args:
            labels: The label of each of the repository's source files in the
                graph, by its workspace-relative path.
            dependents: The labels of the targets that depend directly on each
                label.
            pyright_sources: The label of the target that lists the files
                that each pyright_test checks, by the pyright_test's label.
        """
        self._labels = labels
        self._dependents = dependents
        self._dependencies: dict[str, set[str]] = {}
        for label, direct in dependents.items():
            for dependent in direct:
                self._dependencies.setdefault(dependent, set()).add(label)
        self._pyright_sources = pyright_sources

    def closest_test(self, path: str, tests: frozenset[str]) -> str:
        """Return the test of `tests` that the fewest dependencies separate from `path`, a workspace-relative source path.

        Of several tests at the same distance, the first by label is closest,
        so that every run makes the same choice.

        Raises:
            NoDependentTestError: No test of `tests` depends on `path`.
        """
        start = self._labels[path]
        seen = {start}
        level = {start}
        while level:
            found = level & tests
            if found:
                return min(found)
            following: set[str] = set()
            for label in level:
                following.update(self._dependents.get(label, frozenset()) - seen)
            seen.update(following)
            level = following
        raise NoDependentTestError(f"No test of {sorted(tests)} depends on {path}")

    def pyright_tests_not_checking(self, path: str) -> frozenset[str]:
        """Return the pyright_tests that cannot check `path`, a workspace-relative source path.

        A pyright_test checks the Python files and stubs of its own package,
        and of the packages below it that its dependencies come from, among
        the files that it depends on. A pyright_test that depends on `path`
        through a dependency that is not type-checked still counts as checking
        it.
        """
        if not path.endswith((".py", ".pyi")):
            return frozenset(self._pyright_sources)
        package = _package(self._labels[path])
        depending = self._transitive_dependents(self._labels[path])
        not_checking: set[str] = set()
        for test, sources in self._pyright_sources.items():
            if sources not in depending or package not in self._checked_packages(
                sources
            ):
                not_checking.add(test)
        return frozenset(not_checking)

    def _checked_packages(self, sources: str) -> set[str]:
        sources_package = _package(sources)
        packages = {sources_package}
        for dependency in self._dependencies.get(sources, set()):
            if _package(dependency).startswith(sources_package + "/"):
                packages.add(_package(dependency))
        return packages

    def _transitive_dependents(self, label: str) -> set[str]:
        found = {label}
        pending = [label]
        while pending:
            for dependent in self._dependents.get(pending.pop(), frozenset()):
                if dependent not in found:
                    found.add(dependent)
                    pending.append(dependent)
        return found


def _package(label: str) -> str:
    return label.removeprefix("//").partition(":")[0]


def from_dot(
    graph: str, pyright_tests: frozenset[str], pyright_sources: frozenset[str]
) -> DependencyGraph:
    """Return the dependency graph of `graph`, the output of `bazel query --output=graph --nograph:factored`.

    `pyright_tests` holds the labels of the pyright_tests, and
    `pyright_sources` the labels of the targets that list the files that they
    check. Each pyright_test depends directly on its own list.
    """
    labels: dict[str, str] = {}
    dependents: dict[str, set[str]] = {}
    for line in graph.splitlines():
        dependent, arrow, dependency = line.strip().partition(" -> ")
        if not arrow:
            continue
        dependency = dependency.strip('"')
        dependents.setdefault(dependency, set()).add(dependent.strip('"'))
        if dependency.startswith("//"):
            package, _, name = dependency.removeprefix("//").partition(":")
            labels[f"{package}/{name}" if package else name] = dependency
    sources_by_test: dict[str, str] = {}
    for sources in pyright_sources:
        tests = dependents.get(sources, set()) & pyright_tests
        sources_by_test.update(dict.fromkeys(tests, sources))
    return DependencyGraph(
        labels,
        {label: frozenset(direct) for label, direct in dependents.items()},
        sources_by_test,
    )
