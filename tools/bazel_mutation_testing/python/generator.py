"""List Python mutants with mutmut's mutation operators."""

from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING, NamedTuple, cast

import libcst
from libcst import metadata
from mutmut.mutation import (
    file_mutation,
    mutators,
    pragma_handling,
    trampoline_templates,
)
from mutmut.utils import format_utils

from tools.bazel_mutation_testing import mutant

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

# Lines of unchanged context around each change, as in `diff -u`.
_CONTEXT_LINES = 3
# A mutant's name shows the code it replaces, and the replacement, whole when
# both are at most this many characters long.
_SNIPPET_LENGTH = 60
# Otherwise it shows each one's changed part, with this many unchanged
# characters on each side.
_CHANGE_CONTEXT = 15


class _Function(NamedTuple):
    """A function that mutmut mutates, and where its code is in the file."""

    owner: libcst.ClassDef | None
    """The class whose method the function is."""
    base_line: int
    """The 0-based index of the file line that the first line of the function's
    code from `_code` corresponds to."""


def _lines(text: str) -> list[str]:
    # str.splitlines also splits at characters such as form feeds, which
    # unified diffs do not treat as line ends. The formatter ends every file
    # with a line end.
    return [line + "\n" for line in text.split("\n")[:-1]]


def _line_count(module: libcst.Module, node: libcst.CSTNode) -> int:
    return module.code_for_node(node).count("\n")


def _functions(module: libcst.Module) -> dict[libcst.FunctionDef, _Function]:
    """Return where each function that mutmut mutates is.

    mutmut mutates the functions at the top of the module, and the methods of
    the classes there.
    """
    line = sum(_line_count(module, empty) for empty in module.header)
    functions: dict[libcst.FunctionDef, _Function] = {}
    for node in module.body:
        if isinstance(node, libcst.FunctionDef):
            functions[node] = _Function(owner=None, base_line=line)
        elif isinstance(node, libcst.ClassDef) and isinstance(
            node.body, libcst.IndentedBlock
        ):
            # A method's `_code` starts with its class's own lines, as the
            # class's code does, but it leaves out the class's earlier
            # children. So the first line of a method's `_code` corresponds to
            # the class's first line plus the lines of those children.
            method_line = line
            for child in node.body.body:
                if isinstance(child, libcst.FunctionDef):
                    functions[child] = _Function(owner=node, base_line=method_line)
                method_line += _line_count(module, child)
        line += _line_count(module, node)
    return functions


def _code(
    module: libcst.Module, function: libcst.FunctionDef, owner: libcst.ClassDef | None
) -> str:
    """Return the code of `function`, after its class's own lines for a method.

    A method's code needs its class, which indents it. Rendering a class with
    only the method costs far less than rendering the whole class.
    """
    if owner is None:
        return module.code_for_node(function)
    body = cast("libcst.IndentedBlock", owner.body)
    return module.code_for_node(
        owner.with_changes(body=body.with_changes(body=[function], footer=()))
    )


def _common_prefix_length(first: Sequence[str], second: Sequence[str]) -> int:
    length = 0
    while length < min(len(first), len(second)) and first[length] == second[length]:
        length += 1
    return length


def _patch(
    path: str, lines: list[str], base_line: int, old_code: str, new_code: str
) -> str:
    """Return a patch that changes `old_code` to `new_code` in the file's `lines`.

    Line `base_line` of the file is the first line of `old_code`.
    """
    old = _lines(old_code)
    new = _lines(new_code)
    prefix_length = _common_prefix_length(old, new)
    suffix_length = _common_prefix_length(
        old[prefix_length:][::-1], new[prefix_length:][::-1]
    )
    removed = old[prefix_length : len(old) - suffix_length]
    added = new[prefix_length : len(new) - suffix_length]
    change_start = base_line + prefix_length
    change_end = change_start + len(removed)
    hunk_start = max(0, change_start - _CONTEXT_LINES)
    hunk_end = min(len(lines), change_end + _CONTEXT_LINES)
    before = lines[hunk_start:change_start]
    after = lines[change_end:hunk_end]
    old_count = len(before) + len(removed) + len(after)
    new_count = len(before) + len(added) + len(after)
    return "".join(
        [
            f"--- a/{path}\n",
            f"+++ b/{path}\n",
            f"@@ -{hunk_start + 1},{old_count} +{hunk_start + 1},{new_count} @@\n",
            *[f" {line}" for line in before],
            *[f"-{line}" for line in removed],
            *[f"+{line}" for line in added],
            *[f" {line}" for line in after],
        ]
    )


def _excerpt(code: str, start: int, end: int) -> str:
    """Return `code[start:end]`, marking each end that leaves code out.

    The excerpt ends early to keep it within `_SNIPPET_LENGTH` characters.
    """
    end = min(end, start + _SNIPPET_LENGTH)
    return (
        ("..." if start > 0 else "")
        + code[start:end]
        + ("..." if end < len(code) else "")
    )


def _replacement(module: libcst.Module, mutation: file_mutation.Mutation) -> str:
    """Return the replacement that a mutant's name describes."""
    old = " ".join(module.code_for_node(mutation.original_node).split())
    new = " ".join(module.code_for_node(mutation.mutated_node).split())
    if len(old) <= _SNIPPET_LENGTH and len(new) <= _SNIPPET_LENGTH:
        return f"replace {old} with {new}"
    prefix_length = _common_prefix_length(old, new)
    suffix_length = _common_prefix_length(
        old[prefix_length:][::-1], new[prefix_length:][::-1]
    )
    start = max(0, prefix_length - _CHANGE_CONTEXT)
    old_end = min(len(old), len(old) - suffix_length + _CHANGE_CONTEXT)
    new_end = min(len(new), len(new) - suffix_length + _CHANGE_CONTEXT)
    return (
        f"replace {_excerpt(old, start, old_end)} "
        + f"with {_excerpt(new, start, new_end)}"
    )


def _mutmut_name(
    path: str,
    function: libcst.FunctionDef,
    owner: libcst.ClassDef | None,
    number: int,
) -> str:
    mangled_name = trampoline_templates.mangle_function_name(
        name=function.name.value, class_name=owner.name.value if owner else None
    )
    return format_utils.get_mutant_name(
        pathlib.Path(path), f"{mangled_name}__mutmut_{number}"
    )


def _ignored_code(
    path: str, wrapper: metadata.MetadataWrapper
) -> pragma_handling.IgnoredCode:
    """Return the code that the file's `# pragma: no mutate` comments exclude."""
    # mutmut's get_ignored_lines also reads mutmut's configuration, which the
    # repository does not have, so the tester reads only the pragmas.
    pragmas = pragma_handling.PragmaVisitor(path)
    _ = wrapper.visit(pragmas)
    return pragma_handling.IgnoredCode(
        no_mutate_lines=pragmas.no_mutate_lines,
        ignore_node_lines=pragmas.ignore_node_lines,
        ignore_pattern_lines=set(),
    )


def _file_mutants(path: str, code: str) -> list[mutant.Mutant]:
    wrapper = metadata.MetadataWrapper(libcst.parse_module(code))
    module = wrapper.module
    visitor = file_mutation.MutationVisitor(
        mutators.mutation_operators, _ignored_code(path, wrapper)
    )
    _ = wrapper.visit(visitor)
    positions = wrapper.resolve(metadata.PositionProvider)
    functions = _functions(module)
    lines = _lines(code)
    original_code: dict[libcst.FunctionDef, str] = {}
    mutant_counts: dict[libcst.FunctionDef, int] = {}
    mutants: list[mutant.Mutant] = []
    for mutation in visitor.mutations:
        function = mutation.contained_by_top_level_function
        # mutmut leaves out mutations outside the functions it mutates.
        if function is None or function not in functions:
            continue
        located = functions[function]
        if function not in original_code:
            original_code[function] = _code(module, function, located.owner)
        # mutmut numbers each function's mutants from 1, in the order its
        # visitor finds them.
        number = mutant_counts.get(function, 0) + 1
        mutant_counts[function] = number
        # Replacing a node inside a function gives a function.
        mutated_function = cast(
            "libcst.FunctionDef",
            file_mutation.deep_replace(
                function, mutation.original_node, mutation.mutated_node
            ),
        )
        position = positions[mutation.original_node].start
        mutants.append(
            mutant.Mutant(
                name=f"{path}:{position.line}:{position.column + 1}: "
                + f"{_replacement(module, mutation)} "
                + f"({_mutmut_name(path, function, located.owner, number)})",
                path=path,
                # Coverage records the statement that holds the line.
                lines=(position.line, position.line),
                patch=_patch(
                    path,
                    lines,
                    located.base_line,
                    original_code[function],
                    _code(module, mutated_function, located.owner),
                ),
            )
        )
    return mutants


def list_mutants(
    paths: Iterable[str],
    *,
    workspace: pathlib.Path,
    tracked_paths: frozenset[str],
) -> list[mutant.Mutant]:
    """Return the mutants of the sources at `paths` that are in `tracked_paths`."""
    mutants: list[mutant.Mutant] = []
    for path in paths:
        if path in tracked_paths:
            code = (workspace / path).read_text(encoding="utf-8")
            mutants.extend(_file_mutants(path, code))
    return mutants
