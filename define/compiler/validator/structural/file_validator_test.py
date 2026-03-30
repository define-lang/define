# pyright: reportUnusedCallResult=false
# NOTE: Tests for new syntax or diagnostics belong in program_validator_tests/,
# not here. This file tests FileStructuralValidator internals only (edges, discovered
# files, timing stats, error handling).

import types
from pathlib import Path, PurePosixPath

import pytest

from define.compiler import (
    ast,
    diagnostics,
    exceptions,
    parser,
    parser_exceptions,
    transformer,
)
from define.compiler.graphs import reference_graph
from define.compiler.validator import validation_result
from define.compiler.validator.structural import file_validator


@pytest.fixture
def lark_parser() -> parser.Parser:
    return parser.Parser()


def _make_context(
    tmp_path: Path,
    file_name: str = "test.def",
    fqun: str = "my.domain.com:my_lib",
    sub_root_mappings: dict[str, PurePosixPath] | None = None,
) -> file_validator.FileValidationContext:
    return file_validator.FileValidationContext(
        file_path=PurePosixPath(file_name),
        root_prefix=PurePosixPath(str(tmp_path)),
        expected_fqun=fqun,
        sub_root_mappings=types.MappingProxyType(sub_root_mappings or {}),
    )


def _parse_program(source: str, lark_parser: parser.Parser) -> ast.Program:
    parse_result = lark_parser.parse(source, file_path=PurePosixPath("/test.def"))
    assert parse_result.exception is None
    assert parse_result.tree is not None
    return transformer.DefineTransformer().transform(parse_result.tree)


def _reference_edges(
    result: validation_result.FileValidationResult,
) -> list[reference_graph.ReferenceEdge]:
    return [
        edge
        for definition_result in result.definition_results
        for edge in definition_result.reference_edges
    ]


def _discovered_files(
    result: validation_result.FileValidationResult,
) -> list[validation_result.DiscoveredFile]:
    return [
        discovered
        for definition_result in result.definition_results
        for discovered in definition_result.discovered_files
    ]


class TestFileStructuralValidatorSuccess:
    def test_valid_position(self, tmp_path: Path, lark_parser: parser.Parser):
        source = "define the potential position<my.domain.com:my_lib:/test>.\n"
        (tmp_path / "test.def").write_text(source, encoding="utf-8")
        ctx = _make_context(tmp_path)
        result = file_validator.FileStructuralValidator(lark_parser).validate_file(ctx)

        assert result.exception is None
        assert result.diagnostics == []
        assert result.source == source
        assert len(result.definition_results) == 1
        assert (
            result.definition_results[0].definition.typed_name.name_type == "position"
        )

    def test_valid_action(self, tmp_path: Path, lark_parser: parser.Parser):
        source = "define the potential action<my.domain.com:my_lib:/test>.\n"
        (tmp_path / "test.def").write_text(source, encoding="utf-8")
        ctx = _make_context(tmp_path)
        result = file_validator.FileStructuralValidator(lark_parser).validate_file(ctx)

        assert result.exception is None
        assert result.diagnostics == []
        assert len(result.definition_results) == 1
        assert result.definition_results[0].definition.typed_name.name_type == "action"


class TestFileStructuralValidatorErrors:
    def test_file_not_found(self, tmp_path: Path, lark_parser: parser.Parser):
        ctx = _make_context(tmp_path, file_name="nonexistent.def")
        result = file_validator.FileStructuralValidator(lark_parser).validate_file(ctx)

        assert isinstance(result.exception, exceptions.SourceFileNotFoundError)
        assert result.exception.filesystem_path == Path(tmp_path / "nonexistent.def")
        assert result.definition_results == []
        assert _reference_edges(result) == []
        assert _discovered_files(result) == []

    def test_syntax_error(self, tmp_path: Path, lark_parser: parser.Parser):
        (tmp_path / "test.def").write_text(
            "not valid define syntax\n", encoding="utf-8"
        )
        ctx = _make_context(tmp_path)
        result = file_validator.FileStructuralValidator(lark_parser).validate_file(ctx)

        assert result.exception is not None
        assert result.definition_results == []

    def test_encoding_error(self, tmp_path: Path, lark_parser: parser.Parser):
        (tmp_path / "test.def").write_bytes(b"\x80\x81\x82")
        ctx = _make_context(tmp_path)
        result = file_validator.FileStructuralValidator(lark_parser).validate_file(ctx)

        assert isinstance(result.exception, parser_exceptions.InvalidEncodingError)
        assert result.exception.line == 1
        assert result.exception.column == 1
        assert result.exception.char == "\\x80"

    def test_encoding_error_multiline(self, tmp_path: Path, lark_parser: parser.Parser):
        (tmp_path / "test.def").write_bytes(b"first line\nsecond line\nthird\x80rest\n")
        ctx = _make_context(tmp_path)
        result = file_validator.FileStructuralValidator(lark_parser).validate_file(ctx)

        assert isinstance(result.exception, parser_exceptions.InvalidEncodingError)
        assert result.exception.line == 3
        assert result.exception.column == 6
        assert result.exception.char == "\\x80"
        assert result.exception.context.startswith("third")


class TestFileStructuralValidatorDiagnostics:
    def test_path_mismatch(self, tmp_path: Path, lark_parser: parser.Parser):
        source = "define the potential position<my.domain.com:my_lib:/wrong_path>.\n"
        (tmp_path / "test.def").write_text(source, encoding="utf-8")
        ctx = _make_context(tmp_path)
        result = file_validator.FileStructuralValidator(lark_parser).validate_file(ctx)

        assert [type(d) for d in result.diagnostics] == [
            diagnostics.PathMismatchDiagnostic,
        ]

    def test_fqun_mismatch(self, tmp_path: Path, lark_parser: parser.Parser):
        source = "define the potential position<other.domain.com:other_lib:/test>.\n"
        (tmp_path / "test.def").write_text(source, encoding="utf-8")
        ctx = _make_context(tmp_path)
        result = file_validator.FileStructuralValidator(lark_parser).validate_file(ctx)

        assert [type(d) for d in result.diagnostics] == [
            diagnostics.FqunMismatchDiagnostic,
        ]

    def test_within_file_duplicate(self, tmp_path: Path, lark_parser: parser.Parser):
        source = (
            "define the potential position<my.domain.com:my_lib:/test>.\n"
            "define the potential position<my.domain.com:my_lib:/test>.\n"
        )
        (tmp_path / "test.def").write_text(source, encoding="utf-8")
        ctx = _make_context(tmp_path)
        result = file_validator.FileStructuralValidator(lark_parser).validate_file(ctx)

        assert [type(d) for d in result.diagnostics] == [
            diagnostics.DuplicateDefinitionDiagnostic,
        ]
        assert [
            definition_result.definition.typed_name.source_typed_name
            for definition_result in result.definition_results
        ] == [
            "position<my.domain.com:my_lib:/test>",
            "position<my.domain.com:my_lib:/test>",
        ]


class TestDefinitionStructuralValidator:
    def test_validate_definition_returns_result_object(
        self, tmp_path: Path, lark_parser: parser.Parser
    ):
        source = "define the potential position<my.domain.com:my_lib:/test>.\n"
        program = _parse_program(source, lark_parser)
        validator = file_validator.DefinitionStructuralValidator(
            definition=program.definitions[0],
            context=_make_context(tmp_path),
            seen_definitions={},
        )

        result = validator.validate_definition()

        assert isinstance(result, validation_result.DefinitionValidationResult)
        assert result.definition == program.definitions[0]
        assert result.diagnostics == []

    def test_duplicate_definition_result_still_carries_definition(
        self, tmp_path: Path, lark_parser: parser.Parser
    ):
        source = (
            "define the potential position<my.domain.com:my_lib:/test>.\n"
            "define the potential position<my.domain.com:my_lib:/test>.\n"
        )
        program = _parse_program(source, lark_parser)
        seen_definitions: dict[str, ast.QualityDefinition] = {}

        first_result = file_validator.DefinitionStructuralValidator(
            definition=program.definitions[0],
            context=_make_context(tmp_path),
            seen_definitions=seen_definitions,
        ).validate_definition()
        seen_definitions[program.definitions[0].typed_name.source_typed_name] = (
            program.definitions[0]
        )
        second_result = file_validator.DefinitionStructuralValidator(
            definition=program.definitions[1],
            context=_make_context(tmp_path),
            seen_definitions=seen_definitions,
        ).validate_definition()

        assert first_result.definition == program.definitions[0]
        assert first_result.diagnostics == []
        assert second_result.definition == program.definitions[1]
        assert [type(d) for d in second_result.diagnostics] == [
            diagnostics.DuplicateDefinitionDiagnostic,
        ]

    def test_sequential_validation_returns_definition_results(
        self, tmp_path: Path, lark_parser: parser.Parser
    ):
        source = (
            "define the potential position<my.domain.com:my_lib:/test>.\n"
            "define the potential position<my.domain.com:my_lib:/test>.\n"
        )
        program = _parse_program(source, lark_parser)
        seen_definitions: dict[str, ast.QualityDefinition] = {}
        results: list[validation_result.DefinitionValidationResult] = []

        for definition in program.definitions:
            result = file_validator.DefinitionStructuralValidator(
                definition=definition,
                context=_make_context(tmp_path),
                seen_definitions=seen_definitions,
            ).validate_definition()
            results.append(result)
            seen_definitions[definition.typed_name.source_typed_name] = definition

        assert len(results) == 2
        assert all(
            isinstance(result, validation_result.DefinitionValidationResult)
            for result in results
        )
        assert [result.definition for result in results] == list(program.definitions)
        assert results[0].diagnostics == []
        assert [type(d) for d in results[1].diagnostics] == [
            diagnostics.DuplicateDefinitionDiagnostic,
        ]


class TestFileStructuralValidatorReferenceDiscovery:
    def test_short_form_reference(self, tmp_path: Path, lark_parser: parser.Parser):
        source = (
            "define the potential position<my.domain.com:my_lib:/test> {\n"
            "    it may only contain dimension points where {\n"
            "        it has the position</other>.\n"
            "    }\n"
            "}\n"
        )
        (tmp_path / "test.def").write_text(source, encoding="utf-8")
        ctx = _make_context(tmp_path)
        result = file_validator.FileStructuralValidator(lark_parser).validate_file(ctx)

        assert len(_reference_edges(result)) == 1
        assert len(_discovered_files(result)) == 1
        discovered = _discovered_files(result)[0]
        assert discovered.path == PurePosixPath("other.def")
        assert discovered.root_prefix == PurePosixPath(str(tmp_path))
        assert discovered.expected_fqun == "my.domain.com:my_lib"

    def test_cross_universe_reference_configured(
        self, tmp_path: Path, lark_parser: parser.Parser
    ):
        source = (
            "define the potential position<my.domain.com:my_lib:/test> {\n"
            "    it may only contain dimension points where {\n"
            "        it has the position<other.domain.com:other_lib:/dep>.\n"
            "    }\n"
            "}\n"
        )
        (tmp_path / "test.def").write_text(source, encoding="utf-8")
        ctx = _make_context(
            tmp_path,
            sub_root_mappings={
                "other.domain.com:other_lib": PurePosixPath("deps/other")
            },
        )
        result = file_validator.FileStructuralValidator(lark_parser).validate_file(ctx)

        assert len(_reference_edges(result)) == 1
        assert len(_discovered_files(result)) == 1
        discovered = _discovered_files(result)[0]
        assert discovered.path == PurePosixPath("dep.def")
        assert discovered.root_prefix == PurePosixPath(str(tmp_path)) / "deps/other"
        assert discovered.expected_fqun == "other.domain.com:other_lib"

    def test_cross_universe_reference_not_configured(
        self, tmp_path: Path, lark_parser: parser.Parser
    ):
        source = (
            "define the potential position<my.domain.com:my_lib:/test> {\n"
            "    it may only contain dimension points where {\n"
            "        it has the position<other.domain.com:other_lib:/dep>.\n"
            "    }\n"
            "}\n"
        )
        (tmp_path / "test.def").write_text(source, encoding="utf-8")
        ctx = _make_context(tmp_path)
        result = file_validator.FileStructuralValidator(lark_parser).validate_file(ctx)

        assert [type(d) for d in result.diagnostics] == [
            diagnostics.ExternalUniverseNotConfiguredDiagnostic,
        ]
        assert _reference_edges(result) == []
        assert _discovered_files(result) == []

    def test_multiple_references(self, tmp_path: Path, lark_parser: parser.Parser):
        source = (
            "define the potential position<my.domain.com:my_lib:/test> {\n"
            "    it may only contain dimension points where {\n"
            "        it has the position</dep_a>.\n"
            "        it has the position</dep_b>.\n"
            "    }\n"
            "}\n"
        )
        (tmp_path / "test.def").write_text(source, encoding="utf-8")
        ctx = _make_context(tmp_path)
        result = file_validator.FileStructuralValidator(lark_parser).validate_file(ctx)

        assert len(_reference_edges(result)) == 2
        assert len(_discovered_files(result)) == 2


class TestDimensionPointReferenceEdges:
    def test_chained_globals_produce_multiple_edges(
        self, tmp_path: Path, lark_parser: parser.Parser
    ):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<gateway> {\n"
            "        it may only contain dimension points where {\n"
            "            it has the action</beta>.\n"
            "        }\n"
            "    }\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in position<gateway>::action</beta>::position</gamma>.\n"
            "    }\n"
            "}\n"
        )
        (tmp_path / "test.def").write_text(source, encoding="utf-8")
        ctx = _make_context(tmp_path)
        result = file_validator.FileStructuralValidator(lark_parser).validate_file(ctx)

        assert result.diagnostics == []
        assert len(_reference_edges(result)) == 3
        assert len(_discovered_files(result)) == 3

    def test_local_names_produce_no_edges(
        self, tmp_path: Path, lark_parser: parser.Parser
    ):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<run>.\n"
            "    define the position<inner_pos>.\n"
            "    it happens when {\n"
            "        the position<run> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in position<inner_pos>.\n"
            "    }\n"
            "}\n"
        )
        (tmp_path / "test.def").write_text(source, encoding="utf-8")
        ctx = _make_context(tmp_path)
        result = file_validator.FileStructuralValidator(lark_parser).validate_file(ctx)

        assert result.diagnostics == []
        assert _reference_edges(result) == []
        assert _discovered_files(result) == []

    def test_invalid_global_name_produces_no_edges(
        self, tmp_path: Path, lark_parser: parser.Parser
    ):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<my_pos> {\n"
            "        it may only contain dimension points where {\n"
            "            it has the position</Bad>.\n"
            "        }\n"
            "    }\n"
            "    it happens when {\n"
            "        the position<my_pos> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in position<my_pos>::position</Bad>.\n"
            "    }\n"
            "}\n"
        )
        (tmp_path / "test.def").write_text(source, encoding="utf-8")
        ctx = _make_context(tmp_path)
        result = file_validator.FileStructuralValidator(lark_parser).validate_file(ctx)

        assert len(result.diagnostics) == 2
        assert isinstance(
            result.diagnostics[0],
            diagnostics.InvalidGlobalNamePathCharacterDiagnostic,
        )
        assert result.diagnostics[0].segment == "Bad"
        assert result.diagnostics[0].char == "B"
        assert result.diagnostics[0].location.line == 4
        assert result.diagnostics[0].location.column == 34
        assert isinstance(
            result.diagnostics[1],
            diagnostics.InvalidGlobalNamePathCharacterDiagnostic,
        )
        assert result.diagnostics[1].segment == "Bad"
        assert result.diagnostics[1].char == "B"
        assert result.diagnostics[1].location.line == 10
        assert result.diagnostics[1].location.column == 65
        assert _reference_edges(result) == []
        assert _discovered_files(result) == []


class TestFileStructuralValidatorTimingStats:
    def test_stats_populated(self, tmp_path: Path, lark_parser: parser.Parser):
        source = "define the potential position<my.domain.com:my_lib:/test>.\n"
        (tmp_path / "test.def").write_text(source, encoding="utf-8")
        ctx = _make_context(tmp_path)
        result = file_validator.FileStructuralValidator(lark_parser).validate_file(ctx)

        assert result.stats.overall_compile > 0
        assert result.stats.file_loading > 0
        assert result.stats.parse > 0
        assert result.stats.transform > 0
        assert result.stats.file_validation > 0
