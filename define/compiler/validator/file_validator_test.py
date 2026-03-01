# pyright: reportUnusedCallResult=false
# NOTE: Tests for new syntax or diagnostics belong in program_validator_tests/,
# not here. This file tests FileValidator internals only (edges, discovered
# files, timing stats, error handling).

import types
from pathlib import Path, PurePosixPath

import pytest

from define.compiler import diagnostics, exceptions, parser
from define.compiler.validator import file_validator


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


class TestFileValidatorSuccess:
    def test_valid_position(self, tmp_path: Path, lark_parser: parser.Parser):
        source = "define the potential position<my.domain.com:my_lib:/test>.\n"
        (tmp_path / "test.def").write_text(source, encoding="utf-8")
        ctx = _make_context(tmp_path)
        result = file_validator.FileValidator(lark_parser).validate_file(ctx)

        assert result.exception is None
        assert result.diagnostics == []
        assert result.source == source
        assert len(result.definitions) == 1
        assert result.definitions[0].typed_name.name_type == "position"

    def test_valid_action(self, tmp_path: Path, lark_parser: parser.Parser):
        source = "define the potential action<my.domain.com:my_lib:/test>.\n"
        (tmp_path / "test.def").write_text(source, encoding="utf-8")
        ctx = _make_context(tmp_path)
        result = file_validator.FileValidator(lark_parser).validate_file(ctx)

        assert result.exception is None
        assert result.diagnostics == []
        assert len(result.definitions) == 1
        assert result.definitions[0].typed_name.name_type == "action"


class TestFileValidatorErrors:
    def test_file_not_found(self, tmp_path: Path, lark_parser: parser.Parser):
        ctx = _make_context(tmp_path, file_name="nonexistent.def")
        result = file_validator.FileValidator(lark_parser).validate_file(ctx)

        assert isinstance(result.exception, exceptions.SourceFileNotFoundError)
        assert result.definitions == []
        assert result.reference_edges == []
        assert result.discovered_files == []

    def test_syntax_error(self, tmp_path: Path, lark_parser: parser.Parser):
        (tmp_path / "test.def").write_text(
            "not valid define syntax\n", encoding="utf-8"
        )
        ctx = _make_context(tmp_path)
        result = file_validator.FileValidator(lark_parser).validate_file(ctx)

        assert result.exception is not None
        assert result.definitions == []

    def test_encoding_error(self, tmp_path: Path, lark_parser: parser.Parser):
        (tmp_path / "test.def").write_bytes(b"\x80\x81\x82")
        ctx = _make_context(tmp_path)
        result = file_validator.FileValidator(lark_parser).validate_file(ctx)

        assert result.exception is not None


class TestFileValidatorDiagnostics:
    def test_path_mismatch(self, tmp_path: Path, lark_parser: parser.Parser):
        source = "define the potential position<my.domain.com:my_lib:/wrong_path>.\n"
        (tmp_path / "test.def").write_text(source, encoding="utf-8")
        ctx = _make_context(tmp_path)
        result = file_validator.FileValidator(lark_parser).validate_file(ctx)

        assert [type(d) for d in result.diagnostics] == [
            diagnostics.PathMismatchDiagnostic,
        ]

    def test_fqun_mismatch(self, tmp_path: Path, lark_parser: parser.Parser):
        source = "define the potential position<other.domain.com:other_lib:/test>.\n"
        (tmp_path / "test.def").write_text(source, encoding="utf-8")
        ctx = _make_context(tmp_path)
        result = file_validator.FileValidator(lark_parser).validate_file(ctx)

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
        result = file_validator.FileValidator(lark_parser).validate_file(ctx)

        assert [type(d) for d in result.diagnostics] == [
            diagnostics.DuplicateDefinitionDiagnostic,
        ]


class TestFileValidatorReferenceDiscovery:
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
        result = file_validator.FileValidator(lark_parser).validate_file(ctx)

        assert len(result.reference_edges) == 1
        assert len(result.discovered_files) == 1
        discovered = result.discovered_files[0]
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
        result = file_validator.FileValidator(lark_parser).validate_file(ctx)

        assert len(result.reference_edges) == 1
        assert len(result.discovered_files) == 1
        discovered = result.discovered_files[0]
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
        result = file_validator.FileValidator(lark_parser).validate_file(ctx)

        assert [type(d) for d in result.diagnostics] == [
            diagnostics.ExternalUniverseNotConfiguredDiagnostic,
        ]
        assert result.reference_edges == []
        assert result.discovered_files == []

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
        result = file_validator.FileValidator(lark_parser).validate_file(ctx)

        assert len(result.reference_edges) == 2
        assert len(result.discovered_files) == 2


class TestDimensionPointReferenceEdges:
    def test_chained_globals_produce_multiple_edges(
        self, tmp_path: Path, lark_parser: parser.Parser
    ):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    it happens when {\n"
            "    } and it does {\n"
            "        create a dimension point in position</alpha>::action</beta>::position</gamma>.\n"
            "    }\n"
            "}\n"
        )
        (tmp_path / "test.def").write_text(source, encoding="utf-8")
        ctx = _make_context(tmp_path)
        result = file_validator.FileValidator(lark_parser).validate_file(ctx)

        assert result.diagnostics == []
        assert len(result.reference_edges) == 3
        assert len(result.discovered_files) == 3

    def test_local_names_produce_no_edges(
        self, tmp_path: Path, lark_parser: parser.Parser
    ):
        source = (
            "define the potential action<my.domain.com:my_lib:/test> {\n"
            "    define the position<inner_pos>.\n"
            "    it happens when {\n"
            "    } and it does {\n"
            "        create a dimension point in position<inner_pos>.\n"
            "    }\n"
            "}\n"
        )
        (tmp_path / "test.def").write_text(source, encoding="utf-8")
        ctx = _make_context(tmp_path)
        result = file_validator.FileValidator(lark_parser).validate_file(ctx)

        assert result.diagnostics == []
        assert result.reference_edges == []
        assert result.discovered_files == []

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
            "    } and it does {\n"
            "        create a dimension point in position<my_pos>::position</Bad>.\n"
            "    }\n"
            "}\n"
        )
        (tmp_path / "test.def").write_text(source, encoding="utf-8")
        ctx = _make_context(tmp_path)
        result = file_validator.FileValidator(lark_parser).validate_file(ctx)

        assert len(result.diagnostics) == 2
        assert isinstance(
            result.diagnostics[0],
            diagnostics.InvalidGlobalNamePathCharacterDiagnostic,
        )
        assert result.diagnostics[0].segment == "Bad"
        assert result.diagnostics[0].char == "B"
        assert result.diagnostics[0].position.line == 4
        assert result.diagnostics[0].position.column == 34
        assert isinstance(
            result.diagnostics[1],
            diagnostics.InvalidGlobalNamePathCharacterDiagnostic,
        )
        assert result.diagnostics[1].segment == "Bad"
        assert result.diagnostics[1].char == "B"
        assert result.diagnostics[1].position.line == 9
        assert result.diagnostics[1].position.column == 65
        assert result.reference_edges == []
        assert result.discovered_files == []


class TestFileValidatorTimingStats:
    def test_stats_populated(self, tmp_path: Path, lark_parser: parser.Parser):
        source = "define the potential position<my.domain.com:my_lib:/test>.\n"
        (tmp_path / "test.def").write_text(source, encoding="utf-8")
        ctx = _make_context(tmp_path)
        result = file_validator.FileValidator(lark_parser).validate_file(ctx)

        assert result.stats.overall_compile > 0
        assert result.stats.file_loading > 0
        assert result.stats.parse > 0
        assert result.stats.transform > 0
        assert result.stats.file_validation > 0
