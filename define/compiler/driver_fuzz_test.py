# pyright: reportUnusedCallResult=false
"""Fuzz tests for the Define compiler driver."""

import io
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from lark import exceptions as lark_exceptions

from define.compiler import driver, exceptions, parser_exceptions

_MULTIVERSE_NAMES = ["mv", "standard", "mymv", "test_mv"]
_AUTHORITY_DOMAINS = ["example.com", "define-lang.org", "test.io", "my.domain.co"]
_UNIVERSE_NAMES = ["my_lib", "core", "fuzz_test", "std"]
_PATH_SEGMENTS = ["path", "hello", "sub", "dir", "leaf", "foo", "bar"]
_LOCAL_NAMES = ["x", "my_pos", "local", "inner"]


def _escape_content(text: str) -> str:
    """Escape invisible and control characters, preserving spaces."""
    chars: list[str] = []
    for c in text:
        if c == " " or (c.isprintable() and c != "\n"):
            chars.append(c)
        else:
            chars.append(repr(c)[1:-1])
    return "".join(chars)


def _check_error_stream(error_output: str, *, expect_content: bool) -> None:
    if expect_content:
        assert error_output.strip(), "Error exit code but error stream is empty"
    else:
        assert not error_output, (
            "Success exit code but error stream is not empty: "
            + _escape_content(error_output)
        )
    for i, c in enumerate(error_output):
        if c == "\n" or c == "\t":
            continue
        if not c.isprintable():
            raise AssertionError(
                f"Non-printable character {c!r} at position {i} in error output: "
                + _escape_content(error_output)
            )


@st.composite
def fquns(draw: st.DrawFn) -> str:
    fmt = draw(st.sampled_from(["2part", "3part", "4part"]))
    universe = draw(st.sampled_from(_UNIVERSE_NAMES))
    if fmt == "2part":
        return f"{universe}:"
    authority = draw(st.sampled_from(_AUTHORITY_DOMAINS))
    num_auth_segments = draw(st.integers(min_value=0, max_value=2))
    auth_path = ""
    for _ in range(num_auth_segments):
        seg = draw(st.sampled_from(_PATH_SEGMENTS))
        auth_path += f"/{seg}"
    if fmt == "3part":
        return f"{authority}{auth_path}:{universe}:"
    multiverse = draw(st.sampled_from(_MULTIVERSE_NAMES))
    return f"{multiverse}:{authority}{auth_path}:{universe}:"


_PROJECT_FQUN = "mv:define-lang.org:fuzz_test:"


@st.composite
def global_names(draw: st.DrawFn) -> str:
    fqun = draw(fquns())
    num_segments = draw(st.integers(min_value=1, max_value=3))
    path = ""
    for _ in range(num_segments):
        seg = draw(st.sampled_from(_PATH_SEGMENTS))
        path += f"/{seg}"
    return f"{fqun}{path}"


@st.composite
def position_definitions(draw: st.DrawFn) -> str:
    name = draw(global_names())
    definition_kind = draw(st.sampled_from(["position_simple", "position"]))
    if definition_kind == "position_simple":
        return f"define the potential position<{name}>.\n"
    child_name = draw(global_names())
    child_type = draw(st.sampled_from(["position", "action"]))
    return (
        f"define the potential position<{name}> {{\n"
        f"it may only contain dimension points where {{\n"
        f"it has the {child_type}<{child_name}>.\n"
        f"}}\n"
        f"}}\n"
    )


@st.composite
def action_definitions_simple(draw: st.DrawFn) -> str:
    name = draw(global_names())
    return f"define the potential action<{name}>.\n"


@st.composite
def action_definitions_with_block(draw: st.DrawFn) -> str:
    name = draw(global_names())
    num_local_defs = draw(st.integers(min_value=0, max_value=2))
    local_defs_outer = ""
    local_defs_inner = ""
    for _ in range(num_local_defs):
        local_name = draw(st.sampled_from(_LOCAL_NAMES))
        local_defs_outer += f"define the position<{local_name}>.\n"
        local_defs_inner += f"define the position<{local_name}>.\n"
    return (
        f"define the potential action<{name}> {{\n"
        f"{local_defs_outer}"
        f"it happens when {{\n"
        f"}} and it does {{\n"
        f"{local_defs_inner}"
        f"}}\n"
        f"}}\n"
    )


_VALID_NAME = f"{_PROJECT_FQUN}/test"


@st.composite
def valid_sources(draw: st.DrawFn) -> str:
    kind = draw(
        st.sampled_from(
            [
                "position_simple",
                "position",
                "action_simple",
                "action",
                "action_outer_local",
                "action_inner_local",
                "action_multiple_locals",
                "action_outer_and_inner_positions",
                "action_no_indentation",
                "action_with_blank_lines",
                "comments",
                "action_and_position_same_file",
            ]
        )
    )
    if kind == "position_simple":
        return f"define the potential position<{_VALID_NAME}>.\n"
    if kind == "position":
        return (
            f"define the potential position<{_VALID_NAME}> {{\n"
            f"it may only contain dimension points where {{\n"
            f"it has the position</another_test>.\n"
            f"}}\n"
            f"}}\n"
        )
    if kind == "action_simple":
        return f"define the potential action<{_VALID_NAME}>.\n"
    if kind == "action":
        return (
            f"define the potential action<{_VALID_NAME}> {{\n"
            f"it happens when {{\n"
            f"}} and it does {{\n"
            f"}}\n"
            f"}}\n"
        )
    if kind == "action_outer_local":
        return (
            f"define the potential action<{_VALID_NAME}> {{\n"
            f"define the position<x>.\n"
            f"it happens when {{\n"
            f"}} and it does {{\n"
            f"}}\n"
            f"}}\n"
        )
    if kind == "action_inner_local":
        return (
            f"define the potential action<{_VALID_NAME}> {{\n"
            f"it happens when {{\n"
            f"}} and it does {{\n"
            f"define the position<x>.\n"
            f"}}\n"
            f"}}\n"
        )
    if kind == "action_multiple_locals":
        return (
            f"define the potential action<{_VALID_NAME}> {{\n"
            f"define the position<x>.\n"
            f"define the position<my_pos>.\n"
            f"it happens when {{\n"
            f"}} and it does {{\n"
            f"}}\n"
            f"}}\n"
        )
    if kind == "action_outer_and_inner_positions":
        return (
            f"define the potential action<{_VALID_NAME}> {{\n"
            f"define the position<x>.\n"
            f"it happens when {{\n"
            f"}} and it does {{\n"
            f"define the position<my_pos>.\n"
            f"}}\n"
            f"}}\n"
        )
    if kind == "action_no_indentation":
        return (
            f"define the potential action<{_VALID_NAME}> {{\n"
            f"it happens when {{\n"
            f"}} and it does {{\n"
            f"}}\n"
            f"}}\n"
        )
    if kind == "action_with_blank_lines":
        return (
            f"define the potential action<{_VALID_NAME}> {{\n"
            f"it happens when {{\n"
            f"\n"
            f"}} and it does {{\n"
            f"\n"
            f"}}\n"
            f"}}\n"
        )
    if kind == "comments":
        return (
            "# comment\n"
            + f"define the potential position<{_VALID_NAME}>. # inline comment\n"
        )
    return (
        f"define the potential position<{_VALID_NAME}>.\n"
        + f"define the potential action<{_VALID_NAME}>.\n"
    )


@st.composite
def syntactic_sources(draw: st.DrawFn) -> str:
    """Generate syntactically valid sources with random names (for mutations)."""
    num_defs = draw(st.integers(min_value=1, max_value=3))
    defs: list[str] = []
    for _ in range(num_defs):
        kind = draw(
            st.sampled_from(["position_simple", "position", "action_simple", "action"])
        )
        if kind in ["position_simple", "position"]:
            defs.append(draw(position_definitions()))
        elif kind == "action_simple":
            defs.append(draw(action_definitions_simple()))
        else:
            defs.append(draw(action_definitions_with_block()))
    return "".join(defs)


_MUTATIONS = [
    "delete_char",
    "insert_char",
    "replace_char",
    "delete_keyword",
    "swap_adjacent",
    "remove_newline",
    "remove_angle_bracket",
    "remove_structural_char",
    "insert_unicode",
]


@st.composite
def mutated_sources(draw: st.DrawFn) -> str:
    source = draw(syntactic_sources())
    mutation = draw(st.sampled_from(_MUTATIONS))

    if mutation == "delete_char" and len(source) > 1:
        idx = draw(st.integers(min_value=0, max_value=len(source) - 1))
        return source[:idx] + source[idx + 1 :]

    if mutation == "insert_char":
        idx = draw(st.integers(min_value=0, max_value=len(source)))
        char = draw(st.sampled_from(list("abcdef01234 \t\n<>{}.:/#")))
        return source[:idx] + char + source[idx:]

    if mutation == "replace_char" and len(source) > 0:
        idx = draw(st.integers(min_value=0, max_value=len(source) - 1))
        char = draw(st.sampled_from(list("abcdef01234 \t\n<>{}.:/#")))
        return source[:idx] + char + source[idx + 1 :]

    if mutation == "delete_keyword":
        keywords = ["define", "the", "potential", "position", "action"]
        keyword = draw(st.sampled_from(keywords))
        if keyword in source:
            idx = source.index(keyword)
            return source[:idx] + source[idx + len(keyword) :]

    if mutation == "swap_adjacent" and len(source) > 1:
        idx = draw(st.integers(min_value=0, max_value=len(source) - 2))
        return source[:idx] + source[idx + 1] + source[idx] + source[idx + 2 :]

    if mutation == "remove_newline" and "\n" in source:
        idx = source.index("\n")
        return source[:idx] + source[idx + 1 :]

    if mutation == "remove_angle_bracket":
        for bracket in ["<", ">"]:
            if bracket in source:
                idx = source.index(bracket)
                return source[:idx] + source[idx + 1 :]

    if mutation == "remove_structural_char":
        for char in [":", ".", "{", "}"]:
            if char in source:
                idx = source.index(char)
                return source[:idx] + source[idx + 1 :]

    if mutation == "insert_unicode":
        idx = draw(st.integers(min_value=0, max_value=len(source)))
        char = draw(st.sampled_from(["\u00e9", "\u00f1", "\u4e16", "\U0001f600"]))
        return source[:idx] + char + source[idx:]

    return source


@pytest.fixture
def fuzz_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_dir = tmp_path / ".define" / "project"
    config_dir.mkdir(parents=True)
    (config_dir / "config.defcl").write_text(
        'project: {\n  universe_name: "mv:define-lang.org:fuzz_test"\n}\n'
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


@settings(
    deadline=None,
    database=None,
    max_examples=200,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(source=valid_sources())
def test_valid_syntax_runs(fuzz_project: Path, source: str):
    file_path = fuzz_project / "test.def"
    file_path.write_text(source, encoding="utf-8")
    d = driver.Driver()
    error_stream = io.StringIO()
    result = d.run(Path("test.def"), error_stream=error_stream)
    _check_error_stream(error_stream.getvalue(), expect_content=False)
    assert result == driver.ExitCode.SUCCESS, (
        f"run() returned {result} for {file_path}: {_escape_content(source)}"
    )


@settings(
    deadline=None,
    database=None,
    max_examples=500,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(source=mutated_sources())
def test_mutated_syntax_no_unclassified_errors(fuzz_project: Path, source: str):
    file_path = fuzz_project / "test.def"
    file_path.write_text(source, encoding="utf-8")
    d = driver.Driver()
    try:
        d.validate_file(Path("test.def"))
    except (parser_exceptions.DefineSyntaxError, exceptions.DriverError):
        pass
    except lark_exceptions.UnexpectedInput:
        pytest.fail(
            f"Unclassified lark error for {file_path}: {_escape_content(source)}"
        )


@settings(
    deadline=None,
    database=None,
    max_examples=500,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(source=mutated_sources())
def test_mutated_syntax_never_crashes(fuzz_project: Path, source: str):
    file_path = fuzz_project / "test.def"
    file_path.write_text(source, encoding="utf-8")
    d = driver.Driver()
    error_stream = io.StringIO()
    result = d.run(Path("test.def"), error_stream=error_stream)
    error_output = error_stream.getvalue()
    assert isinstance(result, driver.ExitCode), (
        f"run() did not return ExitCode for {file_path}: {_escape_content(source)}"
    )
    _check_error_stream(error_output, expect_content=result == driver.ExitCode.ERROR)


@settings(
    deadline=None,
    database=None,
    max_examples=100,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(data=st.binary(max_size=500))
def test_random_bytes_never_crash(fuzz_project: Path, data: bytes):
    file_path = fuzz_project / "test.def"
    file_path.write_bytes(data)
    d = driver.Driver()
    error_stream = io.StringIO()
    result = d.run(Path("test.def"), error_stream=error_stream)
    _check_error_stream(error_stream.getvalue(), expect_content=True)
    assert result == driver.ExitCode.ERROR, (
        f"run() returned {result} for {file_path}: {data!r}"
    )
