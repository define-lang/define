# pyright: reportUnusedCallResult=false
"""Fuzz tests for the Define compiler driver."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

import pytest
from hypothesis import HealthCheck, example, given, settings
from hypothesis import strategies as st

from define.compiler import driver, exceptions, parser, parser_exceptions

if TYPE_CHECKING:
    from define.compiler.validator import validation_result

_PARSER = parser.Parser()

_MULTIVERSE_NAMES = ["mv", "standard", "mymv", "test_mv"]
_AUTHORITY_DOMAINS = ["example.com", "define-lang.org", "test.io", "my.domain.co"]
_UNIVERSE_NAMES = ["my_lib", "core", "fuzz_test", "std"]
_PATH_SEGMENTS = ["path", "hello", "sub", "dir", "leaf", "foo", "bar"]
_LOCAL_NAMES = ["x", "my_pos", "local", "inner", "_tmp", "pos2", "node_1"]
_MOVE_POSITION_NAMES = ["mv_a", "mv_b", "mv_c", "mv_d", "mv_e"]
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
_EXAMPLES_MUTATED_SINGLE = 1200
_EXAMPLES_MUTATED_PROJECTS = 800
_EXAMPLES_RANDOM_BYTES = 400
_EXAMPLES_RANDOM_LOCAL_NAMES = 400
_EXAMPLES_RANDOM_GLOBAL_NAMES_RAW = 400
_EXAMPLES_RANDOM_GLOBAL_NAMES_STRUCTURED = 400


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
    name = _global_name(universe_name, rel_def_file)
    return (
        f"define the potential action<{name}> {{\n"
        f"    define the position<_noop>.\n"
        f"    it happens when {{\n"
        f"        the position<_noop> has a particle.\n"
        f"    }} and it does {{\n"
        f"        destroy the particle in position<_noop>.\n"
        f"        define the position<__noop>.\n"
        f"        create a particle in position<__noop>.\n"
        f"    }}\n"
        f"}}\n"
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
        f"{indent}it may only contain particles where {{",
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
        f"{indent}    it may only contain particles where {{",
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


def _create_particle_statement(position_reference: str, *, indent: str) -> str:
    return f"{indent}create a particle in {position_reference}.\n"


def _move_particle_statement(from_ref: str, to_ref: str, *, indent: str) -> str:
    return f"{indent}move the particle in {from_ref} to {to_ref}.\n"


def _destroy_particle_statement(position_reference: str, *, indent: str) -> str:
    return f"{indent}destroy the particle in {position_reference}.\n"


@st.composite
def _global_chain_valid_references(draw: st.DrawFn) -> str:
    chain_length = draw(st.integers(min_value=1, max_value=5))
    segments = [f"position<{draw(global_names())}>"]
    for _ in range(chain_length):
        middle_kind = draw(st.sampled_from(["position", "action"]))
        segments.append(f"{middle_kind}<{draw(global_names())}>")
    segments.append(f"position<{draw(global_names())}>")
    return "::".join(segments)


@st.composite
def _local_start_chain_references(draw: st.DrawFn) -> str:
    local_name = draw(st.sampled_from(_LOCAL_NAMES))
    chain_length = draw(st.integers(min_value=1, max_value=3))
    segments = [f"position<{local_name}>"]
    for _ in range(chain_length):
        middle_kind = draw(st.sampled_from(["position", "action"]))
        segments.append(f"{middle_kind}<{draw(global_names())}>")
    segments.append(f"position<{draw(global_names())}>")
    return "::".join(segments)


@st.composite
def create_particle_references(draw: st.DrawFn) -> str:
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
    trigger_kind: Literal["presence", "constructor", "destructor"] = "presence",
    quality_implications: list[tuple[str, str]] | None = None,
) -> str:
    lines = [f"define the potential action<{action_name}> {{"]
    if quality_implications:
        for typed_kind, impl_name in quality_implications:
            lines.append(f"{indent}it also assigns the {typed_kind}<{impl_name}>.")
    if trigger_kind == "presence":
        lines.append(f"{indent}define the position<run>.")
    for local in outer_locals:
        lines.extend(local.rstrip("\n").splitlines())

    trigger_line = f"{indent}it happens when {{"
    if include_trigger_comment:
        trigger_line += " # trigger comment"
    lines.append(trigger_line)
    if trigger_kind == "constructor":
        lines.append(f"{indent}{indent}this particle is created.")
    elif trigger_kind == "destructor":
        lines.append(f"{indent}{indent}this particle is being destroyed.")
    else:
        lines.append(f"{indent}{indent}the {trigger_condition_ref} has a particle.")
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
    trigger_kind: Literal["presence", "constructor", "destructor"] = "presence",
    quality_implications: list[tuple[str, str]] | None = None,
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
        trigger_kind=trigger_kind,
        quality_implications=quality_implications,
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
    num_auth_segments = draw(st.integers(min_value=0, max_value=4))
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
    definition_kind = draw(
        st.sampled_from(
            [
                "position_simple",
                "position",
            ]
        )
    )
    if definition_kind == "position_simple":
        return f"define the potential position<{name}>.\n"
    num_requirements = draw(st.integers(min_value=1, max_value=5))
    requirements: list[tuple[str, str]] = []
    for _ in range(num_requirements):
        child_name = draw(global_names())
        child_type = draw(st.sampled_from(["position", "action"]))
        requirements.append((child_type, child_name))
    lines = [
        f"define the potential position<{name}> {{",
        "    it may only contain particles where {",
    ]
    for child_type, child_name in requirements:
        lines.append(f"        it has the {child_type}<{child_name}>.")
    lines.extend(["    }", "}"])
    return _join_lines(lines)


@st.composite
def action_definitions_simple(draw: st.DrawFn) -> str:
    name = draw(global_names())
    return _action_block_with_name(
        name,
        trigger_kind=draw(st.sampled_from(["presence", "constructor", "destructor"])),
        outer_locals=[],
        inner_locals=[
            _local_position_simple("__noop", indent="        "),
            _create_particle_statement("position<__noop>", indent="        "),
        ],
    )


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
            max_size=6,
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
    create_count = draw(st.integers(min_value=0, max_value=4))
    for _ in range(create_count):
        position_reference = draw(create_particle_references())
        inner_locals.append(
            _create_particle_statement(position_reference, indent=inner_indent)
        )
    move_count = draw(st.integers(min_value=0, max_value=4))
    for _ in range(move_count):
        from_ref = draw(create_particle_references())
        to_ref = draw(create_particle_references())
        inner_locals.append(
            _move_particle_statement(from_ref, to_ref, indent=inner_indent)
        )
    destroy_count = draw(st.integers(min_value=0, max_value=4))
    for _ in range(destroy_count):
        position_reference = draw(create_particle_references())
        inner_locals.append(
            _destroy_particle_statement(position_reference, indent=inner_indent)
        )
    trigger_condition_ref = draw(create_particle_references())
    inner_locals = list(draw(st.permutations(inner_locals)))
    return _action_block_with_name(
        name,
        outer_locals=outer_locals,
        inner_locals=inner_locals,
        indent=outer_indent,
        include_trigger_comment=include_trigger_comment,
        include_action_close_comment=include_action_close_comment,
        blank_lines_in_blocks=blank_lines_in_blocks,
        trigger_condition_ref=trigger_condition_ref,
        trigger_kind=draw(st.sampled_from(["presence", "constructor", "destructor"])),
    )


_PROJECT_FQUN = "mv:define-lang.org:fuzz_test"
_ANOTHER_VALID_PATH = "/another_test"
_THIRD_VALID_PATH = "/third_test"
_VALID_REFERENCE_PATHS = [_ANOTHER_VALID_PATH, _THIRD_VALID_PATH]


def _valid_reference_options() -> st.SearchStrategy[list[tuple[str, str]]]:
    return st.lists(
        st.tuples(
            st.sampled_from(["position", "action"]),
            st.sampled_from(_VALID_REFERENCE_PATHS),
        ),
        min_size=1,
        max_size=3,
        unique=True,
    )


_VALID_IMPLICATION_TARGETS = [
    ("position", _ANOTHER_VALID_PATH),
    ("position", _THIRD_VALID_PATH),
    ("action", _ANOTHER_VALID_PATH),
    ("action", _THIRD_VALID_PATH),
]


def _valid_implications_strategy() -> st.SearchStrategy[list[tuple[str, str]]]:
    return st.lists(
        st.sampled_from(_VALID_IMPLICATION_TARGETS),
        min_size=0,
        max_size=len(_VALID_IMPLICATION_TARGETS),
        unique=True,
    )


def _implication_chain_reference(typed_kind: str, name: str) -> str:
    if typed_kind == "position":
        return f"position<{name}>"
    return f"action<{name}>::position<_noop>"


def _local_position_with_used_constraints(
    local_name: str,
    requirements: list[tuple[str, str]],
    *,
    indent: str,
) -> str:
    statements = [
        _local_position_with_requirements(local_name, requirements, indent=indent),
        _create_particle_statement(f"position<{local_name}>", indent=indent),
    ]
    for kind, name in requirements:
        child = _implication_chain_reference(kind, name)
        statements.append(
            _create_particle_statement(
                f"position<{local_name}>::{child}", indent=indent
            )
        )
    return "".join(statements)


_TRAILING_COMMENT_TAGS = [
    " # done",
    " # trailing",
    " # ok",
    " #",
    " # x",
]
_STANDALONE_COMMENT_TEXTS = [
    "# note",
    "# TODO: review",
    "# fuzz comment",
    "#",
    "# section break",
]


@st.composite
def _decorated_source(draw: st.DrawFn, source: str) -> str:
    """Inject standalone comments, blank lines, and trailing comments at safe spots."""
    lines = source.splitlines(keepends=True)
    result: list[str] = []
    for line in lines:
        line_content = line.strip()
        stripped = line.lstrip(" ")
        if line_content and draw(st.integers(min_value=0, max_value=9)) == 0:
            line_indent = len(line) - len(stripped)
            inject_indent = line_indent + 4 if stripped.startswith("}") else line_indent
            choice = draw(st.sampled_from(["blank", "comment"]))
            if choice == "blank":
                result.append("\n")
            else:
                text = draw(st.sampled_from(_STANDALONE_COMMENT_TEXTS))
                result.append(f"{' ' * inject_indent}{text}\n")
        body = line.rstrip("\n")
        if (
            body
            and body[-1] in (".", "}", "{")
            and draw(st.integers(min_value=0, max_value=7)) == 0
        ):
            tag = draw(st.sampled_from(_TRAILING_COMMENT_TAGS))
            line = body + tag + "\n"
        result.append(line)
    return "".join(result)


@st.composite
def particle_operation_sequences(draw: st.DrawFn) -> list[str]:
    occupied: set[str] = set()
    defined: set[str] = set()
    statements: list[str] = []
    for _ in range(draw(st.integers(min_value=1, max_value=40))):
        empty_names = [name for name in _MOVE_POSITION_NAMES if name not in occupied]
        occupied_names = [name for name in _MOVE_POSITION_NAMES if name in occupied]
        kinds: list[str] = []
        if empty_names:
            kinds.append("create")
        if occupied_names:
            kinds.append("destroy")
            if empty_names:
                kinds.append("move")
        kind = draw(st.sampled_from(kinds))
        if kind in ("create", "move"):
            target = draw(st.sampled_from(empty_names))
            if target not in defined:
                statements.append(_local_position_simple(target, indent="        "))
                defined.add(target)
            if kind == "create":
                statements.append(
                    _create_particle_statement(f"position<{target}>", indent="        ")
                )
            else:
                source = draw(st.sampled_from(occupied_names))
                statements.append(
                    _move_particle_statement(
                        f"position<{source}>", f"position<{target}>", indent="        "
                    )
                )
                occupied.remove(source)
            occupied.add(target)
        else:
            source = draw(st.sampled_from(occupied_names))
            statements.append(
                _destroy_particle_statement(f"position<{source}>", indent="        ")
            )
            occupied.remove(source)
    return statements


@st.composite
def valid_sources(draw: st.DrawFn) -> str:
    fragments: list[str] = []
    if draw(st.booleans()):
        requirements = draw(_valid_reference_options())
        fragments.append(
            _position_with_requirements(_PROJECT_FQUN, "test.dfn", requirements)
        )

    statements: list[str] = []
    implications = draw(_valid_implications_strategy())
    for kind, name in implications:
        statements.append(
            _create_particle_statement(
                _implication_chain_reference(kind, name), indent="        "
            )
        )
    local_names = draw(
        st.lists(st.sampled_from(_LOCAL_NAMES), min_size=1, max_size=6, unique=True)
    )
    for local_name in local_names:
        if draw(st.booleans()):
            statements.append(
                _local_position_with_used_constraints(
                    local_name, draw(_valid_reference_options()), indent="        "
                )
            )
        else:
            statements.extend(
                [
                    _local_position_simple(local_name, indent="        "),
                    _create_particle_statement(
                        f"position<{local_name}>", indent="        "
                    ),
                ]
            )
        if draw(st.booleans()):
            statements.append(
                _destroy_particle_statement(
                    f"position<{local_name}>", indent="        "
                )
            )

    statements.extend(draw(particle_operation_sequences()))
    fragments.append(
        _action_with_block(
            _PROJECT_FQUN,
            "test.dfn",
            outer_locals=[],
            inner_locals=statements,
            trigger_kind="constructor",
            quality_implications=implications,
            include_trigger_comment=draw(st.booleans()),
            include_action_close_comment=draw(st.booleans()),
            blank_lines_in_blocks=draw(st.booleans()),
        )
    )
    separator = draw(st.sampled_from(["", "\n", "# between definitions\n"]))
    return draw(_decorated_source(separator.join(fragments)))


@st.composite
def position_definitions_with_implications(draw: st.DrawFn) -> str:
    name = draw(global_names())
    impl_name = draw(global_names())
    impl_kind = draw(st.sampled_from(["position", "action"]))
    constraint_name = draw(global_names())
    constraint_kind = draw(st.sampled_from(["position", "action"]))
    return (
        f"define the potential position<{name}> {{\n"
        f"    it also assigns the {impl_kind}<{impl_name}>.\n"
        f"    it may only contain particles where {{\n"
        f"        it has the {constraint_kind}<{constraint_name}>.\n"
        f"    }}\n"
        f"}}\n"
    )


@st.composite
def action_definitions_with_implications(draw: st.DrawFn) -> str:
    name = draw(global_names())
    impl_name = draw(global_names())
    impl_kind = draw(st.sampled_from(["position", "action"]))
    body_ref = (
        f"position<{impl_name}>"
        if impl_kind == "position"
        else f"action<{impl_name}>::position<_noop>"
    )
    return _action_block_with_name(
        name,
        trigger_kind=draw(st.sampled_from(["presence", "constructor", "destructor"])),
        quality_implications=[(impl_kind, impl_name)],
        outer_locals=[],
        inner_locals=[_create_particle_statement(body_ref, indent="        ")],
    )


@st.composite
def syntactic_sources(draw: st.DrawFn) -> str:
    """Generate definition-shaped sources without enforcing source validity."""
    num_defs = draw(st.integers(min_value=1, max_value=5))
    defs: list[str] = []
    for _ in range(num_defs):
        kind = draw(
            st.sampled_from(
                [
                    "position_simple",
                    "position",
                    "action_simple",
                    "action_block",
                    "position_implication",
                    "action_implication",
                ]
            )
        )
        if kind in ["position_simple", "position"]:
            defs.append(draw(position_definitions()))
        elif kind == "action_simple":
            defs.append(draw(action_definitions_simple()))
        elif kind == "action_block":
            defs.append(draw(action_definitions_with_block()))
        elif kind == "position_implication":
            defs.append(draw(position_definitions_with_implications()))
        else:
            defs.append(draw(action_definitions_with_implications()))
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
    "remove_particle_statement_space",
    "insert_unicode",
    "insert_fragment",
    "replace_span",
    "truncate",
    "duplicate_line",
    "remove_line",
    "swap_lines",
    "change_indentation",
    "replace_condition",
]

_SYNTAX_FRAGMENTS = [
    "define the potential position</p>.\n",
    "define the potential action</a> {\n",
    "define the position<p>.\n",
    "it also assigns the action</a>.\n",
    "it may only contain particles where {\n",
    "it has the position</p>.\n",
    "it happens when {\n",
    "this particle is created.\n",
    "this particle is being destroyed.\n",
    "the position<p> has a particle.\n",
    "} and it does {\n",
    "create a particle in position<p>.\n",
    "move the particle in position<p> to position<q>.\n",
    "destroy the particle in position<p>.\n",
    "position<p>",
    "action</a>::position<p>",
    "::",
    "\n",
    " {\n",
    "}\n",
    ".\n",
    "# comment\n",
]


def _mutate_source(source: str, draw: st.DrawFn) -> str:
    mutation = draw(st.sampled_from(_MUTATIONS))

    if mutation in ("insert_fragment", "replace_span", "truncate"):
        start = draw(st.integers(min_value=0, max_value=len(source)))
        if mutation == "truncate":
            return source[:start]
        end = start
        if mutation == "replace_span":
            end = draw(st.integers(min_value=start, max_value=len(source)))
        fragment = draw(st.sampled_from(_SYNTAX_FRAGMENTS))
        return source[:start] + fragment + source[end:]

    if mutation in (
        "duplicate_line",
        "remove_line",
        "swap_lines",
        "change_indentation",
    ):
        lines = source.splitlines(keepends=True)
        if not lines:
            return source
        index = draw(st.integers(min_value=0, max_value=len(lines) - 1))
        if mutation == "duplicate_line":
            lines.insert(index, lines[index])
        elif mutation == "remove_line":
            del lines[index]
        elif mutation == "swap_lines":
            other = draw(st.integers(min_value=0, max_value=len(lines) - 1))
            lines[index], lines[other] = lines[other], lines[index]
        else:
            indentation = draw(
                st.sampled_from(["", " ", "   ", "        ", "\t", " \t"])
            )
            lines[index] = indentation + lines[index].lstrip(" \t")
        return "".join(lines)

    if mutation == "replace_condition":
        conditions = [
            "this particle is created",
            "this particle is being destroyed",
            "the position<run> has a particle",
        ]
        present = [condition for condition in conditions if condition in source]
        if present:
            return source.replace(
                draw(st.sampled_from(present)), draw(st.sampled_from(conditions)), 1
            )

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
            "create a particle in",
            "move the particle in",
            "destroy the particle in",
            "it happens when",
            "and it does",
            "it also assigns the",
            "this particle is created",
            "this particle is being destroyed",
            "it may only contain particles where",
            "it has the",
        ]
        present_keywords = [keyword for keyword in keywords if keyword in source]
        if not present_keywords:
            return source
        keyword = draw(st.sampled_from(present_keywords))
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

    if mutation == "remove_particle_statement_space":
        prefixes = [
            "create a particle in ",
            "move the particle in ",
            "destroy the particle in ",
        ]
        present_prefixes = [prefix for prefix in prefixes if prefix in source]
        if present_prefixes:
            prefix = draw(st.sampled_from(present_prefixes))
            return source.replace(prefix, prefix.rstrip(" "), 1)

    if mutation == "insert_unicode":
        idx = draw(st.integers(min_value=0, max_value=len(source)))
        char = draw(st.sampled_from(["\u00e9", "\u00f1", "\u4e16", "\U0001f600"]))
        return source[:idx] + char + source[idx:]

    return source


@st.composite
def mutated_sources(draw: st.DrawFn) -> str:
    source = draw(st.one_of(syntactic_sources(), valid_sources()))
    num_mutations = draw(st.integers(min_value=1, max_value=3))
    for _ in range(num_mutations):
        source = _mutate_source(source, draw)
    return source


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
        entrypoint = "nested/deep/test.dfn"
        middle_file = "nested/deep/middle.dfn"
        leaf_file = "nested/deep/leaf.dfn"
    else:
        entrypoint = "test.dfn"
        middle_file = "middle.dfn"
        leaf_file = "leaf.dfn"
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
        "test.dfn": _action_with_block(
            root_universe,
            "test.dfn",
            trigger_kind="constructor",
            outer_locals=[],
            inner_locals=[
                _local_position_with_used_constraints(
                    "first", [("position", "/target")], indent="        "
                ),
                _local_position_with_used_constraints(
                    "second", [("action", "/target")], indent="        "
                ),
            ],
            include_trigger_comment=True,
            include_action_close_comment=True,
        ),
        "target.dfn": _position_simple(root_universe, "target.dfn")
        + _action_simple(root_universe, "target.dfn"),
    }
    return ProjectCase(
        entrypoint="test.dfn",
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
        "test.dfn": _position_with_requirements(
            root_universe,
            "test.dfn",
            [("position", "/shared"), ("action", "/shared")],
        ),
        "shared.dfn": _position_simple(root_universe, "shared.dfn")
        + _action_simple(root_universe, "shared.dfn"),
    }
    return ProjectCase(
        entrypoint="test.dfn",
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
        "test.dfn": _position_with_requirements(
            root_universe,
            "test.dfn",
            [
                (
                    "position",
                    _global_name(child_universe, "target.dfn"),
                )
            ],
        )
    }
    child_files = {"target.dfn": _position_simple(child_universe, "target.dfn")}
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
        return ProjectCase(entrypoint="test.dfn", roots=tuple(roots))

    grandchild_universe = _VALID_GRANDCHILD_UNIVERSES[0]
    child_files["target.dfn"] = _position_with_requirements(
        child_universe,
        "target.dfn",
        [("position", _global_name(grandchild_universe, "leaf.dfn"))],
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
                files={"leaf.dfn": _position_simple(grandchild_universe, "leaf.dfn")},
                local_deps={},
            ),
        ]
    )
    return ProjectCase(entrypoint="test.dfn", roots=tuple(roots))


def _build_cross_fqun_action_statements_project(
    root_universe: str,
    child_universe: str,
) -> ProjectCase:
    root_files = {
        "test.dfn": _action_with_block(
            root_universe,
            "test.dfn",
            trigger_kind="constructor",
            outer_locals=[],
            inner_locals=[
                _local_position_with_used_constraints(
                    "inner_pos",
                    [("position", _global_name(child_universe, "target.dfn"))],
                    indent="        ",
                )
            ],
            blank_lines_in_blocks=True,
        )
    }
    child_files = {
        "target.dfn": _position_simple(child_universe, "target.dfn")
        + _action_simple(child_universe, "target.dfn")
    }
    return ProjectCase(
        entrypoint="test.dfn",
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


def _build_move_particle_project(root_universe: str) -> ProjectCase:
    root_files = {
        "test.dfn": _action_with_block(
            root_universe,
            "test.dfn",
            trigger_kind="constructor",
            outer_locals=[],
            inner_locals=[
                _local_position_simple("from_pos", indent="        "),
                _local_position_simple("to_pos", indent="        "),
                _create_particle_statement("position<from_pos>", indent="        "),
                _move_particle_statement(
                    "position<from_pos>", "position<to_pos>", indent="        "
                ),
            ],
        ),
    }
    return ProjectCase(
        entrypoint="test.dfn",
        roots=(ProjectRootCase("", root_universe, root_files, {}),),
    )


def _build_action_quality_implication_project(
    root_universe: str,
    child_universe: str,
) -> ProjectCase:
    target_global = _global_name(child_universe, "target.dfn")
    root_files = {
        "test.dfn": _action_with_block(
            root_universe,
            "test.dfn",
            trigger_kind="constructor",
            outer_locals=[],
            inner_locals=[
                _create_particle_statement(
                    f"action<{target_global}>::position<_noop>",
                    indent="        ",
                ),
            ],
            quality_implications=[("action", target_global)],
        )
    }
    child_files = {"target.dfn": _action_simple(child_universe, "target.dfn")}
    return ProjectCase(
        entrypoint="test.dfn",
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


def _build_destroy_particle_project(root_universe: str) -> ProjectCase:
    root_files = {
        "test.dfn": _action_with_block(
            root_universe,
            "test.dfn",
            trigger_kind="constructor",
            outer_locals=[],
            inner_locals=[
                _local_position_simple("destroy_pos", indent="        "),
                _create_particle_statement("position<destroy_pos>", indent="        "),
                _destroy_particle_statement("position<destroy_pos>", indent="        "),
            ],
        ),
    }
    return ProjectCase(
        entrypoint="test.dfn",
        roots=(ProjectRootCase("", root_universe, root_files, {}),),
    )


def _build_lifecycle_project(
    universe_name: str, *, repetitions: int, explicit_destruction: bool
) -> ProjectCase:
    child = "position</child>"
    files = {
        "child.dfn": _position_simple(universe_name, "child.dfn"),
        "initialize.dfn": _action_with_block(
            universe_name,
            "initialize.dfn",
            trigger_kind="constructor",
            quality_implications=[("position", "/child")],
            outer_locals=[],
            inner_locals=[_create_particle_statement(child, indent="        ")],
        ),
        "cleanup.dfn": _action_with_block(
            universe_name,
            "cleanup.dfn",
            trigger_kind="destructor",
            quality_implications=[("position", "/child")],
            outer_locals=[],
            inner_locals=[
                _local_position_simple("temporary", indent="        "),
                _move_particle_statement(
                    child, "position<temporary>", indent="        "
                ),
                _move_particle_statement(
                    "position<temporary>", child, indent="        "
                ),
            ],
        ),
        "relay.dfn": _join_lines(
            [
                f"define the potential action<{_global_name(universe_name, 'relay.dfn')}> {{",
                "    define the position<incoming>.",
                "    define the position<result>.",
                "    it happens when {",
                "        the position<incoming> has a particle.",
                "    } and it does {",
                "        move the particle in position<incoming> to position<result>.",
                "    }",
                "}",
            ]
        ),
    }
    statements = [
        _local_position_with_requirements(
            "item",
            [("action", "/initialize"), ("action", "/cleanup")],
            indent="        ",
        ),
        _create_particle_statement("position<item>", indent="        "),
    ]
    # Reusing the interface positions exercises guarantees across executions,
    # including qualities and destructors unknown to the relay's contract.
    for _ in range(repetitions):
        statements.extend(
            [
                _move_particle_statement(
                    "position<item>",
                    "action</relay>::position<incoming>",
                    indent="        ",
                ),
                _move_particle_statement(
                    "action</relay>::position<result>",
                    "position<item>",
                    indent="        ",
                ),
            ]
        )
    if explicit_destruction:
        statements.append(
            _destroy_particle_statement("position<item>", indent="        ")
        )
    files["test.dfn"] = _action_with_block(
        universe_name,
        "test.dfn",
        trigger_kind="constructor",
        quality_implications=[("action", "/relay")],
        outer_locals=[],
        inner_locals=statements,
    )
    return ProjectCase(
        entrypoint="test.dfn",
        roots=(ProjectRootCase("", universe_name, files, {}),),
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
                "action_quality_implication",
                "destroy_local",
                "lifecycle",
            ]
        )
    )
    if project_kind == "same_universe_chain":
        project_case = _build_same_universe_chain_project(
            root_universe, use_nested_entrypoint=False
        )
    elif project_kind == "same_universe_nested_chain":
        project_case = _build_same_universe_chain_project(
            root_universe, use_nested_entrypoint=True
        )
    elif project_kind == "action_local_constraints":
        project_case = _build_action_local_constraints_project(root_universe)
    elif project_kind == "dual_type_reference":
        project_case = _build_dual_type_reference_project(root_universe)
    elif project_kind == "cross_fqun":
        project_case = _build_cross_fqun_project(
            root_universe, child_universe, nested_child=False
        )
    elif project_kind == "cross_fqun_nested":
        project_case = _build_cross_fqun_project(
            root_universe, child_universe, nested_child=True
        )
    elif project_kind == "cross_fqun_action_statements":
        project_case = _build_cross_fqun_action_statements_project(
            root_universe, child_universe
        )
    elif project_kind == "move_local":
        project_case = _build_move_particle_project(root_universe)
    elif project_kind == "action_quality_implication":
        project_case = _build_action_quality_implication_project(
            root_universe, child_universe
        )
    elif project_kind == "lifecycle":
        project_case = _build_lifecycle_project(
            root_universe,
            repetitions=draw(st.integers(min_value=1, max_value=8)),
            explicit_destruction=draw(st.booleans()),
        )
    else:
        project_case = _build_destroy_particle_project(root_universe)
    if draw(st.booleans()):
        decorated_roots: list[ProjectRootCase] = []
        for root in project_case.roots:
            decorated_files = {
                path: draw(_decorated_source(content))
                for path, content in root.files.items()
            }
            decorated_roots.append(replace(root, files=decorated_files))
        project_case = ProjectCase(
            entrypoint=project_case.entrypoint,
            roots=tuple(decorated_roots),
        )
    return project_case


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
    num_mutations = draw(st.integers(min_value=1, max_value=3))
    for _ in range(num_mutations):
        project_case = _mutate_project_case(project_case, draw)
    return project_case


@pytest.fixture
def fuzz_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _setup_project(tmp_path, _PROJECT_FQUN)
    (tmp_path / "another_test.dfn").write_text(
        _action_simple(_PROJECT_FQUN, "another_test.dfn")
        + _position_simple(_PROJECT_FQUN, "another_test.dfn"),
        encoding="utf-8",
    )
    (tmp_path / "third_test.dfn").write_text(
        _action_simple(_PROJECT_FQUN, "third_test.dfn")
        + _position_simple(_PROJECT_FQUN, "third_test.dfn"),
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
    results: list[validation_result.FileValidationResult], source_hint: str
) -> None:
    for result in results:
        if result.diagnostics or result.exception is not None:
            pytest.fail(
                f"Expected clean validation results, got:\n{results!r}\n\nProject:\n{source_hint}",
                pytrace=False,
            )


def _assert_only_parser_syntax_exceptions(
    results: list[validation_result.FileValidationResult], source_hint: str
) -> None:
    allowed_exceptions = (
        parser_exceptions.DefineSyntaxError,
        exceptions.SourceFileNotFoundError,
    )
    for result in results:
        if result.exception is not None and not isinstance(
            result.exception, allowed_exceptions
        ):
            pytest.fail(
                f"Unclassified error: {result.exception!r}\n{result.exception!s}\n\nResults:\n{results!r}\n\nSource:\n{source_hint}",
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


_NAME_MARKER = "\x00NAME_MARKER\x00"


def _splice_name_bytes(template: str, name_bytes: bytes) -> bytes:
    before, after = template.split(_NAME_MARKER, 1)
    return before.encode() + name_bytes + after.encode()


@st.composite
def _random_name_bytes(draw: st.DrawFn) -> bytes:
    data = draw(st.binary(min_size=1, max_size=80))
    filtered = bytes(b for b in data if b not in (ord(">"), ord("\n"), ord("\r")))
    if not filtered:
        return b"x"
    return filtered


@st.composite
def _random_name_section_bytes(draw: st.DrawFn) -> bytes:
    data = draw(st.binary(min_size=1, max_size=20))
    filtered = bytes(
        b for b in data if b not in (ord(">"), ord("\n"), ord("\r"), ord(":"))
    )
    return filtered or b"x"


@st.composite
def _random_path_segment_bytes(draw: st.DrawFn) -> bytes:
    data = draw(st.binary(min_size=1, max_size=20))
    filtered = bytes(
        b for b in data if b not in (ord(">"), ord("\n"), ord("\r"), ord(":"), ord("/"))
    )
    return filtered or b"x"


_GLOBAL_NAME_CONTEXTS = [
    "position_def",
    "action_def",
    "constructor",
    "destructor",
    "position_req",
    "action_req",
    "create_ref",
    "move_from_ref",
    "move_to_ref",
    "destroy_ref",
    "trigger_ref",
    "quality_impl_position_def",
    "quality_impl_action_def",
]


def _global_name_context_template(context: str) -> str:
    if context in ("constructor", "destructor"):
        return _action_block_with_name(
            _NAME_MARKER,
            trigger_kind="constructor" if context == "constructor" else "destructor",
            outer_locals=[],
            inner_locals=[_local_position_simple("local", indent="        ")],
        )
    if context == "position_def":
        return f"define the potential position<{_NAME_MARKER}>.\n"
    if context == "action_def":
        return f"define the potential action<{_NAME_MARKER}> {{\n    define the position<_noop>.\n    it happens when {{\n        the position<_noop> has a particle.\n    }} and it does {{\n        define the position<__noop>.\n        create a particle in position<__noop>.\n    }}\n}}\n"
    if context == "position_req":
        return _position_with_requirements(
            _PROJECT_FQUN, "test.dfn", [("position", _NAME_MARKER)]
        )
    if context == "action_req":
        return _position_with_requirements(
            _PROJECT_FQUN, "test.dfn", [("action", _NAME_MARKER)]
        )
    if context == "create_ref":
        return _action_with_block(
            _PROJECT_FQUN,
            "test.dfn",
            outer_locals=[],
            inner_locals=[
                _create_particle_statement(
                    f"position<{_NAME_MARKER}>", indent="        "
                )
            ],
        )
    if context == "move_from_ref":
        return _action_with_block(
            _PROJECT_FQUN,
            "test.dfn",
            outer_locals=[
                _local_position_simple("from_pos", indent="    "),
                _local_position_simple("to_pos", indent="    "),
            ],
            inner_locals=[
                _create_particle_statement("position<from_pos>", indent="        "),
                _move_particle_statement(
                    f"position<{_NAME_MARKER}>",
                    "position<to_pos>",
                    indent="        ",
                ),
            ],
        )
    if context == "move_to_ref":
        return _action_with_block(
            _PROJECT_FQUN,
            "test.dfn",
            outer_locals=[
                _local_position_simple("from_pos", indent="    "),
            ],
            inner_locals=[
                _create_particle_statement("position<from_pos>", indent="        "),
                _move_particle_statement(
                    "position<from_pos>",
                    f"position<{_NAME_MARKER}>",
                    indent="        ",
                ),
            ],
        )
    if context == "destroy_ref":
        return _action_with_block(
            _PROJECT_FQUN,
            "test.dfn",
            outer_locals=[],
            inner_locals=[
                _destroy_particle_statement(
                    f"position<{_NAME_MARKER}>", indent="        "
                )
            ],
        )
    if context == "quality_impl_position_def":
        name = _global_name(_PROJECT_FQUN, "test.dfn")
        return (
            f"define the potential position<{name}> {{\n"
            f"    it also assigns the position<{_NAME_MARKER}>.\n"
            f"    it may only contain particles where {{\n"
            f"        it has the position<{_ANOTHER_VALID_PATH}>.\n"
            f"    }}\n"
            f"}}\n"
        )
    if context == "quality_impl_action_def":
        return _action_with_block(
            _PROJECT_FQUN,
            "test.dfn",
            outer_locals=[],
            inner_locals=[
                _create_particle_statement(
                    f"position<{_ANOTHER_VALID_PATH}>", indent="        "
                ),
            ],
            quality_implications=[("action", _NAME_MARKER)],
        )
    return _action_block_with_name(
        _global_name(_PROJECT_FQUN, "test.dfn"),
        outer_locals=[],
        inner_locals=[_create_particle_statement("position<run>", indent="        ")],
        trigger_condition_ref=f"position<{_NAME_MARKER}>",
    )


_LOCAL_NAME_CONTEXTS = [
    "local_def_simple",
    "local_def_constrained",
    "create_ref",
    "move_from_ref",
    "move_to_ref",
    "destroy_ref",
    "trigger_ref",
]


def _local_name_context_template(context: str) -> str:
    if context == "local_def_simple":
        return _action_with_block(
            _PROJECT_FQUN,
            "test.dfn",
            outer_locals=[f"    define the position<{_NAME_MARKER}>.\n"],
            inner_locals=[
                _create_particle_statement("position<run>", indent="        ")
            ],
        )
    if context == "local_def_constrained":
        return _action_with_block(
            _PROJECT_FQUN,
            "test.dfn",
            outer_locals=[
                _local_position_with_requirements(
                    _NAME_MARKER,
                    [("position", _ANOTHER_VALID_PATH)],
                    indent="    ",
                )
            ],
            inner_locals=[
                _create_particle_statement("position<run>", indent="        ")
            ],
        )
    if context == "create_ref":
        return _action_with_block(
            _PROJECT_FQUN,
            "test.dfn",
            outer_locals=[],
            inner_locals=[
                _create_particle_statement(
                    f"position<{_NAME_MARKER}>", indent="        "
                )
            ],
        )
    if context == "move_from_ref":
        return _action_with_block(
            _PROJECT_FQUN,
            "test.dfn",
            outer_locals=[
                _local_position_simple("from_pos", indent="    "),
                _local_position_simple("to_pos", indent="    "),
            ],
            inner_locals=[
                _create_particle_statement("position<from_pos>", indent="        "),
                _move_particle_statement(
                    f"position<{_NAME_MARKER}>",
                    "position<to_pos>",
                    indent="        ",
                ),
            ],
        )
    if context == "move_to_ref":
        return _action_with_block(
            _PROJECT_FQUN,
            "test.dfn",
            outer_locals=[
                _local_position_simple("from_pos", indent="    "),
            ],
            inner_locals=[
                _create_particle_statement("position<from_pos>", indent="        "),
                _move_particle_statement(
                    "position<from_pos>",
                    f"position<{_NAME_MARKER}>",
                    indent="        ",
                ),
            ],
        )
    if context == "destroy_ref":
        return _action_with_block(
            _PROJECT_FQUN,
            "test.dfn",
            outer_locals=[],
            inner_locals=[
                _destroy_particle_statement(
                    f"position<{_NAME_MARKER}>", indent="        "
                )
            ],
        )
    return _action_block_with_name(
        _global_name(_PROJECT_FQUN, "test.dfn"),
        outer_locals=[],
        inner_locals=[_create_particle_statement("position<run>", indent="        ")],
        trigger_condition_ref=f"position<{_NAME_MARKER}>",
    )


@st.composite
def _structured_random_global_name_bytes(draw: st.DrawFn) -> bytes:
    form = draw(
        st.sampled_from(
            ["path_only", "universe_path", "authority_universe_path", "full"]
        )
    )
    num_segments = draw(st.integers(min_value=1, max_value=3))
    path_segments = [draw(_random_path_segment_bytes()) for _ in range(num_segments)]
    path = b"/" + b"/".join(path_segments)
    if form == "path_only":
        return path
    universe = draw(
        st.one_of(
            st.sampled_from(_UNIVERSE_NAMES).map(str.encode),
            _random_name_section_bytes(),
        )
    )
    if form == "universe_path":
        return universe + b":" + path
    authority = draw(
        st.one_of(
            st.sampled_from(_AUTHORITY_DOMAINS).map(str.encode),
            _random_name_section_bytes(),
        )
    )
    if form == "authority_universe_path":
        return authority + b":" + universe + b":" + path
    multiverse = draw(
        st.one_of(
            st.sampled_from(_MULTIVERSE_NAMES).map(str.encode),
            _random_name_section_bytes(),
        )
    )
    return multiverse + b":" + authority + b":" + universe + b":" + path


@settings(
    deadline=None,
    database=None,
    max_examples=_EXAMPLES_VALID_SINGLE,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(source=valid_sources())
def test_valid_syntax_validates_cleanly(fuzz_project: Path, source: str):
    file_path = fuzz_project / "test.dfn"
    file_path.write_text(source, encoding="utf-8")
    d = driver.Driver(_PARSER)
    results = d.validate_program(Path("test.dfn")).program_validation.file_results
    _assert_results_are_clean(results, _escape_content(source))


@settings(
    deadline=None,
    database=None,
    max_examples=_EXAMPLES_VALID_PROJECTS,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(project_case=valid_project_cases())
@example(
    project_case=_build_lifecycle_project(
        _PROJECT_FQUN, repetitions=8, explicit_destruction=True
    )
)
@example(
    project_case=_build_lifecycle_project(
        _PROJECT_FQUN, repetitions=8, explicit_destruction=False
    )
)
def test_valid_projects_validate_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, project_case: ProjectCase
):
    _materialize_project_case(tmp_path, project_case)
    monkeypatch.chdir(tmp_path)

    d = driver.Driver(_PARSER)
    debug_source = _project_case_debug_text(project_case)
    results = d.validate_program(
        Path(project_case.entrypoint)
    ).program_validation.file_results
    _assert_results_are_clean(results, debug_source)


@settings(
    deadline=None,
    database=None,
    max_examples=_EXAMPLES_MUTATED_SINGLE,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(source=mutated_sources())
def test_mutated_syntax_no_unclassified_errors(fuzz_project: Path, source: str):
    (fuzz_project / "test.dfn").write_text(source, encoding="utf-8")
    d = driver.Driver(_PARSER)
    results = d.validate_program(Path("test.dfn")).program_validation.file_results
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
    d = driver.Driver(_PARSER)
    results = d.validate_program(
        Path(project_case.entrypoint)
    ).program_validation.file_results
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
    file_path = fuzz_project / "test.dfn"
    file_path.write_bytes(data)
    d = driver.Driver(_PARSER)
    results = d.validate_program(Path("test.dfn")).program_validation.file_results
    _assert_only_parser_syntax_exceptions(results, repr(data))


@settings(
    deadline=None,
    database=None,
    max_examples=_EXAMPLES_RANDOM_LOCAL_NAMES,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    name_bytes=_random_name_bytes(),
    context=st.sampled_from(_LOCAL_NAME_CONTEXTS),
)
def test_random_local_name_bytes_no_unclassified_errors(
    fuzz_project: Path, name_bytes: bytes, context: str
):
    template = _local_name_context_template(context)
    (fuzz_project / "test.dfn").write_bytes(_splice_name_bytes(template, name_bytes))
    d = driver.Driver(_PARSER)
    results = d.validate_program(Path("test.dfn")).program_validation.file_results
    _assert_only_parser_syntax_exceptions(results, repr(name_bytes))


@settings(
    deadline=None,
    database=None,
    max_examples=_EXAMPLES_RANDOM_GLOBAL_NAMES_RAW,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    name_bytes=_random_name_bytes(),
    context=st.sampled_from(_GLOBAL_NAME_CONTEXTS),
)
def test_random_global_name_raw_bytes_no_unclassified_errors(
    fuzz_project: Path, name_bytes: bytes, context: str
):
    template = _global_name_context_template(context)
    (fuzz_project / "test.dfn").write_bytes(_splice_name_bytes(template, name_bytes))
    d = driver.Driver(_PARSER)
    results = d.validate_program(Path("test.dfn")).program_validation.file_results
    _assert_only_parser_syntax_exceptions(results, repr(name_bytes))


@settings(
    deadline=None,
    database=None,
    max_examples=_EXAMPLES_RANDOM_GLOBAL_NAMES_STRUCTURED,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    name_bytes=_structured_random_global_name_bytes(),
    context=st.sampled_from(_GLOBAL_NAME_CONTEXTS),
)
def test_random_global_name_structured_bytes_no_unclassified_errors(
    fuzz_project: Path, name_bytes: bytes, context: str
):
    template = _global_name_context_template(context)
    (fuzz_project / "test.dfn").write_bytes(_splice_name_bytes(template, name_bytes))
    d = driver.Driver(_PARSER)
    results = d.validate_program(Path("test.dfn")).program_validation.file_results
    _assert_only_parser_syntax_exceptions(results, repr(name_bytes))
