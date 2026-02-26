# pyright: reportUnusedCallResult=false
"""Fuzz tests for the Define compiler driver."""

import io
import shutil
from dataclasses import dataclass, replace
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from define.compiler import driver, exceptions, parser_exceptions, validation_result

_MULTIVERSE_NAMES = ["mv", "standard", "mymv", "test_mv"]
_AUTHORITY_DOMAINS = ["example.com", "define-lang.org", "test.io", "my.domain.co"]
_UNIVERSE_NAMES = ["my_lib", "core", "fuzz_test", "std"]
_PATH_SEGMENTS = ["path", "hello", "sub", "dir", "leaf", "foo", "bar"]
_LOCAL_NAMES = ["x", "my_pos", "local", "inner", "_tmp", "pos2", "node_1"]
_VALID_ROOT_UNIVERSES = [
    "mv:define-lang.org:fuzz_test",
    "mv:define-lang.org:fuzz_root",
    "mv:define-lang.org:fuzz_world",
]
_VALID_CHILD_UNIVERSES = [
    "mv:define-lang.org:fuzz_sub",
    "mv:define-lang.org:fuzz_child",
    "mv:define-lang.org:fuzz_dep",
]
_VALID_GRANDCHILD_UNIVERSES = [
    "mv:define-lang.org:fuzz_grandchild",
    "mv:define-lang.org:fuzz_leafroot",
]
_EXAMPLES_VALID_SINGLE = 180
_EXAMPLES_VALID_PROJECTS = 120
_EXAMPLES_MUTATED_SINGLE = 240
_EXAMPLES_MUTATED_PROJECTS = 120
_EXAMPLES_RANDOM_BYTES = 120


def _escape_content(text: str) -> str:
    """Escape invisible and control characters, preserving spaces."""
    chars: list[str] = []
    for c in text:
        if c == " " or c.isprintable():
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


def _definition_path(rel_def_file: str) -> str:
    return "/" + Path(rel_def_file).with_suffix("").as_posix()


def _global_name(universe_name: str, rel_def_file: str) -> str:
    return f"{universe_name}:{_definition_path(rel_def_file)}"


def _join_lines(lines: list[str]) -> str:
    return "\n".join(lines) + "\n"


def _position_simple(universe_name: str, rel_def_file: str) -> str:
    return (
        f"define the potential position<{_global_name(universe_name, rel_def_file)}>.\n"
    )


def _action_simple(universe_name: str, rel_def_file: str) -> str:
    return (
        f"define the potential action<{_global_name(universe_name, rel_def_file)}>.\n"
    )


def _position_with_requirements(
    universe_name: str,
    rel_def_file: str,
    requirements: list[tuple[str, str]],
    *,
    indent: str = "    ",
) -> str:
    lines = [
        f"define the potential position<{_global_name(universe_name, rel_def_file)}> {{",
        f"{indent}it may only contain dimension points where {{",
    ]
    for req_type, req_name in requirements:
        lines.append(f"{indent * 2}it has the {req_type}<{req_name}>.")
    lines.extend(
        [
            f"{indent}}}",
            "}",
        ]
    )
    return _join_lines(lines)


def _local_position_simple(name: str, *, indent: str) -> str:
    return f"{indent}define the position<{name}>.\n"


def _local_position_with_requirements(
    name: str,
    requirements: list[tuple[str, str]],
    *,
    indent: str,
) -> str:
    lines = [
        f"{indent}define the position<{name}> {{",
        f"{indent}    it may only contain dimension points where {{",
    ]
    for req_type, req_name in requirements:
        lines.append(f"{indent}        it has the {req_type}<{req_name}>.")
    lines.extend(
        [
            f"{indent}    }}",
            f"{indent}}}",
        ]
    )
    return _join_lines(lines)


def _action_block_with_name(
    action_name: str,
    *,
    outer_locals: list[str],
    inner_locals: list[str],
    indent: str = "    ",
    include_trigger_comment: bool = False,
    include_action_close_comment: bool = False,
    blank_lines_in_blocks: bool = False,
) -> str:
    lines = [f"define the potential action<{action_name}> {{"]
    for local in outer_locals:
        lines.extend(local.rstrip("\n").splitlines())

    trigger_line = f"{indent}it happens when {{"
    if include_trigger_comment:
        trigger_line += " # trigger comment"
    lines.append(trigger_line)
    if blank_lines_in_blocks:
        lines.append("")
    action_open = f"{indent}}} and it does {{"
    lines.append(action_open)
    if blank_lines_in_blocks:
        lines.append("")
    for local in inner_locals:
        lines.extend(local.rstrip("\n").splitlines())
    action_close = f"{indent}}}"
    if include_action_close_comment:
        action_close += " # action close comment"
    lines.append(action_close)
    lines.append("}")
    return _join_lines(lines)


def _action_with_block(
    universe_name: str,
    rel_def_file: str,
    *,
    outer_locals: list[str],
    inner_locals: list[str],
    indent: str = "    ",
    include_trigger_comment: bool = False,
    include_action_close_comment: bool = False,
    blank_lines_in_blocks: bool = False,
) -> str:
    return _action_block_with_name(
        _global_name(universe_name, rel_def_file),
        outer_locals=outer_locals,
        inner_locals=inner_locals,
        indent=indent,
        include_trigger_comment=include_trigger_comment,
        include_action_close_comment=include_action_close_comment,
        blank_lines_in_blocks=blank_lines_in_blocks,
    )


def _setup_project(
    root: Path,
    universe_name: str,
    local_deps: dict[str, str] | None = None,
) -> None:
    config_dir = root / ".define" / "project"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.defcl").write_text(
        f'project: {{\n  universe_name: "{universe_name}"\n}}\n',
        encoding="utf-8",
    )
    if local_deps is None:
        return
    deps_dir = root / ".define" / "deps"
    deps_dir.mkdir(parents=True, exist_ok=True)
    entries = ",\n    ".join(
        f'{{\n      universe_name: "{name}"\n      path: "{path}"\n    }}'
        for name, path in local_deps.items()
    )
    content = (
        f"deps: {{\n  local: [\n    {entries}\n  ]\n}}\n"
        if local_deps
        else "deps: {}\n"
    )
    (deps_dir / "local.defcl").write_text(content, encoding="utf-8")


def _write_files(root: Path, files: dict[str, str]) -> None:
    for rel_path, source in files.items():
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")


def _reset_tmp_path(tmp_path: Path) -> None:
    for entry in tmp_path.iterdir():
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()


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


@st.composite
def long_global_names(draw: st.DrawFn) -> str:
    fqun = draw(fquns())
    num_segments = draw(st.integers(min_value=1, max_value=3))
    path = ""
    for _ in range(num_segments):
        seg = draw(st.sampled_from(_PATH_SEGMENTS))
        path += f"/{seg}"
    return f"{fqun}{path}"


@st.composite
def short_global_names(draw: st.DrawFn) -> str:
    num_segments = draw(st.integers(min_value=1, max_value=3))
    path = ""
    for _ in range(num_segments):
        seg = draw(st.sampled_from(_PATH_SEGMENTS))
        path += f"/{seg}"
    return path


@st.composite
def global_names(draw: st.DrawFn) -> str:
    return draw(st.one_of(short_global_names(), long_global_names()))


@st.composite
def position_definitions(draw: st.DrawFn) -> str:
    name = draw(global_names())
    definition_kind = draw(st.sampled_from(["position_simple", "position"]))
    if definition_kind == "position_simple":
        return f"define the potential position<{name}>.\n"
    num_requirements = draw(st.integers(min_value=1, max_value=3))
    requirements: list[tuple[str, str]] = []
    for _ in range(num_requirements):
        child_name = draw(global_names())
        child_type = draw(st.sampled_from(["position", "action"]))
        requirements.append((child_type, child_name))
    lines = [
        f"define the potential position<{name}> {{",
        "it may only contain dimension points where {",
    ]
    for child_type, child_name in requirements:
        lines.append(f"it has the {child_type}<{child_name}>.")
    lines.extend(["}", "}"])
    return _join_lines(lines)


@st.composite
def action_definitions_simple(draw: st.DrawFn) -> str:
    name = draw(global_names())
    return f"define the potential action<{name}>.\n"


@st.composite
def action_definitions_with_block(draw: st.DrawFn) -> str:
    name = draw(global_names())
    indent = draw(st.sampled_from(["", "    "]))
    include_trigger_comment = draw(st.booleans())
    include_action_close_comment = draw(st.booleans())
    blank_lines_in_blocks = draw(st.booleans())
    all_local_names = draw(
        st.lists(
            st.sampled_from(_LOCAL_NAMES),
            min_size=0,
            max_size=4,
            unique=True,
        )
    )
    split_idx = draw(st.integers(min_value=0, max_value=len(all_local_names)))
    outer_names = all_local_names[:split_idx]
    inner_names = all_local_names[split_idx:]
    outer_locals: list[str] = []
    inner_locals: list[str] = []
    for local_name in outer_names:
        if draw(st.booleans()):
            outer_locals.append(_local_position_simple(local_name, indent=indent))
        else:
            req_type = draw(st.sampled_from(["position", "action"]))
            req_name = draw(global_names())
            outer_locals.append(
                _local_position_with_requirements(
                    local_name,
                    [(req_type, req_name)],
                    indent=indent,
                )
            )
    for local_name in inner_names:
        if draw(st.booleans()):
            inner_locals.append(_local_position_simple(local_name, indent=indent))
        else:
            req_type = draw(st.sampled_from(["position", "action"]))
            req_name = draw(global_names())
            inner_locals.append(
                _local_position_with_requirements(
                    local_name,
                    [(req_type, req_name)],
                    indent=indent,
                )
            )
    return _action_block_with_name(
        name,
        outer_locals=outer_locals,
        inner_locals=inner_locals,
        indent=indent,
        include_trigger_comment=include_trigger_comment,
        include_action_close_comment=include_action_close_comment,
        blank_lines_in_blocks=blank_lines_in_blocks,
    )


_PROJECT_FQUN = "mv:define-lang.org:fuzz_test"
_VALID_NAME = f"{_PROJECT_FQUN}:/test"
_ANOTHER_VALID_PATH = "/another_test"


def _valid_reference_options() -> st.SearchStrategy[list[tuple[str, str]]]:
    return st.lists(
        st.tuples(
            st.sampled_from(["position", "action"]),
            st.sampled_from([_ANOTHER_VALID_PATH]),
        ),
        min_size=1,
        max_size=3,
    )


def _valid_local_definition_strategy(
    local_name: str, indent: str
) -> st.SearchStrategy[str]:
    return st.one_of(
        st.just(_local_position_simple(local_name, indent=indent)),
        _valid_reference_options().map(
            lambda reqs: _local_position_with_requirements(
                local_name, reqs, indent=indent
            )
        ),
    )


@st.composite
def valid_sources(draw: st.DrawFn) -> str:
    include_position = draw(st.booleans())
    include_action = draw(st.booleans())
    if not include_position and not include_action:
        include_position = True

    fragments: list[str] = []
    if include_position:
        position_kind = draw(st.sampled_from(["simple", "constrained"]))
        if position_kind == "simple":
            fragments.append(f"define the potential position<{_VALID_NAME}>.\n")
        else:
            requirements = draw(_valid_reference_options())
            fragments.append(
                _position_with_requirements(
                    _PROJECT_FQUN,
                    "test.def",
                    requirements,
                )
            )

    if include_action:
        action_kind = draw(st.sampled_from(["simple", "block"]))
        if action_kind == "simple":
            fragments.append(f"define the potential action<{_VALID_NAME}>.\n")
        else:
            indent = draw(st.sampled_from(["", "    "]))
            include_trigger_comment = draw(st.booleans())
            include_action_close_comment = draw(st.booleans())
            blank_lines_in_blocks = draw(st.booleans())
            local_names = draw(
                st.lists(
                    st.sampled_from(_LOCAL_NAMES),
                    min_size=0,
                    max_size=4,
                    unique=True,
                )
            )
            split_idx = draw(st.integers(min_value=0, max_value=len(local_names)))
            outer_names = local_names[:split_idx]
            inner_names = local_names[split_idx:]
            outer_locals = [
                draw(_valid_local_definition_strategy(local_name, indent))
                for local_name in outer_names
            ]
            inner_locals = [
                draw(_valid_local_definition_strategy(local_name, indent))
                for local_name in inner_names
            ]
            fragments.append(
                _action_with_block(
                    _PROJECT_FQUN,
                    "test.def",
                    outer_locals=outer_locals,
                    inner_locals=inner_locals,
                    indent=indent,
                    include_trigger_comment=include_trigger_comment,
                    include_action_close_comment=include_action_close_comment,
                    blank_lines_in_blocks=blank_lines_in_blocks,
                )
            )

    separator = draw(
        st.sampled_from(
            [
                "",
                "\n",
                "# between definitions\n",
                "\n# between definitions\n",
            ]
        )
    )
    return separator.join(fragments)


@st.composite
def syntactic_sources(draw: st.DrawFn) -> str:
    """Generate syntactically valid sources with random names (for mutations)."""
    num_defs = draw(st.integers(min_value=1, max_value=3))
    defs: list[str] = []
    for _ in range(num_defs):
        kind = draw(
            st.sampled_from(
                ["position_simple", "position", "action_simple", "action_block"]
            )
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


def _mutate_source(source: str, draw: st.DrawFn) -> str:
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
        keywords = [
            "define",
            "the",
            "potential",
            "position",
            "action",
            "it happens when",
            "and it does",
        ]
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


@st.composite
def mutated_sources(draw: st.DrawFn) -> str:
    source = draw(syntactic_sources())
    return _mutate_source(source, draw)


@dataclass(frozen=True)
class ProjectRootCase:
    relative_path: str
    universe_name: str
    files: dict[str, str]
    local_deps: dict[str, str]


@dataclass(frozen=True)
class ProjectCase:
    entrypoint: str
    roots: tuple[ProjectRootCase, ...]


def _build_same_universe_chain_project(
    root_universe: str,
    *,
    use_nested_entrypoint: bool,
) -> ProjectCase:
    if use_nested_entrypoint:
        entrypoint = "nested/deep/test.def"
        middle_file = "nested/deep/middle.def"
        leaf_file = "nested/deep/leaf.def"
    else:
        entrypoint = "test.def"
        middle_file = "middle.def"
        leaf_file = "leaf.def"
    root_files = {
        entrypoint: _position_with_requirements(
            root_universe, entrypoint, [("position", _definition_path(middle_file))]
        ),
        middle_file: _position_with_requirements(
            root_universe, middle_file, [("position", _definition_path(leaf_file))]
        ),
        leaf_file: _position_simple(root_universe, leaf_file),
    }
    return ProjectCase(
        entrypoint=entrypoint,
        roots=(
            ProjectRootCase(
                relative_path="",
                universe_name=root_universe,
                files=root_files,
                local_deps={},
            ),
        ),
    )


def _build_action_local_constraints_project(root_universe: str) -> ProjectCase:
    root_files = {
        "test.def": _action_with_block(
            root_universe,
            "test.def",
            outer_locals=[
                _local_position_with_requirements(
                    "outer_pos",
                    [("position", "/target")],
                    indent="    ",
                )
            ],
            inner_locals=[
                _local_position_with_requirements(
                    "inner_pos",
                    [("action", "/target")],
                    indent="    ",
                )
            ],
            include_trigger_comment=True,
            include_action_close_comment=True,
        ),
        "target.def": _position_simple(root_universe, "target.def")
        + _action_simple(root_universe, "target.def"),
    }
    return ProjectCase(
        entrypoint="test.def",
        roots=(
            ProjectRootCase(
                relative_path="",
                universe_name=root_universe,
                files=root_files,
                local_deps={},
            ),
        ),
    )


def _build_dual_type_reference_project(root_universe: str) -> ProjectCase:
    root_files = {
        "test.def": _position_with_requirements(
            root_universe,
            "test.def",
            [("position", "/shared"), ("action", "/shared")],
        ),
        "shared.def": _position_simple(root_universe, "shared.def")
        + _action_simple(root_universe, "shared.def"),
    }
    return ProjectCase(
        entrypoint="test.def",
        roots=(
            ProjectRootCase(
                relative_path="",
                universe_name=root_universe,
                files=root_files,
                local_deps={},
            ),
        ),
    )


def _build_cross_fqun_project(
    root_universe: str,
    child_universe: str,
    *,
    nested_child: bool,
) -> ProjectCase:
    child_path = "lib"
    root_files = {
        "test.def": _position_with_requirements(
            root_universe,
            "test.def",
            [
                (
                    "position",
                    _global_name(child_universe, "target.def"),
                )
            ],
        )
    }
    child_files = {"target.def": _position_simple(child_universe, "target.def")}
    roots: list[ProjectRootCase] = [
        ProjectRootCase(
            relative_path="",
            universe_name=root_universe,
            files=root_files,
            local_deps={child_universe: child_path},
        )
    ]
    if not nested_child:
        roots.append(
            ProjectRootCase(
                relative_path=child_path,
                universe_name=child_universe,
                files=child_files,
                local_deps={},
            )
        )
        return ProjectCase(entrypoint="test.def", roots=tuple(roots))

    grandchild_universe = _VALID_GRANDCHILD_UNIVERSES[0]
    child_files["target.def"] = _position_with_requirements(
        child_universe,
        "target.def",
        [("position", _global_name(grandchild_universe, "leaf.def"))],
    )
    roots.extend(
        [
            ProjectRootCase(
                relative_path=child_path,
                universe_name=child_universe,
                files=child_files,
                local_deps={grandchild_universe: "inner"},
            ),
            ProjectRootCase(
                relative_path="lib/inner",
                universe_name=grandchild_universe,
                files={"leaf.def": _position_simple(grandchild_universe, "leaf.def")},
                local_deps={},
            ),
        ]
    )
    return ProjectCase(entrypoint="test.def", roots=tuple(roots))


def _build_cross_fqun_action_statements_project(
    root_universe: str,
    child_universe: str,
) -> ProjectCase:
    root_files = {
        "test.def": _action_with_block(
            root_universe,
            "test.def",
            outer_locals=[],
            inner_locals=[
                _local_position_with_requirements(
                    "inner_pos",
                    [("position", _global_name(child_universe, "target.def"))],
                    indent="    ",
                )
            ],
            blank_lines_in_blocks=True,
        )
    }
    child_files = {
        "target.def": _position_simple(child_universe, "target.def")
        + _action_simple(child_universe, "target.def")
    }
    return ProjectCase(
        entrypoint="test.def",
        roots=(
            ProjectRootCase(
                relative_path="",
                universe_name=root_universe,
                files=root_files,
                local_deps={child_universe: "lib"},
            ),
            ProjectRootCase(
                relative_path="lib",
                universe_name=child_universe,
                files=child_files,
                local_deps={},
            ),
        ),
    )


@st.composite
def valid_project_cases(draw: st.DrawFn) -> ProjectCase:
    root_universe = draw(st.sampled_from(_VALID_ROOT_UNIVERSES))
    child_universe = draw(st.sampled_from(_VALID_CHILD_UNIVERSES))
    project_kind = draw(
        st.sampled_from(
            [
                "same_universe_chain",
                "same_universe_nested_chain",
                "action_local_constraints",
                "dual_type_reference",
                "cross_fqun",
                "cross_fqun_nested",
                "cross_fqun_action_statements",
            ]
        )
    )
    if project_kind == "same_universe_chain":
        return _build_same_universe_chain_project(
            root_universe, use_nested_entrypoint=False
        )
    if project_kind == "same_universe_nested_chain":
        return _build_same_universe_chain_project(
            root_universe, use_nested_entrypoint=True
        )
    if project_kind == "action_local_constraints":
        return _build_action_local_constraints_project(root_universe)
    if project_kind == "dual_type_reference":
        return _build_dual_type_reference_project(root_universe)
    if project_kind == "cross_fqun":
        return _build_cross_fqun_project(
            root_universe, child_universe, nested_child=False
        )
    if project_kind == "cross_fqun_nested":
        return _build_cross_fqun_project(
            root_universe, child_universe, nested_child=True
        )
    return _build_cross_fqun_action_statements_project(root_universe, child_universe)


def _mutate_project_case(
    project_case: ProjectCase,
    draw: st.DrawFn,
) -> ProjectCase:
    file_locations: list[tuple[int, str]] = []
    for i, root_case in enumerate(project_case.roots):
        for rel_path in root_case.files:
            file_locations.append((i, rel_path))
    target_root_idx, target_file = draw(st.sampled_from(file_locations))
    roots = list(project_case.roots)
    target_root = roots[target_root_idx]
    mutated_files = dict(target_root.files)
    mutated_files[target_file] = _mutate_source(mutated_files[target_file], draw)
    roots[target_root_idx] = replace(target_root, files=mutated_files)
    return ProjectCase(entrypoint=project_case.entrypoint, roots=tuple(roots))


@st.composite
def mutated_project_cases(draw: st.DrawFn) -> ProjectCase:
    project_case = draw(valid_project_cases())
    return _mutate_project_case(project_case, draw)


@pytest.fixture
def fuzz_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _setup_project(tmp_path, _PROJECT_FQUN)
    (tmp_path / "another_test.def").write_text(
        _action_simple(_PROJECT_FQUN, "another_test.def")
        + _position_simple(_PROJECT_FQUN, "another_test.def"),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _materialize_project_case(tmp_path: Path, project_case: ProjectCase) -> None:
    _reset_tmp_path(tmp_path)
    for root_case in project_case.roots:
        root_path = tmp_path / root_case.relative_path
        root_path.mkdir(parents=True, exist_ok=True)
        _setup_project(
            root_path,
            root_case.universe_name,
            local_deps=root_case.local_deps,
        )
        _write_files(root_path, root_case.files)


def _assert_results_are_clean(
    results: list[validation_result.ValidationResult], source_hint: str
) -> None:
    diagnostics_seen = [diag for result in results for diag in result.diagnostics]
    exceptions_seen = [
        result.exception for result in results if result.exception is not None
    ]
    if diagnostics_seen or exceptions_seen:
        rendered = "\n".join(
            [f"exception: {exc!r}" for exc in exceptions_seen]
            + [f"diagnostic: {diag!r}" for diag in diagnostics_seen]
        )
        pytest.fail(
            "Expected clean validation results, got errors:\n"
            + f"{rendered}\n"
            + f"\nProject:\n{source_hint}",
            pytrace=False,
        )


def _assert_only_parser_syntax_exceptions(
    results: list[validation_result.ValidationResult], source_hint: str
) -> None:
    allowed_exceptions = (
        parser_exceptions.DefineSyntaxError,
        exceptions.SourceFileNotFoundError,
    )
    exceptions_seen = [
        result.exception for result in results if result.exception is not None
    ]
    unclassified_errors = [
        error for error in exceptions_seen if not isinstance(error, allowed_exceptions)
    ]
    if unclassified_errors:
        rendered_errors = "\n".join(
            f"- {error!r}:\n\t{error!s}" for error in unclassified_errors
        )
        pytest.fail(
            "Unclassified errors:\n"
            + f"{rendered_errors}\n"
            + f"\nSource:\n{source_hint}",
            pytrace=False,
        )


def _project_case_debug_text(project_case: ProjectCase) -> str:
    lines = [f"entrypoint: {project_case.entrypoint}"]
    for root_case in project_case.roots:
        lines.append(
            f"root={root_case.relative_path or '.'} universe={root_case.universe_name}"
        )
        if root_case.local_deps:
            lines.append(f"deps={root_case.local_deps!r}")
        for rel_path, source in sorted(root_case.files.items()):
            lines.append(f"--- {root_case.relative_path}/{rel_path}".replace("//", "/"))
            lines.append(source.rstrip("\n"))
    return "\n".join(lines)


@settings(
    deadline=None,
    database=None,
    max_examples=_EXAMPLES_VALID_SINGLE,
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
    max_examples=_EXAMPLES_VALID_PROJECTS,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(project_case=valid_project_cases())
def test_valid_projects_run_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, project_case: ProjectCase
):
    _materialize_project_case(tmp_path, project_case)
    monkeypatch.chdir(tmp_path)

    d = driver.Driver()
    debug_source = _project_case_debug_text(project_case)
    results = d.validate_program(Path(project_case.entrypoint))
    _assert_results_are_clean(results, debug_source)

    error_stream = io.StringIO()
    run_result = d.run(Path(project_case.entrypoint), error_stream=error_stream)
    _check_error_stream(error_stream.getvalue(), expect_content=False)
    assert run_result == driver.ExitCode.SUCCESS, debug_source


@settings(
    deadline=None,
    database=None,
    max_examples=_EXAMPLES_MUTATED_SINGLE,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(source=mutated_sources())
def test_mutated_syntax_no_unclassified_errors(fuzz_project: Path, source: str):
    file_path = fuzz_project / "test.def"
    file_path.write_text(source, encoding="utf-8")
    d = driver.Driver()
    try:
        results = d.validate_program(Path("test.def"))
    except exceptions.DefineError:
        return
    _assert_only_parser_syntax_exceptions(results, _escape_content(source))


@settings(
    deadline=None,
    database=None,
    max_examples=_EXAMPLES_MUTATED_SINGLE,
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
    max_examples=_EXAMPLES_MUTATED_PROJECTS,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(project_case=mutated_project_cases())
def test_mutated_projects_no_unclassified_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, project_case: ProjectCase
):
    _materialize_project_case(tmp_path, project_case)
    monkeypatch.chdir(tmp_path)
    d = driver.Driver()
    try:
        results = d.validate_program(Path(project_case.entrypoint))
    except exceptions.DefineError:
        return
    _assert_only_parser_syntax_exceptions(
        results, _project_case_debug_text(project_case)
    )


@settings(
    deadline=None,
    database=None,
    max_examples=_EXAMPLES_MUTATED_PROJECTS,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(project_case=mutated_project_cases())
def test_mutated_projects_never_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, project_case: ProjectCase
):
    _materialize_project_case(tmp_path, project_case)
    monkeypatch.chdir(tmp_path)
    d = driver.Driver()
    error_stream = io.StringIO()
    result = d.run(Path(project_case.entrypoint), error_stream=error_stream)
    error_output = error_stream.getvalue()
    assert isinstance(result, driver.ExitCode), (
        "run() did not return ExitCode for project:\n"
        + _project_case_debug_text(project_case)
    )
    _check_error_stream(error_output, expect_content=result == driver.ExitCode.ERROR)


@settings(
    deadline=None,
    database=None,
    max_examples=_EXAMPLES_RANDOM_BYTES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(data=st.binary(max_size=800))
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
