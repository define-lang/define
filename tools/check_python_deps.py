"""Keep Python dependencies and type-check coverage synchronized."""

from __future__ import annotations

import argparse
import ast
import importlib.metadata
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

PYTHON_RULE_CLASSES: Final = frozenset({"py_binary", "py_library", "py_test"})
BAZEL_IMPORTS: Final = {"python.runfiles": "@rules_python//python/runfiles"}


@dataclass(frozen=True)
class PythonTarget:
    """A hand-maintained one-source Python target."""

    label: str
    rule_class: str
    build_file: Path
    source: Path
    deps: frozenset[str]
    kept_deps: frozenset[str] = frozenset()
    generated_source: bool = False


@dataclass(frozen=True)
class PyrightTarget:
    """A pyright test that type-checks Python targets."""

    label: str
    build_file: Path
    deps: frozenset[str]
    kept_deps: frozenset[str] = frozenset()
    include_subpackages: bool = False


type DependencyTarget = PythonTarget | PyrightTarget


@dataclass(frozen=True)
class DependencyChanges:
    """Differences between declared and expected dependencies."""

    target: DependencyTarget
    expected: frozenset[str]

    @property
    def missing(self) -> frozenset[str]:
        """Return dependencies required by imports but not declared."""
        return self.expected - self.target.deps

    @property
    def unnecessary(self) -> frozenset[str]:
        """Return declared dependencies not required by imports."""
        return self.target.deps - self.expected


@dataclass(frozen=True)
class ImportAnalysis:
    """Bazel owners and unresolved modules found in Python imports."""

    dependencies: frozenset[str]
    unresolved: frozenset[str]


@dataclass(frozen=True)
class ParsedTarget:
    """A Python target paired with its parsed source."""

    target: PythonTarget
    tree: ast.Module


@dataclass(frozen=True)
class RepositoryAnalysis:
    """Loaded Python targets and reusable source analysis for a repository."""

    repository: Path
    parsed_targets: tuple[ParsedTarget, ...]
    module_owners: dict[str, str]
    external_module_owners: dict[str, str]
    conftest_fixtures: dict[Path, frozenset[str]]
    pyright_targets: tuple[PyrightTarget, ...] = ()


@dataclass(frozen=True)
class AnalysisResults:
    """Dependency changes and unresolved imports found for selected targets."""

    changes: tuple[DependencyChanges, ...]
    unresolved: dict[str, frozenset[str]]


class Arguments(argparse.Namespace):
    """Command-line arguments for the dependency synchronizer."""

    def __init__(self):
        """Initialize defaults that argparse replaces with parsed values."""
        super().__init__()
        self.check: bool = False
        self.files: list[Path] = []


def _canonical_label(label: str) -> str:
    if label.startswith("//") and ":" not in label:
        return f"{label}:{label.rsplit('/', 1)[-1]}"
    if label.startswith("@") and ":" in label:
        package, target = label.rsplit(":", 1)
        if package.rsplit("/", 1)[-1] == target:
            return package
    return label


def _string_list(call: ast.Call, attribute: str) -> list[str]:
    keyword = next(
        (keyword for keyword in call.keywords if keyword.arg == attribute), None
    )
    if keyword is None or not isinstance(keyword.value, (ast.List, ast.Tuple)):
        return []
    return [
        element.value
        for element in keyword.value.elts
        if isinstance(element, ast.Constant) and isinstance(element.value, str)
    ]


def _string_value(call: ast.Call, attribute: str) -> str | None:
    keyword = next(
        (keyword for keyword in call.keywords if keyword.arg == attribute), None
    )
    if (
        keyword is not None
        and isinstance(keyword.value, ast.Constant)
        and isinstance(keyword.value.value, str)
    ):
        return keyword.value.value
    return None


def _rule_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    return None


def _has_keyword(call: ast.Call, attribute: str) -> bool:
    return any(keyword.arg == attribute for keyword in call.keywords)


def _has_tag(call: ast.Call, tag: str) -> bool:
    return tag in _string_list(call, "tags")


def _absolute_label(package: Path, value: str) -> str:
    return _canonical_label(
        _package_label(package, value[1:]) if value.startswith(":") else value
    )


def _declared_deps(call: ast.Call, package: Path) -> frozenset[str]:
    return frozenset(
        _absolute_label(package, value) for value in _string_list(call, "deps")
    )


def _kept_deps(lines: list[str], call: ast.Call, package: Path) -> frozenset[str]:
    if call.end_lineno is None:
        raise ValueError("Could not locate the end of a rule with a # keep dependency")
    kept: set[str] = set()
    for line in lines[call.lineno - 1 : call.end_lineno]:
        if "# keep" not in line:
            continue
        before_comment = line.split("# keep", 1)[0]
        try:
            value = cast(
                "object", ast.literal_eval(before_comment.strip().removesuffix(","))
            )
        except (SyntaxError, ValueError) as error:
            raise ValueError(f"Invalid # keep dependency: {line.strip()}") from error
        if not isinstance(value, str):
            raise TypeError(f"Invalid # keep dependency: {line.strip()}")
        kept.add(_absolute_label(package, value))
    return frozenset(kept)


def _package_label(package: Path, target: str) -> str:
    return f"//{package.as_posix()}:{target}"


def _load_targets(
    repository: Path,
) -> tuple[list[PythonTarget], list[PyrightTarget], dict[str, str]]:
    targets: list[PythonTarget] = []
    pyright_targets: list[PyrightTarget] = []
    proto_sources: dict[str, Path] = {}
    py_proto_deps: dict[str, str] = {}
    for build_file in repository.rglob("BUILD.bazel"):
        relative_build_file = build_file.relative_to(repository)
        if relative_build_file.parts[0] not in {"defcl", "define", "tools"}:
            continue
        package = relative_build_file.parent
        contents = build_file.read_text()
        lines = contents.splitlines()
        tree = ast.parse(contents, filename=str(relative_build_file))
        for statement in tree.body:
            if not isinstance(statement, ast.Expr) or not isinstance(
                statement.value, ast.Call
            ):
                continue
            call = statement.value
            rule_class = _rule_name(call)
            target_name = _string_value(call, "name")
            if target_name is None:
                continue
            label = _package_label(package, target_name)
            if rule_class == "proto_library":
                sources = _string_list(call, "srcs")
                if len(sources) == 1:
                    proto_sources[label] = package / sources[0]
            elif rule_class == "py_proto_library":
                deps = _string_list(call, "deps")
                if len(deps) == 1:
                    dependency = deps[0]
                    if dependency.startswith(":"):
                        dependency = _package_label(package, dependency[1:])
                    py_proto_deps[label] = dependency
            elif rule_class == "pyright_test" and not _has_keyword(call, "srcs"):
                pyright_targets.append(
                    PyrightTarget(
                        label=label,
                        build_file=relative_build_file,
                        deps=_declared_deps(call, package),
                        kept_deps=_kept_deps(lines, call, package),
                        include_subpackages=_has_tag(call, "include-subpackages"),
                    )
                )
            elif rule_class in PYTHON_RULE_CLASSES:
                sources = _string_list(call, "srcs")
                if len(sources) != 1:
                    raise ValueError(
                        f"{label} must have exactly one Python source, found {sources}"
                    )
                if not sources[0].endswith(".py"):
                    raise ValueError(
                        f"{label} source must be a Python file, found {sources[0]!r}"
                    )
                targets.append(
                    PythonTarget(
                        label=label,
                        rule_class=rule_class,
                        build_file=relative_build_file,
                        source=package / sources[0].removeprefix(":"),
                        deps=_declared_deps(call, package),
                        kept_deps=_kept_deps(lines, call, package),
                        generated_source=sources[0].startswith(":"),
                    )
                )

    module_owners = {
        module_name(target.source): target.label
        for target in targets
        if target.source.name != "pyright_test_runner.py"
    }
    module_owners.update(
        {
            target.source.stem: target.label
            for target in targets
            if target.source.parent == Path("tools")
        }
    )
    for label, proto_dep in py_proto_deps.items():
        source = proto_sources.get(proto_dep)
        if source is not None:
            module_owners[module_name(source.with_suffix("")) + "_pb2"] = label
    return targets, pyright_targets, module_owners


def module_name(source: Path) -> str:
    """Return the importable module name for a repository-relative source."""
    if source.name == "__init__.py":
        return ".".join(source.parent.parts)
    return ".".join(source.with_suffix("").parts)


def _is_unresolved_module(
    module: str,
    module_owners: dict[str, str],
    external_module_owners: dict[str, str],
) -> bool:
    top_level = module.partition(".")[0]
    return (
        top_level not in sys.stdlib_module_names
        and module != "__future__"
        and _resolve_import(module, module_owners, external_module_owners) is None
    )


def analyze_imports(
    tree: ast.AST,
    module_owners: dict[str, str],
    external_module_owners: dict[str, str],
) -> ImportAnalysis:
    """Resolve import owners and report imports with no known owner."""
    dependencies: set[str] = set()
    unresolved: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                owner = _resolve_import(
                    alias.name, module_owners, external_module_owners
                )
                if owner is not None:
                    dependencies.add(owner)
                elif _is_unresolved_module(
                    alias.name, module_owners, external_module_owners
                ):
                    unresolved.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            package_owner_required = False
            for alias in node.names:
                candidate = f"{node.module}.{alias.name}"
                if candidate in module_owners:
                    dependencies.add(module_owners[candidate])
                else:
                    package_owner_required = True
            if package_owner_required:
                owner = _resolve_import(
                    node.module, module_owners, external_module_owners
                )
                if owner is not None:
                    dependencies.add(owner)
                elif _is_unresolved_module(
                    node.module, module_owners, external_module_owners
                ):
                    unresolved.add(node.module)
    return ImportAnalysis(frozenset(dependencies), frozenset(unresolved))


def _pytest_fixture_name(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> str | None:
    for decorator in node.decorator_list:
        fixture_call: ast.Call | None = None
        fixture_decorator = decorator
        if isinstance(decorator, ast.Call):
            fixture_call = decorator
            fixture_decorator = decorator.func
        if not (
            isinstance(fixture_decorator, ast.Attribute)
            and isinstance(fixture_decorator.value, ast.Name)
            and fixture_decorator.value.id == "pytest"
            and fixture_decorator.attr == "fixture"
        ):
            continue
        if fixture_call is not None:
            for keyword in fixture_call.keywords:
                if (
                    keyword.arg == "name"
                    and isinstance(keyword.value, ast.Constant)
                    and isinstance(keyword.value.value, str)
                ):
                    return keyword.value.value
        return node.name
    return None


def fixture_names(tree: ast.Module) -> frozenset[str]:
    """Return pytest fixture names defined in a conftest module."""
    fixtures = {
        fixture_name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        if (fixture_name := _pytest_fixture_name(node)) is not None
    }
    return frozenset(fixtures)


def requested_fixture_names(tree: ast.Module) -> frozenset[str]:
    """Return names pytest may inject as test or fixture function parameters."""
    names: set[str] = set()
    functions: list[ast.FunctionDef | ast.AsyncFunctionDef] = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    for statement in tree.body:
        if isinstance(statement, ast.ClassDef) and statement.name.startswith("Test"):
            functions.extend(
                node
                for node in statement.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            )
    for node in functions:
        if not node.name.startswith("test") and _pytest_fixture_name(node) is None:
            continue
        arguments = node.args
        names.update(argument.arg for argument in arguments.posonlyargs)
        names.update(argument.arg for argument in arguments.args)
        names.update(argument.arg for argument in arguments.kwonlyargs)
    return frozenset(names)


def _resolve_import(
    module: str,
    module_owners: dict[str, str],
    external_module_owners: dict[str, str],
) -> str | None:
    candidate = module
    while candidate:
        if candidate in module_owners:
            return module_owners[candidate]
        candidate = candidate.rpartition(".")[0]

    for prefix, label in BAZEL_IMPORTS.items():
        if module == prefix or module.startswith(f"{prefix}."):
            return label
    return external_module_owners.get(module.partition(".")[0])


def _pypi_label(distribution: str) -> str:
    normalized = re.sub(r"[-_.]+", "_", distribution).lower()
    return f"@pypi//{normalized}"


def _external_module_owners() -> dict[str, str]:
    owners: dict[str, str] = {}
    for module, distributions in importlib.metadata.packages_distributions().items():
        labels = {_pypi_label(distribution) for distribution in distributions}
        if len(labels) > 1:
            formatted_labels = ", ".join(sorted(labels))
            raise ValueError(
                f"Import package {module!r} is provided by multiple distributions: {formatted_labels}"
            )
        if labels:
            owners[module] = labels.pop()
    return owners


def _expected_deps(
    parsed_target: ParsedTarget,
    import_analysis: ImportAnalysis,
    module_owners: dict[str, str],
    conftest_fixtures: dict[Path, frozenset[str]],
) -> frozenset[str]:
    target = parsed_target.target
    expected = set(import_analysis.dependencies)
    expected.update(target.kept_deps)
    if target.source.name == "__init__.py":
        expected.update(target.deps)
    expected.discard(target.label)
    if target.rule_class == "py_test":
        requested_fixtures = requested_fixture_names(parsed_target.tree)
        package = target.source.parent
        while package.parts:
            conftest = package / "conftest.py"
            if requested_fixtures & conftest_fixtures.get(conftest, frozenset()):
                conftest_owner = module_owners.get(module_name(conftest))
                if conftest_owner is not None and conftest_owner != target.label:
                    expected.add(conftest_owner)
            package = package.parent
    return frozenset(expected)


def _find_rule_bounds(contents: str, target_name: str) -> tuple[int, int]:
    tree = ast.parse(contents)
    for node in tree.body:
        if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
            continue
        for keyword in node.value.keywords:
            if (
                keyword.arg == "name"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value == target_name
            ):
                if node.end_lineno is None:
                    raise ValueError(f"Could not locate target {target_name}")
                return node.lineno - 1, node.end_lineno
    raise ValueError(f"Could not locate target {target_name}")


def _render_label(label: str, target: DependencyTarget) -> str:
    package = target.label.rsplit(":", 1)[0]
    if label.startswith(f"{package}:"):
        return f":{label.rsplit(':', 1)[1]}"
    if label.startswith("@") and ":" in label:
        repository_package, name = label.rsplit(":", 1)
        if repository_package.rsplit("/", 1)[-1] == name:
            return repository_package
    return label


def replace_deps(
    rule_lines: list[str], deps: frozenset[str], target: DependencyTarget
) -> list[str]:
    """Replace or add a rule's deps attribute."""
    text = "".join(rule_lines)
    tree = ast.parse(text)
    call = tree.body[0]
    if not isinstance(call, ast.Expr) or not isinstance(call.value, ast.Call):
        raise TypeError("Expected a rule call")
    deps_keyword = next(
        (keyword for keyword in call.value.keywords if keyword.arg == "deps"), None
    )
    indent = " " * 4
    if deps:
        rendered = [f"{indent}deps = [\n"]
        rendered.extend(
            (
                f'{indent * 2}"{_render_label(label, target)}",'
                f"{'  # keep' if label in target.kept_deps else ''}\n"
            )
            for label in sorted(deps)
        )
        rendered.append(f"{indent}],\n")
    else:
        rendered = []

    if deps_keyword is not None:
        if deps_keyword.value.end_lineno is None:
            raise ValueError("Could not locate deps")
        start = deps_keyword.value.lineno - 1
        end = deps_keyword.value.end_lineno
        if start == end - 1:
            start = deps_keyword.value.lineno - 1
        return rule_lines[:start] + rendered + rule_lines[end:]

    closing = len(rule_lines) - 1
    return rule_lines[:closing] + rendered + rule_lines[closing:]


def _apply_changes(repository: Path, changes: list[DependencyChanges]) -> None:
    by_build_file: dict[Path, list[DependencyChanges]] = {}
    for change in changes:
        by_build_file.setdefault(change.target.build_file, []).append(change)

    for relative_build_file, file_changes in by_build_file.items():
        build_file = repository / relative_build_file
        lines = build_file.read_text().splitlines(keepends=True)
        for change in sorted(
            file_changes, key=lambda item: item.target.label, reverse=True
        ):
            target_name = change.target.label.rsplit(":", 1)[1]
            start, end = _find_rule_bounds("".join(lines), target_name)
            lines[start:end] = replace_deps(
                lines[start:end], change.expected, change.target
            )
        _ = build_file.write_text("".join(lines))


def _relative_files(files: list[Path], repository: Path) -> frozenset[Path]:
    return frozenset(
        path.resolve().relative_to(repository) if path.is_absolute() else path
        for path in files
    )


def _selected_targets(
    parsed_targets: tuple[ParsedTarget, ...], selected_files: frozenset[Path]
) -> tuple[ParsedTarget, ...]:
    if not selected_files:
        return parsed_targets
    changed_conftest_packages = {
        path.parent for path in selected_files if path.name == "conftest.py"
    }
    return tuple(
        parsed_target
        for parsed_target in parsed_targets
        if (
            parsed_target.target.source in selected_files
            or parsed_target.target.build_file in selected_files
            or (
                parsed_target.target.rule_class == "py_test"
                and any(
                    parsed_target.target.source.is_relative_to(package)
                    for package in changed_conftest_packages
                )
            )
        )
    )


def _load_repository(
    repository: Path,
    external_module_owners: dict[str, str],
) -> RepositoryAnalysis:
    targets, pyright_targets, module_owners = _load_targets(repository)
    parsed_targets = tuple(
        ParsedTarget(
            target,
            ast.parse(
                (repository / target.source).read_text(),
                filename=str(target.source),
            ),
        )
        for target in targets
        if not target.generated_source
    )
    conftest_fixtures = {
        parsed_target.target.source: fixture_names(parsed_target.tree)
        for parsed_target in parsed_targets
        if parsed_target.target.source.name == "conftest.py"
    }
    return RepositoryAnalysis(
        repository,
        parsed_targets,
        module_owners,
        external_module_owners,
        conftest_fixtures,
        tuple(pyright_targets),
    )


def load_repository(repository: Path) -> RepositoryAnalysis:
    """Load targets and parse each analyzable source file once."""
    return _load_repository(repository, _external_module_owners())


def _pyright_owner(
    pyright_by_package: dict[Path, PyrightTarget], python_package: Path
) -> PyrightTarget | None:
    package = python_package
    while package.parts:
        possible_owner = pyright_by_package.get(package)
        if possible_owner is not None and (
            package == python_package or possible_owner.include_subpackages
        ):
            return possible_owner
        package = package.parent
    return None


def _pyright_dependency_changes(
    repository_analysis: RepositoryAnalysis,
    selected_targets: tuple[ParsedTarget, ...],
    selected_files: frozenset[Path],
) -> tuple[DependencyChanges, ...]:
    pyright_targets = repository_analysis.pyright_targets
    expected_by_label: dict[str, set[str]] = {
        target.label: set(target.kept_deps) for target in pyright_targets
    }
    pyright_by_package = {
        target.build_file.parent: target for target in pyright_targets
    }
    owner_by_python_label: dict[str, PyrightTarget] = {}
    for parsed_target in repository_analysis.parsed_targets:
        python_target = parsed_target.target
        owner = _pyright_owner(pyright_by_package, python_target.build_file.parent)
        if owner is None:
            continue
        owner_by_python_label[python_target.label] = owner
        expected_by_label[owner.label].add(python_target.label)

    if selected_files:
        selected_pyright_labels = {
            pyright_target.label
            for pyright_target in pyright_targets
            if pyright_target.build_file in selected_files
        }
        selected_pyright_labels.update(
            owner.label
            for parsed_target in selected_targets
            if (owner := owner_by_python_label.get(parsed_target.target.label))
            is not None
        )
    else:
        selected_pyright_labels = {target.label for target in pyright_targets}

    changes: list[DependencyChanges] = []
    for target in pyright_targets:
        if target.label not in selected_pyright_labels:
            continue
        expected = frozenset(expected_by_label[target.label])
        if target.deps != expected:
            changes.append(DependencyChanges(target, expected))
    return tuple(changes)


def analyze_targets(
    repository_analysis: RepositoryAnalysis, files: list[Path]
) -> AnalysisResults:
    """Analyze selected targets without modifying repository files."""
    selected_files = _relative_files(files, repository_analysis.repository)
    parsed_targets = _selected_targets(
        repository_analysis.parsed_targets, selected_files
    )
    import_analyses = {
        parsed_target.target.label: analyze_imports(
            parsed_target.tree,
            repository_analysis.module_owners,
            repository_analysis.external_module_owners,
        )
        for parsed_target in parsed_targets
    }
    unresolved = {
        label: analysis.unresolved
        for label, analysis in import_analyses.items()
        if analysis.unresolved
    }
    dependency_changes = tuple(
        DependencyChanges(parsed_target.target, expected)
        for parsed_target in parsed_targets
        if (
            expected := _expected_deps(
                parsed_target,
                import_analyses[parsed_target.target.label],
                repository_analysis.module_owners,
                repository_analysis.conftest_fixtures,
            )
        )
        != parsed_target.target.deps
    )
    pyright_changes = _pyright_dependency_changes(
        repository_analysis, parsed_targets, selected_files
    )
    return AnalysisResults(dependency_changes + pyright_changes, unresolved)


def report_results(
    repository_analysis: RepositoryAnalysis,
    results: AnalysisResults,
    *,
    check_only: bool,
) -> int:
    """Report analysis results and optionally update BUILD files."""
    if results.unresolved:
        for label, imports in results.unresolved.items():
            print(label)
            for module in sorted(imports):
                print(f"  unresolved import {module}")
        return 1
    if not results.changes:
        return 0

    for change in results.changes:
        print(change.target.label)
        for label in sorted(change.missing):
            print(f"  add {label}")
        for label in sorted(change.unnecessary):
            print(f"  remove {label}")

    if not check_only:
        _apply_changes(repository_analysis.repository, list(results.changes))
        _ = print("\nUpdated BUILD.bazel files. Re-run the command to verify.")
    return 1


def main() -> int:
    """Check or repair all hand-maintained Python target dependencies."""
    parser = argparse.ArgumentParser()
    _ = parser.add_argument(
        "--check", action="store_true", help="Do not modify BUILD files."
    )
    _ = parser.add_argument(
        "files",
        nargs="*",
        type=Path,
        help="Only check targets owned by these Python or BUILD files.",
    )
    args = parser.parse_args(namespace=Arguments())
    repository_analysis = load_repository(Path.cwd())
    results = analyze_targets(repository_analysis, args.files)
    return report_results(repository_analysis, results, check_only=args.check)


if __name__ == "__main__":
    sys.exit(main())
