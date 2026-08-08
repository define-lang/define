"""Generate Define source that stresses modular destruction fragments."""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from tools.generators import generator_cli, generator_io

if TYPE_CHECKING:
    from pathlib import Path

DEFAULT_FQUN_PREFIX = "mv:define-lang.org:destruction_fragments"
DEFAULT_CALLERS = 24
DEFAULT_CALL_DEPTH = 40
DEFAULT_PASS_THROUGH_ACTIONS = 1
DEFAULT_LOCAL_CHILDREN = 3
DEFAULT_REPETITIONS = 2

_INDENT = "    "
_INNER_INDENT = "        "
_DEEP_INDENT = "            "


def _qualified(prefix: str, path: str) -> str:
    return f"{prefix}:{path}"


def _child_path(
    caller: int,
    stage: int,
    child: int,
    *,
    shared_child_paths: bool,
) -> str:
    caller_part = "" if shared_child_paths else f"caller_{caller}_"
    return f"/fragment_child_{caller_part}{stage}_{child}"


def _stage_path(caller: int, stage: int) -> str:
    return f"/caller_{caller}/stage_{stage}"


def _pass_path(caller: int, stage: int, index: int) -> str:
    return f"/caller_{caller}/pass_{stage}_{index}"


def _root_paths(
    caller: int,
    first_stage: int,
    call_depth: int,
    local_children: int,
    *,
    shared_child_paths: bool,
) -> list[str]:
    return [
        _child_path(
            caller,
            stage,
            child,
            shared_child_paths=shared_child_paths,
        )
        for stage in range(first_stage, call_depth)
        for child in range(local_children)
    ]


def _emit_position(position_name: str, child_paths: list[str]) -> list[str]:
    if not child_paths:
        return [f"{_INDENT}define the position<{position_name}>."]
    lines = [
        f"{_INDENT}define the position<{position_name}> {{",
        f"{_INNER_INDENT}it may only contain particles where {{",
    ]
    lines.extend(
        f"{_DEEP_INDENT}it has the position<{child_path}>."
        for child_path in child_paths
    )
    lines.extend([f"{_INNER_INDENT}}}", f"{_INDENT}}}"])
    return lines


def _emit_child_positions(
    prefix: str,
    callers: int,
    call_depth: int,
    local_children: int,
    *,
    shared_child_paths: bool,
) -> list[str]:
    lines: list[str] = []
    caller_range = range(1) if shared_child_paths else range(callers)
    for caller in caller_range:
        for stage in range(call_depth):
            for child in range(local_children):
                path = _child_path(
                    caller,
                    stage,
                    child,
                    shared_child_paths=shared_child_paths,
                )
                lines.append(
                    f"define the potential position<{_qualified(prefix, path)}>."
                )
    lines.append("")
    return lines


def _emit_destroyer(prefix: str) -> list[str]:
    return [
        f"define the potential action<{_qualified(prefix, '/destroyer')}> {{",
        f"{_INDENT}define the position<run>.",
        f"{_INDENT}it happens when {{",
        f"{_INNER_INDENT}the position<run> has a particle.",
        f"{_INDENT}}} and it does {{",
        f"{_INNER_INDENT}destroy the particle in position<run>.",
        f"{_INDENT}}}",
        "}",
        "",
    ]


def _stage_next_action(
    caller: int,
    stage: int,
    call_depth: int,
    pass_through_actions: int,
) -> str:
    if pass_through_actions:
        return _pass_path(caller, stage, 0)
    if stage + 1 < call_depth:
        return _stage_path(caller, stage + 1)
    return "/destroyer"


def _emit_stage(
    prefix: str,
    caller: int,
    stage: int,
    call_depth: int,
    pass_through_actions: int,
    local_children: int,
    *,
    shared_child_paths: bool,
) -> list[str]:
    next_action = _stage_next_action(caller, stage, call_depth, pass_through_actions)
    remaining_roots = _root_paths(
        caller,
        stage,
        call_depth,
        local_children,
        shared_child_paths=shared_child_paths,
    )
    action_path = _stage_path(caller, stage)
    lines = [
        f"define the potential action<{_qualified(prefix, action_path)}> {{",
        f"{_INDENT}it also assigns the action<{next_action}>.",
    ]
    lines.extend(_emit_position("run", remaining_roots))
    lines.extend(
        [
            f"{_INDENT}it happens when {{",
            f"{_INNER_INDENT}the position<run> has a particle.",
            f"{_INDENT}}} and it does {{",
        ]
    )
    for child in range(local_children):
        child_path = _child_path(
            caller,
            stage,
            child,
            shared_child_paths=shared_child_paths,
        )
        lines.append(
            f"{_INNER_INDENT}create a particle in position<run>::position<{child_path}>."
        )
    lines.extend(
        [
            f"{_INNER_INDENT}move the particle in position<run> to action<{next_action}>::position<run>.",
            f"{_INDENT}}}",
            "}",
            "",
        ]
    )
    return lines


def _emit_pass_through(
    prefix: str,
    caller: int,
    stage: int,
    index: int,
    call_depth: int,
    pass_through_actions: int,
    local_children: int,
    *,
    shared_child_paths: bool,
) -> list[str]:
    if index + 1 < pass_through_actions:
        next_action = _pass_path(caller, stage, index + 1)
    elif stage + 1 < call_depth:
        next_action = _stage_path(caller, stage + 1)
    else:
        next_action = "/destroyer"
    remaining_roots = _root_paths(
        caller,
        stage + 1,
        call_depth,
        local_children,
        shared_child_paths=shared_child_paths,
    )
    action_path = _pass_path(caller, stage, index)
    lines = [
        f"define the potential action<{_qualified(prefix, action_path)}> {{",
        f"{_INDENT}it also assigns the action<{next_action}>.",
    ]
    lines.extend(_emit_position("run", remaining_roots))
    lines.extend(
        [
            f"{_INDENT}it happens when {{",
            f"{_INNER_INDENT}the position<run> has a particle.",
            f"{_INDENT}}} and it does {{",
            f"{_INNER_INDENT}move the particle in position<run> to action<{next_action}>::position<run>.",
            f"{_INDENT}}}",
            "}",
            "",
        ]
    )
    return lines


def _emit_entry_point(
    prefix: str,
    callers: int,
    call_depth: int,
    local_children: int,
    repetitions: int,
    *,
    shared_child_paths: bool,
) -> list[str]:
    lines = [f"define the potential action<{_qualified(prefix, '/test')}> {{"]
    for caller in range(callers):
        first_action = _stage_path(caller, 0)
        lines.append(f"{_INDENT}it also assigns the action<{first_action}>.")
    lines.extend(
        [
            f"{_INDENT}it happens when {{",
            f"{_INNER_INDENT}this particle is created.",
            f"{_INDENT}}} and it does {{",
        ]
    )
    for caller in range(callers):
        roots = _root_paths(
            caller,
            0,
            call_depth,
            local_children,
            shared_child_paths=shared_child_paths,
        )
        for repetition in range(repetitions):
            source_name = f"source_{caller}_{repetition}"
            lines.extend(
                [
                    f"{_INNER_INDENT}define the position<{source_name}> {{",
                    f"{_DEEP_INDENT}it may only contain particles where {{",
                ]
            )
            lines.extend(
                f"{_DEEP_INDENT}{_INDENT}it has the position<{root}>." for root in roots
            )
            first_action = _stage_path(caller, 0)
            lines.extend(
                [
                    f"{_DEEP_INDENT}}}",
                    f"{_INNER_INDENT}}}",
                    f"{_INNER_INDENT}create a particle in position<{source_name}>.",
                    f"{_INNER_INDENT}move the particle in position<{source_name}> to action<{first_action}>::position<run>.",
                ]
            )
    lines.extend([f"{_INDENT}}}", "}", ""])
    return lines


def generate_source_lines(
    callers: int = DEFAULT_CALLERS,
    call_depth: int = DEFAULT_CALL_DEPTH,
    pass_through_actions: int = DEFAULT_PASS_THROUGH_ACTIONS,
    local_children: int = DEFAULT_LOCAL_CHILDREN,
    repetitions: int = DEFAULT_REPETITIONS,
    *,
    shared_child_paths: bool = False,
    fqun_prefix: str = DEFAULT_FQUN_PREFIX,
) -> list[str]:
    """Return a real Define workload for destruction-fragment compilation."""
    positive_parameters = {
        "callers": callers,
        "call_depth": call_depth,
        "local_children": local_children,
        "repetitions": repetitions,
    }
    for name, value in positive_parameters.items():
        if value < 1:
            raise ValueError(f"{name} must be at least 1, got {value}")
    if pass_through_actions < 0:
        raise ValueError(
            f"pass_through_actions must be at least 0, got {pass_through_actions}"
        )

    lines = ["# Generated Define source. Modular destruction-fragment workload.", ""]
    lines.extend(
        _emit_child_positions(
            fqun_prefix,
            callers,
            call_depth,
            local_children,
            shared_child_paths=shared_child_paths,
        )
    )
    lines.extend(_emit_destroyer(fqun_prefix))
    for caller in range(callers):
        for stage in reversed(range(call_depth)):
            for index in reversed(range(pass_through_actions)):
                lines.extend(
                    _emit_pass_through(
                        fqun_prefix,
                        caller,
                        stage,
                        index,
                        call_depth,
                        pass_through_actions,
                        local_children,
                        shared_child_paths=shared_child_paths,
                    )
                )
            lines.extend(
                _emit_stage(
                    fqun_prefix,
                    caller,
                    stage,
                    call_depth,
                    pass_through_actions,
                    local_children,
                    shared_child_paths=shared_child_paths,
                )
            )
    lines.extend(
        _emit_entry_point(
            fqun_prefix,
            callers,
            call_depth,
            local_children,
            repetitions,
            shared_child_paths=shared_child_paths,
        )
    )
    return lines


def write_to_path(
    output: Path,
    callers: int = DEFAULT_CALLERS,
    call_depth: int = DEFAULT_CALL_DEPTH,
    pass_through_actions: int = DEFAULT_PASS_THROUGH_ACTIONS,
    local_children: int = DEFAULT_LOCAL_CHILDREN,
    repetitions: int = DEFAULT_REPETITIONS,
    *,
    shared_child_paths: bool = False,
    fqun_prefix: str = DEFAULT_FQUN_PREFIX,
) -> int:
    """Write generated source to ``output`` and return its line count."""
    return generator_io.write_lines(
        output,
        generate_source_lines(
            callers=callers,
            call_depth=call_depth,
            pass_through_actions=pass_through_actions,
            local_children=local_children,
            repetitions=repetitions,
            shared_child_paths=shared_child_paths,
            fqun_prefix=fqun_prefix,
        ),
    )


@click.command()
@click.option(
    "--output", type=generator_cli.OUTPUT_FILE, required=True, help="Generated file."
)
@click.option(
    "--callers",
    type=generator_cli.POSITIVE_INTEGER,
    default=DEFAULT_CALLERS,
    show_default=True,
    help="Independent caller chains that share the destroying action.",
)
@click.option(
    "--call-depth",
    type=generator_cli.POSITIVE_INTEGER,
    default=DEFAULT_CALL_DEPTH,
    show_default=True,
    help="Actions contributing occupied children along each caller chain.",
)
@click.option(
    "--pass-through-actions",
    type=generator_cli.NONNEGATIVE_INTEGER,
    default=DEFAULT_PASS_THROUGH_ACTIONS,
    show_default=True,
    help="Actions adding no executable behavior after each contributor.",
)
@click.option(
    "--local-children",
    type=generator_cli.POSITIVE_INTEGER,
    default=DEFAULT_LOCAL_CHILDREN,
    show_default=True,
    help="Occupied child destructions contributed by each action.",
)
@click.option(
    "--repetitions",
    type=generator_cli.POSITIVE_INTEGER,
    default=DEFAULT_REPETITIONS,
    show_default=True,
    help="Executions of every caller chain.",
)
@click.option(
    "--shared-child-paths/--disjoint-child-paths",
    default=False,
    show_default=True,
    help="Reuse child-position qualities across callers or give each caller its own.",
)
@click.option(
    "--fqun-prefix",
    default=DEFAULT_FQUN_PREFIX,
    show_default=True,
    help="Universe prefix for every definition.",
)
def main(
    output: Path,
    callers: int,
    call_depth: int,
    pass_through_actions: int,
    local_children: int,
    repetitions: int,
    *,
    shared_child_paths: bool,
    fqun_prefix: str,
):
    """Generate a real Define workload for modular destruction fragments.

    Each caller chain adds occupied child paths at every contributing action,
    interleaves optional actions that add no executable work, and converges on one
    reusable destroying action. Repetitions execute the same chains again. Use the
    shared-path flag to compare shared and disjoint caller path shapes.
    """
    written = generator_cli.invoke(
        lambda: write_to_path(
            output,
            callers=callers,
            call_depth=call_depth,
            pass_through_actions=pass_through_actions,
            local_children=local_children,
            repetitions=repetitions,
            shared_child_paths=shared_child_paths,
            fqun_prefix=fqun_prefix,
        )
    )
    generator_cli.report_written("lines", written, output)


if __name__ == "__main__":
    main()
