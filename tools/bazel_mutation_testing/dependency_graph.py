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
        self, labels: Mapping[str, str], dependents: Mapping[str, frozenset[str]]
    ):
        """Create the graph.

        Args:
            labels: The label of each of the repository's source files in the
                graph, by its workspace-relative path.
            dependents: The labels of the targets that depend directly on each
                label.
        """
        self._labels = labels
        self._dependents = dependents

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


def from_dot(graph: str) -> DependencyGraph:
    """Return the dependency graph of `graph`, the output of `bazel query --output=graph --nograph:factored`."""
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
    return DependencyGraph(
        labels,
        {label: frozenset(direct) for label, direct in dependents.items()},
    )
