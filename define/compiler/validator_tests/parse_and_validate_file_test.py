# pyright: reportUnusedCallResult=false
from pathlib import PurePosixPath

from define.compiler import parser_exceptions
from define.compiler.validator_tests.conftest import ParseAndValidateFile


def test_returns_single_file_timing_stats(
    parse_and_validate_file: ParseAndValidateFile,
):
    source = "define the potential position<my.domain.com:my_lib:/test>.\n"
    result = parse_and_validate_file(source)

    assert result.diagnostics == []
    assert result.exception is None
    assert result.source == source
    assert result.file_path == PurePosixPath("test.def")

    timings = result.stats
    assert timings.overall >= 0
    assert timings.parse >= 0
    assert timings.transform is not None
    assert timings.validate is not None
    assert timings.transform >= 0
    assert timings.validate >= 0
    assert timings.parse < timings.overall
    assert timings.transform < timings.overall
    assert timings.validate < timings.overall
    assert timings.overall == (timings.parse + timings.transform + timings.validate)


def test_parse_error_populates_exceptions_and_sets_later_phases_to_none(
    parse_and_validate_file: ParseAndValidateFile,
):
    result = parse_and_validate_file(
        "defin the potential position<my.domain.com:my_lib:/bad>.\n"
    )

    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.DefineSyntaxError)
    assert result.source is not None
    assert result.file_path == PurePosixPath("test.def")

    timings = result.stats
    assert timings.overall >= 0
    assert timings.parse >= 0
    assert timings.transform is None
    assert timings.validate is None
    assert timings.overall == timings.parse


def test_invalid_utf8_populates_exceptions_and_source_is_none(
    parse_and_validate_file: ParseAndValidateFile,
):
    result = parse_and_validate_file(
        b"define the potential position<my.domain.com:my_lib:/bad>.\n\xff"
    )

    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.InvalidEncodingError)
    assert result.source is None
    assert result.file_path == PurePosixPath("test.def")

    timings = result.stats
    assert timings.overall >= 0
    assert timings.parse >= 0
    assert timings.transform is None
    assert timings.validate is None
    assert timings.overall == timings.parse


def test_transform_error_from_name_parser_populates_exceptions(
    parse_and_validate_file: ParseAndValidateFile,
):
    source = (
        "define the potential position<"
        + "mv:define-lang.org:test:files:/invalid/syntax/fqun_format/too_many_colons"
        + ">.\n"
    )
    result = parse_and_validate_file(source)

    assert result.diagnostics == []
    assert isinstance(result.exception, parser_exceptions.GlobalNameInvalidFqunFormat)
    assert result.source == source
    assert result.file_path == PurePosixPath("test.def")

    timings = result.stats
    assert timings.overall >= 0
    assert timings.parse >= 0
    assert timings.transform is not None
    assert timings.transform >= 0
    assert timings.validate is None
    assert timings.overall == (timings.parse + timings.transform)
