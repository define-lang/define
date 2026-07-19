# pyright: reportUnusedCallResult=false
# pyright: reportImplicitStringConcatenation=false
"""Shared test fixtures for the Define compiler."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol, cast, overload

import pytest

from define.compiler import ast, diagnostics, parser
from define.compiler.data_structures import typed_name_dict
from define.compiler.graphs import action_call_graph
from define.compiler.validator import test_helpers, validation_result
from define.compiler.validator.reference_graph import (
    operation_graph,
    reference_graph_validator,
)
from define.compiler.validator.structural import program_validator
from define.testdata import path_resolver

_PARSER = parser.Parser()
_TEST_FQUN = "my.domain.com:my_lib"

type PositionReferenceFor = Callable[[str], ast.PositionReference]


def parse_and_transform(
    source: str, file_path: PurePosixPath | None = None
) -> ast.Program:
    """Parse and transform source into an AST Program via the shared parser."""
    result = _PARSER.parse_and_transform(source, file_path=file_path)
    assert result.diagnostics == []
    assert result.exception is None
    assert result.program is not None
    return result.program


def _make_position_reference(chained_name: str) -> ast.PositionReference:
    """Create a PositionReference by parsing a chained name in a minimal action context."""
    elements = chained_name.split("::")
    local_defs: list[str] = []
    seen: set[str] = set()
    for elem in elements:
        if not elem.startswith("position<"):
            continue
        name = elem[len("position<") : -1]
        if name.startswith("/"):
            continue
        if name in seen:
            continue
        seen.add(name)
        local_defs.append(f"        define the position<{name}>.\n")

    source = (
        f"define the potential action<{_TEST_FQUN}:/test> {{\n"
        "    define the position<_trigger>.\n"
        "    it happens when {\n"
        "        the position<_trigger> has a particle.\n"
        "    } and it does {\n"
        + "".join(local_defs)
        + f"        create a particle in {chained_name}.\n"
        "    }\n"
        "}\n"
    )
    program = parse_and_transform(source)
    action_def = program.definitions[0]
    assert isinstance(action_def, ast.ActionDefinition)
    for stmt in action_def.action_statements.statements:
        if isinstance(stmt, ast.CreateParticleStatement):
            return stmt.target_position
    raise ValueError(f"No create statement found for: {chained_name}")


@pytest.fixture
def position_reference_for() -> PositionReferenceFor:
    """Create a PositionReference from a source-form chained name.

    Pass the source-form chained name (e.g. ``"position<local>::position</x>"``).
    Local position names (without ``/``) are auto-defined in the action body.
    """
    return _make_position_reference


@dataclass
class FullValidationResult:
    """Result of running both structural and reference graph validation."""

    program_result: validation_result.ProgramValidationResult
    reference_graph_result: reference_graph_validator.ReferenceGraphValidationResult

    @property
    def action_call_graph(self) -> action_call_graph.ActionCallGraph:
        """The actions this program's actions trigger."""
        return self.reference_graph_result.action_call_graph

    @property
    def operation_graphs(
        self,
    ) -> typed_name_dict.TypedNameDict[
        ast.GlobalTypedName, operation_graph.OperationGraph
    ]:
        """Every action's operation dependency graph."""
        return self.reference_graph_result.operation_graphs


type ParseAndValidateFile = Callable[
    [str | bytes], validation_result.FileValidationResult
]
_DEFAULT_RELATIVE_PATH = PurePosixPath("path.dfn")


class ValidateProject(Protocol):
    """Callable that validates a multi-file project and returns results."""

    def __call__(
        self,
        files: dict[str, str],
        *,
        universe_name: str = ...,
        max_workers: int | None = ...,
        local_deps: dict[str, str] | None = ...,
        sub_roots: dict[str, str] | None = ...,
        entry_file: str = ...,
    ) -> validation_result.ProgramValidationResult:
        """Validate a project with the given files."""
        ...


class ValidateSourceAsFile(Protocol):
    """Callable that validates source as a file and returns diagnostics."""

    @overload
    def __call__(
        self,
        source: str,
        expected_universe_name: str,
    ) -> list[diagnostics.Diagnostic]: ...

    @overload
    def __call__(
        self,
        source: str,
        expected_universe_name: str,
        relative_path: PurePosixPath,
    ) -> list[diagnostics.Diagnostic]: ...


def _run_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    files: dict[str, str],
    universe_name: str,
    max_workers: int | None = None,
    local_deps: dict[str, str] | None = None,
    sub_roots: dict[str, str] | None = None,
    entry_file: str = "test.dfn",
) -> validation_result.ProgramValidationResult:
    test_helpers.write_project_config(tmp_path, universe_name)
    if local_deps is not None:
        test_helpers.write_local_deps_config(tmp_path, local_deps)
        for dep_path in local_deps.values():
            (tmp_path / dep_path).mkdir(parents=True, exist_ok=True)
    if sub_roots is not None:
        for sub_root_path, sub_universe in sub_roots.items():
            test_helpers.write_sub_root(tmp_path, sub_root_path, sub_universe)
    for name, content in files.items():
        file_path = tmp_path / name
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    pv = program_validator.ProgramStructuralValidator(_PARSER)
    return pv.validate_program(PurePosixPath(entry_file), max_workers=max_workers)


@pytest.fixture
def validate_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> ValidateProject:
    """Set up a multi-file project in a temp dir and validate it."""

    def _run(
        files: dict[str, str],
        *,
        universe_name: str = "my.domain.com:my_lib",
        max_workers: int | None = None,
        local_deps: dict[str, str] | None = None,
        sub_roots: dict[str, str] | None = None,
        entry_file: str = "test.dfn",
    ) -> validation_result.ProgramValidationResult:
        return _run_validation(
            tmp_path,
            monkeypatch,
            files,
            universe_name,
            max_workers=max_workers,
            local_deps=local_deps,
            sub_roots=sub_roots,
            entry_file=entry_file,
        )

    return _run


@pytest.fixture
def parse_and_validate_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> ParseAndValidateFile:
    """Parse and validate a single source string as a file in a temp project."""

    def _run(source: str | bytes) -> validation_result.FileValidationResult:
        relative_path = PurePosixPath("test.dfn")
        source_path = tmp_path / relative_path
        test_helpers.write_project_config(tmp_path, "my.domain.com:my_lib")
        if isinstance(source, str):
            source_path.write_text(source, encoding="utf-8")
        else:
            source_path.write_bytes(source)
        monkeypatch.chdir(tmp_path)
        results = (
            program_validator.ProgramStructuralValidator(_PARSER)
            .validate_program(relative_path)
            .file_results
        )
        assert len(results) == 1
        return results[0]

    return _run


@pytest.fixture
def validate_source_as_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> ValidateSourceAsFile:
    """Validate one source string as a file and return diagnostics."""

    def _run(
        source: str,
        expected_universe_name: str,
        relative_path: PurePosixPath = _DEFAULT_RELATIVE_PATH,
    ) -> list[diagnostics.Diagnostic]:
        source_path = tmp_path / relative_path
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text(source, encoding="utf-8")
        test_helpers.write_project_config(tmp_path, expected_universe_name)
        monkeypatch.chdir(tmp_path)
        results = (
            program_validator.ProgramStructuralValidator(_PARSER)
            .validate_program(relative_path)
            .file_results
        )
        assert len(results) == 1
        return list(results[0].diagnostics)

    return _run


type ValidateNonFilesystemWithReferenceGraph = Callable[
    [str], validation_result.ProgramValidationResult
]


class ValidateTestdataNonFilesystemWithReferenceGraph(Protocol):
    """Validate the convention-derived non-filesystem source."""

    def __call__(self) -> validation_result.ProgramValidationResult:
        """Run structural and reference graph validation."""
        ...


def _testdata_directory(request: pytest.FixtureRequest) -> Path:
    test_function = cast("pytest.Function", request.node)
    test_class = test_function.parent
    test_class_name = test_class.name if isinstance(test_class, pytest.Class) else None
    return path_resolver.directory_for(
        request.path,
        test_function.name,
        test_class_name,
    )


@pytest.fixture
def testdata_project_directory(
    request: pytest.FixtureRequest,
) -> Path:
    """Return the current test's convention-derived project directory."""
    return _testdata_directory(request)


@pytest.fixture
def validate_non_filesystem_with_reference_graph() -> (
    ValidateNonFilesystemWithReferenceGraph
):
    """Validate source text through both structural and reference graph validation."""

    def _run(source: str) -> validation_result.ProgramValidationResult:
        result = program_validator.ProgramStructuralValidator(
            _PARSER
        ).validate_program_non_filesystem(source)
        reference_graph_validator.ReferenceGraphValidator(
            result.reference_graph,
            result.definition_results,
        ).validate()
        return result

    return _run


@pytest.fixture
def validate_testdata_non_filesystem_with_reference_graph(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> ValidateTestdataNonFilesystemWithReferenceGraph:
    """Validate source.dfn from the current test's derived testdata directory."""
    directory = _testdata_directory(request)
    source = (directory / "source.dfn").read_text(encoding="utf-8")

    def _run() -> validation_result.ProgramValidationResult:
        monkeypatch.chdir(directory)
        result = program_validator.ProgramStructuralValidator(
            _PARSER
        ).validate_program_non_filesystem(source)
        reference_graph_validator.ReferenceGraphValidator(
            result.reference_graph,
            result.definition_results,
        ).validate()
        return result

    return _run


def _run_reference_graph_validation(
    structural_result: validation_result.ProgramValidationResult,
) -> FullValidationResult:
    reference_graph_result = reference_graph_validator.ReferenceGraphValidator(
        structural_result.reference_graph,
        structural_result.definition_results,
    ).validate()
    return FullValidationResult(
        program_result=structural_result,
        reference_graph_result=reference_graph_result,
    )


class ValidateProjectWithReferenceGraph(Protocol):
    """Callable that runs structural + reference graph validation."""

    def __call__(
        self,
        files: dict[str, str],
        *,
        universe_name: str = ...,
        max_workers: int | None = ...,
        local_deps: dict[str, str] | None = ...,
        sub_roots: dict[str, str] | None = ...,
        entry_file: str = ...,
    ) -> FullValidationResult:
        """Validate a project through both validation phases."""
        ...


class ValidateTestdataProjectWithReferenceGraph(Protocol):
    """Validate the convention-derived filesystem project."""

    def __call__(
        self,
        *,
        max_workers: int | None = ...,
        entry_file: str = ...,
    ) -> FullValidationResult:
        """Run structural and reference graph validation."""
        ...


@pytest.fixture
def validate_project_with_reference_graph(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> ValidateProjectWithReferenceGraph:
    """Set up a multi-file project and run both structural and reference graph validation."""

    def _run(
        files: dict[str, str],
        *,
        universe_name: str = "my.domain.com:my_lib",
        max_workers: int | None = None,
        local_deps: dict[str, str] | None = None,
        sub_roots: dict[str, str] | None = None,
        entry_file: str = "test.dfn",
    ) -> FullValidationResult:
        structural_result = _run_validation(
            tmp_path,
            monkeypatch,
            files,
            universe_name,
            max_workers=max_workers,
            local_deps=local_deps,
            sub_roots=sub_roots,
            entry_file=entry_file,
        )
        return _run_reference_graph_validation(structural_result)

    return _run


@pytest.fixture
def validate_testdata_project_with_reference_graph(
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> ValidateTestdataProjectWithReferenceGraph:
    """Stage and validate the current test's convention-derived project."""
    directory = _testdata_directory(request)

    def _run(
        *,
        max_workers: int | None = None,
        entry_file: str = "test.dfn",
    ) -> FullValidationResult:
        monkeypatch.chdir(directory)
        structural_result = program_validator.ProgramStructuralValidator(
            _PARSER
        ).validate_program(PurePosixPath(entry_file), max_workers=max_workers)
        return _run_reference_graph_validation(structural_result)

    return _run
