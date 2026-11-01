# pyright: reportUnusedCallResult=false
# NOTE: Tests for new syntax or diagnostics belong in program_validator_tests/,
# not here. This file tests FileStructuralValidator internals only (edges,
# error handling).

from __future__ import annotations

import hashlib
import types
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from define.compiler import config
from define.compiler.data_structures import define_path
from define.compiler.errors import diagnostics, exceptions, parser_exceptions
from define.compiler.parsing import test_helpers
from define.compiler.validator import validation_result
from define.compiler.validator.structural import file_validator

if TYPE_CHECKING:
    from define.compiler import ast
    from define.compiler.graphs import reference_graph


def _make_context(
    tmp_path: Path,
    file_name: str = "test.dfn",
    fqun: str = "my.domain.com:my_lib",
    sub_root_mappings: dict[str, define_path.DefinePath] | None = None,
) -> file_validator.FileValidationContext:
    return file_validator.FileValidationContext(
        file_path=define_path.DefinePath(file_name),
        root_prefix=define_path.DefinePath(str(tmp_path)),
        root_config=config.ProjectRootConfig(
            fqun=fqun,
            sub_roots=types.MappingProxyType(sub_root_mappings or {}),
        ),
    )


def _parse_program(source: str) -> ast.Program:
    return test_helpers.parse(source, PurePosixPath("/test.dfn"))


def _load_and_validate_every_definition(
    context: file_validator.FileValidationContext,
) -> validation_result.FileValidationResult:
    loaded_file = file_validator.FileStructuralValidator().load_file(context)
    definition_results: list[validation_result.DefinitionValidationResult] = []
    for definition in loaded_file.definitions.values():
        definition_results.append(loaded_file.validate_definition(definition))
    return loaded_file.build_file_validation_result(definition_results)


def _reference_edges(
    result: validation_result.FileValidationResult,
) -> list[reference_graph.ReferenceEdge]:
    return [
        edge
        for definition_result in result.definition_results
        for edge in definition_result.reference_edges
    ]


class TestFileStructuralValidatorSuccess:
    def test_valid_position(self, tmp_path: Path):
        source = "define the potential position<my.domain.com:my_lib:/test>.\n"
        (tmp_path / "test.dfn").write_text(source, encoding="utf-8", newline="\n")
        ctx = _make_context(tmp_path)
        result = _load_and_validate_every_definition(ctx)

        assert result.exception is None
        assert result.diagnostics == []
        assert result.source_digest == hashlib.sha256(source.encode()).digest()
        assert len(result.definition_results) == 1
        assert (
            result.definition_results[0].definition.typed_name.name_type == "position"
        )

    def test_valid_action(self, tmp_path: Path):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<_noop>.\n"
            "    it happens when {\n"
            "        the position<_noop> has a particle.\n"
            "    } and it does {\n"
            "        define the position<__noop>.\n"
            "        create a particle in position<__noop>.\n"
            "    }\n"
            "}\n"
        )
        (tmp_path / "test.dfn").write_text(source, encoding="utf-8", newline="\n")
        ctx = _make_context(tmp_path)
        result = _load_and_validate_every_definition(ctx)

        assert result.exception is None
        assert result.diagnostics == []
        assert len(result.definition_results) == 1
        assert result.definition_results[0].definition.typed_name.name_type == "action"


class TestFileStructuralValidatorErrors:
    def test_file_not_found(self, tmp_path: Path):
        ctx = _make_context(tmp_path, file_name="nonexistent.dfn")
        result = _load_and_validate_every_definition(ctx)

        assert isinstance(result.exception, exceptions.SourceFileNotFoundError)
        assert result.exception.filesystem_path == Path(tmp_path / "nonexistent.dfn")
        assert result.definition_results == []
        assert _reference_edges(result) == []

    def test_syntax_error(self, tmp_path: Path):
        (tmp_path / "test.dfn").write_text(
            "not valid define syntax\n", encoding="utf-8", newline="\n"
        )
        ctx = _make_context(tmp_path)
        result = _load_and_validate_every_definition(ctx)

        assert result.exception is not None
        assert result.definition_results == []

    def test_encoding_error(self, tmp_path: Path):
        (tmp_path / "test.dfn").write_bytes(b"\x80\x81\x82")
        ctx = _make_context(tmp_path)
        result = _load_and_validate_every_definition(ctx)

        assert isinstance(result.exception, parser_exceptions.InvalidEncodingError)
        assert result.exception.location.line == 1
        assert result.exception.location.column == 1
        assert result.exception.char == "\\x80"

    def test_encoding_error_multiline(self, tmp_path: Path):
        (tmp_path / "test.dfn").write_bytes(
            b"# first line\n# second line\n# third\x80rest\n"
        )
        ctx = _make_context(tmp_path)
        result = _load_and_validate_every_definition(ctx)

        assert isinstance(result.exception, parser_exceptions.InvalidEncodingError)
        assert result.exception.location.line == 3
        assert result.exception.location.column == 8
        assert result.exception.location.end_line == 3
        assert result.exception.location.end_column == 8
        assert result.exception.char == "\\x80"


class TestFileStructuralValidatorDiagnostics:
    def test_path_mismatch(self, tmp_path: Path):
        source = "define the potential position<my.domain.com:my_lib:/wrong_path>.\n"
        (tmp_path / "test.dfn").write_text(source, encoding="utf-8", newline="\n")
        ctx = _make_context(tmp_path)
        result = _load_and_validate_every_definition(ctx)

        assert [type(d) for d in result.diagnostics] == [
            diagnostics.PathMismatchDiagnostic,
        ]

    def test_fqun_mismatch(self, tmp_path: Path):
        source = "define the potential position<other.domain.com:other_lib:/test>.\n"
        (tmp_path / "test.dfn").write_text(source, encoding="utf-8", newline="\n")
        ctx = _make_context(tmp_path)
        result = _load_and_validate_every_definition(ctx)

        assert [type(d) for d in result.diagnostics] == [
            diagnostics.FqunMismatchDiagnostic,
        ]

    def test_within_file_duplicate(self, tmp_path: Path):
        source = (
            "define the potential position<my.domain.com:my_lib:/test>.\n"
            "define the potential position<my.domain.com:my_lib:/test>.\n"
        )
        (tmp_path / "test.dfn").write_text(source, encoding="utf-8", newline="\n")
        ctx = _make_context(tmp_path)
        result = _load_and_validate_every_definition(ctx)

        assert [type(d) for d in result.diagnostics] == [
            diagnostics.DuplicateDefinitionDiagnostic,
        ]
        assert [
            definition_result.definition.location.line
            for definition_result in result.definition_results
        ] == [1]


class TestDefinitionStructuralValidator:
    def test_validate_definition_returns_result_object(self, tmp_path: Path):
        source = "define the potential position<my.domain.com:my_lib:/test>.\n"
        program = _parse_program(source)
        validator = file_validator.DefinitionStructuralValidator(
            definition=program.definitions[0],
            context=_make_context(tmp_path),
        )

        result = validator.validate_definition()

        assert isinstance(result, validation_result.DefinitionValidationResult)
        assert result.definition == program.definitions[0]
        assert result.diagnostics == []


class TestLoadedFile:
    def test_definitions_hold_the_first_of_duplicates(self, tmp_path: Path):
        source = (
            "define the potential position<my.domain.com:my_lib:/test>.\n"
            "define the potential position<my.domain.com:my_lib:/test>.\n"
        )
        (tmp_path / "test.dfn").write_text(source, encoding="utf-8", newline="\n")
        loaded_file = file_validator.FileStructuralValidator().load_file(
            _make_context(tmp_path)
        )

        assert [
            definition.location.line for definition in loaded_file.definitions.values()
        ] == [1]

    def test_loading_validates_no_definition(self, tmp_path: Path):
        source = (
            "define the potential position<my.domain.com:my_lib:/test> {\n"
            "    it may only contain particles where {\n"
            "        it has the position<my.domain.com:my_lib:/Bad>.\n"
            "    }\n"
            "}\n"
        )
        (tmp_path / "test.dfn").write_text(source, encoding="utf-8", newline="\n")
        loaded_file = file_validator.FileStructuralValidator().load_file(
            _make_context(tmp_path)
        )

        assert loaded_file.file_diagnostics == []


class TestFileStructuralValidatorReferenceDiscovery:
    def test_short_form_reference(self, tmp_path: Path):
        source = (
            "define the potential position<my.domain.com:my_lib:/test> {\n"
            "    it may only contain particles where {\n"
            "        it has the position</other>.\n"
            "    }\n"
            "}\n"
        )
        (tmp_path / "test.dfn").write_text(source, encoding="utf-8", newline="\n")
        ctx = _make_context(tmp_path)
        result = _load_and_validate_every_definition(ctx)

        edges = _reference_edges(result)
        assert len(edges) == 1
        assert (
            edges[0].global_name_reference.full_typed_name
            == "position<my.domain.com:my_lib:/other>"
        )
        assert edges[0].global_name_reference.name_content.fqun is None
        assert (
            edges[0].global_name_reference.enclosing_fqun.canonical
            == "my.domain.com:my_lib"
        )

    def test_cross_universe_reference_configured(self, tmp_path: Path):
        source = (
            "define the potential position<my.domain.com:my_lib:/test> {\n"
            "    it may only contain particles where {\n"
            "        it has the position<other.domain.com:other_lib:/dep>.\n"
            "    }\n"
            "}\n"
        )
        (tmp_path / "test.dfn").write_text(source, encoding="utf-8", newline="\n")
        ctx = _make_context(
            tmp_path,
            sub_root_mappings={
                "other.domain.com:other_lib": define_path.DefinePath("deps/other")
            },
        )
        result = _load_and_validate_every_definition(ctx)

        edges = _reference_edges(result)
        assert len(edges) == 1
        assert (
            edges[0].global_name_reference.full_typed_name
            == "position<other.domain.com:other_lib:/dep>"
        )
        assert edges[0].global_name_reference.name_content.fqun is not None
        assert (
            edges[0].global_name_reference.name_content.fqun.canonical
            == "other.domain.com:other_lib"
        )

    def test_cross_universe_reference_not_configured(self, tmp_path: Path):
        source = (
            "define the potential position<my.domain.com:my_lib:/test> {\n"
            "    it may only contain particles where {\n"
            "        it has the position<other.domain.com:other_lib:/dep>.\n"
            "    }\n"
            "}\n"
        )
        (tmp_path / "test.dfn").write_text(source, encoding="utf-8", newline="\n")
        ctx = _make_context(tmp_path)
        result = _load_and_validate_every_definition(ctx)

        assert [type(d) for d in result.diagnostics] == [
            diagnostics.ExternalUniverseNotConfiguredDiagnostic,
        ]
        assert _reference_edges(result) == []

    def test_multiple_references(self, tmp_path: Path):
        source = (
            "define the potential position<my.domain.com:my_lib:/test> {\n"
            "    it may only contain particles where {\n"
            "        it has the position</dep_a>.\n"
            "        it has the position</dep_b>.\n"
            "    }\n"
            "}\n"
        )
        (tmp_path / "test.dfn").write_text(source, encoding="utf-8", newline="\n")
        ctx = _make_context(tmp_path)
        result = _load_and_validate_every_definition(ctx)

        assert len(_reference_edges(result)) == 2

    def test_same_global_in_many_contexts_emits_one_edge(self, tmp_path: Path):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    it also assigns the position</shared>.\n"
            "    define the position<inner> {\n"
            "        it may only contain particles where {\n"
            "            it has the position</shared>.\n"
            "        }\n"
            "    }\n"
            "    define the position<trigger_pos>.\n"
            "    it happens when {\n"
            "        the position<trigger_pos> has a particle.\n"
            "    } and it does {\n"
            "        create a particle in position</shared>.\n"
            "        move the particle in position</shared> to position<inner>.\n"
            "        destroy the particle in position</shared>.\n"
            "    }\n"
            "}\n"
        )
        (tmp_path / "test.dfn").write_text(source, encoding="utf-8", newline="\n")
        ctx = _make_context(tmp_path)
        result = _load_and_validate_every_definition(ctx)

        assert result.diagnostics == []
        edges = _reference_edges(result)
        assert len(edges) == 1
        assert (
            edges[0].global_name_reference.full_typed_name
            == "position<my.domain.com:my_lib:/shared>"
        )


class TestParticleReferenceEdges:
    def test_chained_globals_produce_multiple_edges(self, tmp_path: Path):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<gateway> {\n"
            "        it may only contain particles where {\n"
            "            it has the action</beta>.\n"
            "        }\n"
            "    }\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        create a particle in position<gateway>::action</beta>::position</gamma>.\n"
            "    }\n"
            "}\n"
        )
        (tmp_path / "test.dfn").write_text(source, encoding="utf-8", newline="\n")
        ctx = _make_context(tmp_path)
        result = _load_and_validate_every_definition(ctx)

        assert result.diagnostics == []
        assert len(_reference_edges(result)) == 2

    def test_local_names_produce_no_edges(self, tmp_path: Path):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<inner_pos>.\n"
            "    it happens when {\n"
            "        the position<run> has a particle.\n"
            "    } and it does {\n"
            "        create a particle in position<inner_pos>.\n"
            "    }\n"
            "}\n"
        )
        (tmp_path / "test.dfn").write_text(source, encoding="utf-8", newline="\n")
        ctx = _make_context(tmp_path)
        result = _load_and_validate_every_definition(ctx)

        assert result.diagnostics == []
        assert _reference_edges(result) == []

    def test_invalid_global_name_produces_no_edges(self, tmp_path: Path):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<my_pos> {\n"
            "        it may only contain particles where {\n"
            "            it has the position</Bad>.\n"
            "        }\n"
            "    }\n"
            "    it happens when {\n"
            "        the position<my_pos> has a particle.\n"
            "    } and it does {\n"
            "        create a particle in position<my_pos>::position</Bad>.\n"
            "    }\n"
            "}\n"
        )
        (tmp_path / "test.dfn").write_text(source, encoding="utf-8", newline="\n")
        ctx = _make_context(tmp_path)
        result = _load_and_validate_every_definition(ctx)

        assert len(result.diagnostics) == 2
        assert isinstance(
            result.diagnostics[0],
            diagnostics.InvalidGlobalNamePathCharacterDiagnostic,
        )
        assert result.diagnostics[0].segment == "Bad"
        assert result.diagnostics[0].chars == ("B",)
        assert result.diagnostics[0].location.line == 4
        assert result.diagnostics[0].location.column == 34
        assert isinstance(
            result.diagnostics[1],
            diagnostics.InvalidGlobalNamePathCharacterDiagnostic,
        )
        assert result.diagnostics[1].segment == "Bad"
        assert result.diagnostics[1].chars == ("B",)
        assert result.diagnostics[1].location.line == 10
        assert result.diagnostics[1].location.column == 58
        assert _reference_edges(result) == []
