# pyright: reportUnusedCallResult=false
"""Fuzz tests for the Define compiler driver."""

import shutil
from dataclasses import dataclass, replace
from pathlib import Path
from typing import cast

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from define.compiler import driver, exceptions, parser_exceptions
from define.compiler.validator import validation_result

_MULTIVERSE_NAMES = ["mv", "standard", "mymv", "test_mv"]
_AUTHORITY_DOMAINS = ["example.com", "define-lang.org", "test.io", "my.domain.co"]
_UNIVERSE_NAMES = ["my_lib", "core", "fuzz_test", "std"]
_PATH_SEGMENTS = ["path", "hello", "sub", "dir", "leaf", "foo", "bar"]
_LOCAL_NAMES = ["x", "my_pos", "local", "inner", "_tmp", "pos2", "node_1"]
_CHAIN_LOCALS_FOR_CREATE = ["src_pos", "src_pos2"]
_MOVE_POSITION_NAMES = ["mv_a", "mv_b", "mv_c"]
_ACTION_WITH_INNER_FILE = "action_with_inner.def"
_INNER_POS_IN_ACTION = "inner_pos"
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
_EXAMPLES_VALID_SINGLE = 600
_EXAMPLES_VALID_PROJECTS = 400
_EXAMPLES_MUTATED_SINGLE = 800
_EXAMPLES_MUTATED_PROJECTS = 400
_EXAMPLES_RANDOM_BYTES = 400


def _escape_content(text: str) -> str:
    """Escape invisible and control characters, preserving spaces."""
    chars: list[str] = []
    for c in text:
        if c == " " or c.isprintable():
            chars.append(c)
        else:
            chars.append(repr(c)[1:-1])
    return "".join(chars)


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


def _create_dimension_point_statement(position_reference: str, *, indent: str) -> str:
    return f"{indent}create a dimension point in {position_reference}.\n"


def _move_dimension_point_statement(from_ref: str, to_ref: str, *, indent: str) -> str:
    return f"{indent}move the dimension point in {from_ref} to {to_ref}.\n"


@st.composite
def _global_chain_valid_references(draw: st.DrawFn) -> str:
    chain_length = draw(st.integers(min_value=1, max_value=3))
    segments = [f"position<{draw(global_names())}>"]
    for _ in range(chain_length):
        middle_kind = draw(st.sampled_from(["position", "action"]))
        segments.append(f"{middle_kind}<{draw(global_names())}>")
    segments.append(f"position<{draw(global_names())}>")
    return "::".join(segments)


@st.composite
def _local_start_chain_references(draw: st.DrawFn) -> str:
    local_name = draw(st.sampled_from(_LOCAL_NAMES))
    chain_length = draw(st.integers(min_value=1, max_value=2))
    segments = [f"position<{local_name}>"]
    for _ in range(chain_length):
        middle_kind = draw(st.sampled_from(["position", "action"]))
        segments.append(f"{middle_kind}<{draw(global_names())}>")
    segments.append(f"position<{draw(global_names())}>")
    return "::".join(segments)


@st.composite
def create_dimension_point_references(draw: st.DrawFn) -> str:
    return cast(
        "str",
        draw(
            st.one_of(
                global_names().map(lambda n: f"position<{n}>"),
                st.sampled_from(_LOCAL_NAMES).map(lambda n: f"position<{n}>"),
                _global_chain_valid_references(),
                _local_start_chain_references(),
                global_names().map(lambda n: f"action<{n}>"),
                st.tuples(global_names(), global_names()).map(
                    lambda t: f"action<{t[0]}>::position<{t[1]}>"
                ),
                st.tuples(global_names(), global_names()).map(
                    lambda t: f"position<{t[0]}>::action<{t[1]}>"
                ),
                st.tuples(global_names(), global_names()).map(
                    lambda t: f"action<{t[0]}>::action<{t[1]}>"
                ),
                st.tuples(global_names(), global_names(), global_names()).map(
                    lambda t: f"action<{t[0]}>::action<{t[1]}>::position<{t[2]}>"
                ),
                st.tuples(
                    global_names(), global_names(), global_names(), global_names()
                ).map(
                    lambda t: (
                        f"position<{t[0]}>::action<{t[1]}>::action<{t[2]}>::position<{t[3]}>"
                    )
                ),
            )
        ),
    )


def _action_block_with_name(
    action_name: str,
    *,
    outer_locals: list[str],
    inner_locals: list[str],
    indent: str = "    ",
    include_trigger_comment: bool = False,
    include_action_close_comment: bool = False,
    blank_lines_in_blocks: bool = False,
    trigger_condition_ref: str = "position<run>",
) -> str:
    lines = [f"define the potential action<{action_name}> {{"]
    lines.append(f"{indent}define the position<run>.")
    for local in outer_locals:
        lines.extend(local.rstrip("\n").splitlines())

    trigger_line = f"{indent}it happens when {{"
    if include_trigger_comment:
        trigger_line += " # trigger comment"
    lines.append(trigger_line)
    lines.append(f"{indent}{indent}the {trigger_condition_ref} has a dimension point.")
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
    trigger_condition_ref: str = "position<run>",
) -> str:
    return _action_block_with_name(
        _global_name(universe_name, rel_def_file),
        outer_locals=outer_locals,
        inner_locals=inner_locals,
        indent=indent,
        include_trigger_comment=include_trigger_comment,
        include_action_close_comment=include_action_close_comment,
        blank_lines_in_blocks=blank_lines_in_blocks,
        trigger_condition_ref=trigger_condition_ref,
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
        "    it may only contain dimension points where {",
    ]
    for child_type, child_name in requirements:
        lines.append(f"        it has the {child_type}<{child_name}>.")
    lines.extend(["    }", "}"])
    return _join_lines(lines)


@st.composite
def action_definitions_simple(draw: st.DrawFn) -> str:
    name = draw(global_names())
    return f"define the potential action<{name}>.\n"


@st.composite
def action_definitions_with_block(draw: st.DrawFn) -> str:
    name = draw(global_names())
    outer_indent = "    "
    inner_indent = "        "
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
            outer_locals.append(_local_position_simple(local_name, indent=outer_indent))
        else:
            req_type = draw(st.sampled_from(["position", "action"]))
            req_name = draw(global_names())
            outer_locals.append(
                _local_position_with_requirements(
                    local_name,
                    [(req_type, req_name)],
                    indent=outer_indent,
                )
            )
    for local_name in inner_names:
        if draw(st.booleans()):
            inner_locals.append(_local_position_simple(local_name, indent=inner_indent))
        else:
            req_type = draw(st.sampled_from(["position", "action"]))
            req_name = draw(global_names())
            inner_locals.append(
                _local_position_with_requirements(
                    local_name,
                    [(req_type, req_name)],
                    indent=inner_indent,
                )
            )
    create_count = draw(st.integers(min_value=0, max_value=2))
    for _ in range(create_count):
        position_reference = draw(create_dimension_point_references())
        inner_locals.append(
            _create_dimension_point_statement(position_reference, indent=inner_indent)
        )
    move_count = draw(st.integers(min_value=0, max_value=2))
    for _ in range(move_count):
        from_ref = draw(create_dimension_point_references())
        to_ref = draw(create_dimension_point_references())
        inner_locals.append(
            _move_dimension_point_statement(from_ref, to_ref, indent=inner_indent)
        )
    trigger_condition_ref = draw(create_dimension_point_references())
    return _action_block_with_name(
        name,
        outer_locals=outer_locals,
        inner_locals=inner_locals,
        indent=outer_indent,
        include_trigger_comment=include_trigger_comment,
        include_action_close_comment=include_action_close_comment,
        blank_lines_in_blocks=blank_lines_in_blocks,
        trigger_condition_ref=trigger_condition_ref,
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
def _valid_create_spec(
    draw: st.DrawFn,
    *,
    local_name: str,
    indent: str,
    allow_target_another_test: bool,
    allow_target_inner_pos: bool,
) -> tuple[str, str | None]:
    kinds = ["local_direct"]
    if allow_target_another_test:
        kinds.extend(["local_chained", "global_direct"])
    if allow_target_inner_pos:
        kinds.append("local_chained_via_action")
    kind = draw(st.sampled_from(kinds))
    if kind == "global_direct":
        return f"position<{_ANOTHER_VALID_PATH}>", None
    if kind == "local_direct":
        return (
            f"position<{local_name}>",
            _local_position_simple(local_name, indent=indent),
        )
    action_path = _definition_path(_ACTION_WITH_INNER_FILE)
    if kind == "local_chained_via_action":
        return (
            f"position<{local_name}>::action<{action_path}>::position<{_INNER_POS_IN_ACTION}>",
            _local_position_with_requirements(
                local_name, [("action", action_path)], indent=indent
            ),
        )
    return (
        f"position<{local_name}>::position<{_ANOTHER_VALID_PATH}>",
        _local_position_with_requirements(
            local_name, [("position", _ANOTHER_VALID_PATH)], indent=indent
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
            outer_indent = "    "
            inner_indent = "        "
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
            outer_locals: list[str] = []
            inner_locals: list[str] = []
            create_count = draw(
                st.integers(min_value=0, max_value=len(_CHAIN_LOCALS_FOR_CREATE))
            )
            another_test_targeted = False
            inner_pos_targeted = False
            for i in range(create_count):
                ref, outer_def = draw(
                    _valid_create_spec(
                        local_name=_CHAIN_LOCALS_FOR_CREATE[i],
                        indent=outer_indent,
                        allow_target_another_test=not another_test_targeted,
                        allow_target_inner_pos=not inner_pos_targeted,
                    )
                )
                if outer_def is not None:
                    outer_locals.append(outer_def)
                last_segment = ref.split("::")[-1]
                if _ANOTHER_VALID_PATH in last_segment:
                    another_test_targeted = True
                elif _INNER_POS_IN_ACTION in last_segment:
                    inner_pos_targeted = True
                inner_locals.append(
                    _create_dimension_point_statement(ref, indent=inner_indent)
                )
            move_count = draw(st.integers(min_value=0, max_value=2))
            if move_count > 0:
                needed = _MOVE_POSITION_NAMES[: move_count + 1]
                for pos_name in needed:
                    outer_locals.append(
                        _local_position_simple(pos_name, indent=outer_indent)
                    )
                inner_locals.append(
                    _create_dimension_point_statement(
                        f"position<{needed[0]}>", indent=inner_indent
                    )
                )
                for i in range(move_count):
                    inner_locals.append(
                        _move_dimension_point_statement(
                            f"position<{needed[i]}>",
                            f"position<{needed[i + 1]}>",
                            indent=inner_indent,
                        )
                    )
            outer_locals += [
                draw(_valid_local_definition_strategy(local_name, outer_indent))
                for local_name in outer_names
            ]
            inner_locals += [
                draw(_valid_local_definition_strategy(local_name, inner_indent))
                for local_name in inner_names
            ]
            trigger_condition_ref = draw(create_dimension_point_references())
            fragments.append(
                _action_with_block(
                    _PROJECT_FQUN,
                    "test.def",
                    outer_locals=outer_locals,
                    inner_locals=inner_locals,
                    indent=outer_indent,
                    include_trigger_comment=include_trigger_comment,
                    include_action_close_comment=include_action_close_comment,
                    blank_lines_in_blocks=blank_lines_in_blocks,
                    trigger_condition_ref=trigger_condition_ref,
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
            "create a dimension point in",
            "move the dimension point in",
            "it happens when",
            "and it does",
        ]
        keyword = draw(st.sampled_from(keywords))
        indices: list[int] = []
        start = 0
        while (pos := source.find(keyword, start)) != -1:
            indices.append(pos)
            start = pos + 1
        if indices:
            idx = draw(st.sampled_from(indices))
            return source[:idx] + source[idx + len(keyword) :]

    if mutation == "swap_adjacent" and len(source) > 1:
        idx = draw(st.integers(min_value=0, max_value=len(source) - 2))
        return source[:idx] + source[idx + 1] + source[idx] + source[idx + 2 :]

    if mutation == "remove_newline" and "\n" in source:
        indices = [i for i, c in enumerate(source) if c == "\n"]
        idx = draw(st.sampled_from(indices))
        return source[:idx] + source[idx + 1 :]

    if mutation == "remove_angle_bracket":
        indices = [i for i, c in enumerate(source) if c in "<>"]
        if indices:
            idx = draw(st.sampled_from(indices))
            return source[:idx] + source[idx + 1 :]

    if mutation == "remove_structural_char":
        indices = [i for i, c in enumerate(source) if c in ":.{}"]
        if indices:
            idx = draw(st.sampled_from(indices))
            return source[:idx] + source[idx + 1 :]

    if mutation == "insert_unicode":
        idx = draw(st.integers(min_value=0, max_value=len(source)))
        char = draw(st.sampled_from(["\u00e9", "\u00f1", "\u4e16", "\U0001f600"]))
        return source[:idx] + char + source[idx:]

    return source


@st.composite
def mutated_sources(draw: st.DrawFn) -> str:
    source = draw(syntactic_sources())
    mutated = _mutate_source(source, draw)
    if "create a dimension point in " in mutated:
        return mutated.replace(
            "create a dimension point in ", "create a dimension point in", 1
        )
    if "move the dimension point in " in mutated:
        return mutated.replace(
            "move the dimension point in ", "move the dimension point in", 1
        )
    return mutated


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
                    indent="        ",
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
                    indent="        ",
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


def _build_move_dimension_point_project(root_universe: str) -> ProjectCase:
    root_files = {
        "test.def": _action_with_block(
            root_universe,
            "test.def",
            outer_locals=[
                _local_position_simple("from_pos", indent="    "),
                _local_position_simple("to_pos", indent="    "),
            ],
            inner_locals=[
                _create_dimension_point_statement(
                    "position<from_pos>", indent="        "
                ),
                _move_dimension_point_statement(
                    "position<from_pos>", "position<to_pos>", indent="        "
                ),
            ],
        ),
    }
    return ProjectCase(
        entrypoint="test.def",
        roots=(ProjectRootCase("", root_universe, root_files, {}),),
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
                "move_local",
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
    if project_kind == "cross_fqun_action_statements":
        return _build_cross_fqun_action_statements_project(
            root_universe, child_universe
        )
    return _build_move_dimension_point_project(root_universe)


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
    (tmp_path / _ACTION_WITH_INNER_FILE).write_text(
        _action_with_block(
            _PROJECT_FQUN,
            _ACTION_WITH_INNER_FILE,
            outer_locals=[_local_position_simple(_INNER_POS_IN_ACTION, indent="    ")],
            inner_locals=[],
        ),
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
def test_valid_syntax_validates_cleanly(fuzz_project: Path, source: str):
    file_path = fuzz_project / "test.def"
    file_path.write_text(source, encoding="utf-8")
    d = driver.Driver()
    results = d.validate_program(Path("test.def")).results
    _assert_results_are_clean(results, _escape_content(source))


@settings(
    deadline=None,
    database=None,
    max_examples=_EXAMPLES_VALID_PROJECTS,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(project_case=valid_project_cases())
def test_valid_projects_validate_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, project_case: ProjectCase
):
    _materialize_project_case(tmp_path, project_case)
    monkeypatch.chdir(tmp_path)

    d = driver.Driver()
    debug_source = _project_case_debug_text(project_case)
    results = d.validate_program(Path(project_case.entrypoint)).results
    _assert_results_are_clean(results, debug_source)


@settings(
    deadline=None,
    database=None,
    max_examples=_EXAMPLES_MUTATED_SINGLE,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(source=mutated_sources())
def test_mutated_syntax_no_unclassified_errors(fuzz_project: Path, source: str):
    (fuzz_project / "test.def").write_text(source, encoding="utf-8")
    d = driver.Driver()
    results = d.validate_program(Path("test.def")).results
    _assert_only_parser_syntax_exceptions(results, _escape_content(source))


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
    results = d.validate_program(Path(project_case.entrypoint)).results
    _assert_only_parser_syntax_exceptions(
        results, _project_case_debug_text(project_case)
    )


@settings(
    deadline=None,
    database=None,
    max_examples=_EXAMPLES_RANDOM_BYTES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(data=st.binary(max_size=800))
def test_random_bytes_no_unclassified_errors(fuzz_project: Path, data: bytes):
    file_path = fuzz_project / "test.def"
    file_path.write_bytes(data)
    d = driver.Driver()
    results = d.validate_program(Path("test.def")).results
    _assert_only_parser_syntax_exceptions(results, repr(data))
