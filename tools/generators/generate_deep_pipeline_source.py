"""Generate a Define source file with deep, independent processing pipelines.

Emits a single ``.dfn`` that compiles to zero diagnostics, whose shape drives
Action Requirements up through long chains of callers rather than stressing
parse volume or graph density.

Each pipeline is one application workflow:

  * The entry-point action prepares one work particle for each pipeline.
  * Each processing action moves that particle into the next action's interface
    position and triggers it, so a requirement inferred at the deepest stage
    propagates back through every caller above it.
  * The final action moves the work particle and destroys its temporary child
    particle.
  * Optionally, each action also passes positions with set values to the next,
    and the final action reads them, so value requirements propagate too.
  * Optionally, the work particle has a destructor that reads a value of the
    particle being destroyed, so destructor requirements propagate too.

Pipelines are independent because a large program contains many workflows of
similar structure with separately specialized actions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import click

from tools.generators import generator_cli, generator_io

if TYPE_CHECKING:
    from pathlib import Path

DEFAULT_FQUN_PREFIX = "mv:define-lang.org:deep_pipeline"
DEFAULT_PIPELINES = 64
DEFAULT_PROCESSING_STAGES = 72

_MIN_PIPELINES = 1
_MIN_PROCESSING_STAGES = 1
_OUTER_INDENT = "    "
_INNER_INDENT = "        "
_DEEP_INDENT = "            "
_DEEPEST_INDENT = "                "

_TEMPORARY_METADATA_POSITION = "/temporary_metadata"
_AUDIT_DESTRUCTOR = "/audit_record"
_AUDIT_KEEPER = "/keep_audit"
_AUDIT_READING_POSITION = "/audit_reading"
_AUDIT_KEPT_POSITION = "/audit_kept"
_VALUE_QUALITY = "value<standard:/number/natural>"


def _action_path(kind: str, pipeline: int, stage: int | None = None) -> str:
    pipeline_path = f"/pipeline_{pipeline}"
    if stage is None:
        return f"{pipeline_path}/{kind}"
    return f"{pipeline_path}/{kind}_{stage}"


def _qualified(prefix: str, path: str) -> str:
    return f"{prefix}:{path}"


def _record_position(name: str, *, destructor_reads: bool) -> list[str]:
    lines = [
        f"{_OUTER_INDENT}define the position<{name}> {{",
        f"{_INNER_INDENT}it may only contain particles where {{",
        f"{_DEEP_INDENT}it has the position<{_TEMPORARY_METADATA_POSITION}>.",
    ]
    if destructor_reads:
        lines.append(f"{_DEEP_INDENT}it has the action<{_AUDIT_DESTRUCTOR}>.")
    lines.extend([f"{_INNER_INDENT}}}", f"{_OUTER_INDENT}}}"])
    return lines


def _value_positions(values_per_stage: int) -> list[str]:
    lines: list[str] = []
    for value in range(values_per_stage):
        lines.extend(
            [
                f"{_OUTER_INDENT}define the position<value_{value}> {{",
                f"{_INNER_INDENT}it may only contain particles where {{",
                f"{_DEEP_INDENT}it has the {_VALUE_QUALITY}.",
                f"{_INNER_INDENT}}}",
                f"{_OUTER_INDENT}}}",
            ]
        )
    return lines


def _move_values(callee_position: str, values_per_stage: int) -> list[str]:
    lines: list[str] = []
    for value in range(values_per_stage):
        lines.append(
            f"{_INNER_INDENT}move the particle in position<value_{value}> to {callee_position}::position<value_{value}>."
        )
    return lines


def _emit_global_positions(
    prefix: str, values_per_stage: int, *, destructor_reads: bool
) -> list[str]:
    lines = [
        f"define the potential position<{_qualified(prefix, _TEMPORARY_METADATA_POSITION)}>.",
        "",
    ]
    value_positions = [f"/kept_{value}" for value in range(values_per_stage)]
    if destructor_reads:
        value_positions.extend((_AUDIT_READING_POSITION, _AUDIT_KEPT_POSITION))
    for path in value_positions:
        lines.extend(
            [
                f"define the potential position<{_qualified(prefix, path)}> {{",
                f"{_OUTER_INDENT}it may only contain particles where {{",
                f"{_INNER_INDENT}it has the {_VALUE_QUALITY}.",
                f"{_OUTER_INDENT}}}",
                "}",
                "",
            ]
        )
    return lines


def _emit_audit_actions(prefix: str) -> list[str]:
    return [
        f"define the potential action<{_qualified(prefix, _AUDIT_KEEPER)}> {{",
        f"{_OUTER_INDENT}it also assigns the position<{_AUDIT_KEPT_POSITION}>.",
        f"{_OUTER_INDENT}define the position<run>.",
        f"{_OUTER_INDENT}define the position<input> {{",
        f"{_INNER_INDENT}it may only contain particles where {{",
        f"{_DEEP_INDENT}it has the {_VALUE_QUALITY}.",
        f"{_INNER_INDENT}}}",
        f"{_OUTER_INDENT}}}",
        f"{_OUTER_INDENT}it happens when {{",
        f"{_INNER_INDENT}the position<run> has a particle.",
        f"{_OUTER_INDENT}}} and it does {{",
        f"{_INNER_INDENT}create a particle in position<{_AUDIT_KEPT_POSITION}>.",
        f"{_INNER_INDENT}set the value of position<{_AUDIT_KEPT_POSITION}> from position<input>.",
        f"{_INNER_INDENT}destroy the particle in position<input>.",
        f"{_INNER_INDENT}destroy the particle in position<run>.",
        f"{_OUTER_INDENT}}}",
        "}",
        "",
        f"define the potential action<{_qualified(prefix, _AUDIT_DESTRUCTOR)}> {{",
        f"{_OUTER_INDENT}it also assigns the position<{_AUDIT_READING_POSITION}>.",
        f"{_OUTER_INDENT}it happens when {{",
        f"{_INNER_INDENT}this particle is being destroyed.",
        f"{_OUTER_INDENT}}} and it does {{",
        f"{_INNER_INDENT}define the position<reader> {{",
        f"{_DEEP_INDENT}it may only contain particles where {{",
        f"{_DEEPEST_INDENT}it has the action<{_AUDIT_KEEPER}>.",
        f"{_DEEP_INDENT}}}",
        f"{_INNER_INDENT}}}",
        f"{_INNER_INDENT}create a particle in position<reader>.",
        f"{_INNER_INDENT}create a particle in position<reader>::action<{_AUDIT_KEEPER}>::position<input>.",
        f"{_INNER_INDENT}set the value of position<reader>::action<{_AUDIT_KEEPER}>::position<input> from position<{_AUDIT_READING_POSITION}>.",
        f"{_INNER_INDENT}create a particle in position<reader>::action<{_AUDIT_KEEPER}>::position<run>.",
        f"{_OUTER_INDENT}}}",
        "}",
        "",
    ]


def _emit_header() -> list[str]:
    return [
        "# Generated Define source. Deep, independent processing pipelines.",
        "",
    ]


def _emit_finalizer(
    prefix: str, pipeline: int, values_per_stage: int, *, destructor_reads: bool
) -> list[str]:
    action_name = _qualified(prefix, _action_path("finalize_record", pipeline))
    lines = [f"define the potential action<{action_name}> {{"]
    for value in range(values_per_stage):
        lines.append(f"{_OUTER_INDENT}it also assigns the position</kept_{value}>.")
    lines.append(f"{_OUTER_INDENT}define the position<start>.")
    lines.extend(_record_position("pending_record", destructor_reads=destructor_reads))
    lines.extend(
        _record_position("completed_record", destructor_reads=destructor_reads)
    )
    lines.extend(_value_positions(values_per_stage))
    lines.extend(
        [
            f"{_OUTER_INDENT}it happens when {{",
            f"{_INNER_INDENT}the position<start> has a particle.",
            f"{_OUTER_INDENT}}} and it does {{",
            f"{_INNER_INDENT}move the particle in position<pending_record> to position<completed_record>.",
            f"{_INNER_INDENT}destroy the particle in position<completed_record>::position<{_TEMPORARY_METADATA_POSITION}>.",
        ]
    )
    if destructor_reads:
        lines.append(
            f"{_INNER_INDENT}destroy the particle in position<completed_record>."
        )
    for value in range(values_per_stage):
        lines.extend(
            (
                f"{_INNER_INDENT}create a particle in position</kept_{value}>.",
                f"{_INNER_INDENT}set the value of position</kept_{value}> from position<value_{value}>.",
                f"{_INNER_INDENT}destroy the particle in position<value_{value}>.",
            )
        )
    lines.extend(
        [
            f"{_INNER_INDENT}destroy the particle in position<start>.",
            f"{_OUTER_INDENT}}}",
            "}",
            "",
        ]
    )
    return lines


def _emit_record_preparer(
    prefix: str, pipeline: int, values_per_stage: int, *, destructor_reads: bool
) -> list[str]:
    action_name = _qualified(prefix, _action_path("prepare_record", pipeline))
    finalizer = _action_path("finalize_record", pipeline)
    return [
        f"define the potential action<{action_name}> {{",
        f"{_OUTER_INDENT}define the position<start>.",
        *_record_position("record", destructor_reads=destructor_reads),
        *_value_positions(values_per_stage),
        f"{_OUTER_INDENT}it happens when {{",
        f"{_INNER_INDENT}the position<start> has a particle.",
        f"{_OUTER_INDENT}}} and it does {{",
        f"{_INNER_INDENT}define the position<record_processing> {{",
        f"{_DEEP_INDENT}it may only contain particles where {{",
        f"{_DEEPEST_INDENT}it has the action<{finalizer}>.",
        f"{_DEEP_INDENT}}}",
        f"{_INNER_INDENT}}}",
        f"{_INNER_INDENT}create a particle in position<record_processing>.",
        f"{_INNER_INDENT}move the particle in position<record> to position<record_processing>::action<{finalizer}>::position<pending_record>.",
        *_move_values(
            f"position<record_processing>::action<{finalizer}>", values_per_stage
        ),
        f"{_INNER_INDENT}create a particle in position<record_processing>::action<{finalizer}>::position<start>.",
        f"{_INNER_INDENT}destroy the particle in position<start>.",
        f"{_OUTER_INDENT}}}",
        "}",
        "",
    ]


def _emit_processing_stage(  # noqa: PLR0913 - Each stage shape is independent.
    prefix: str,
    pipeline: int,
    stage: int,
    next_action: str,
    values_per_stage: int,
    *,
    destructor_reads: bool,
) -> list[str]:
    action_name = _qualified(prefix, _action_path("process_stage", pipeline, stage))
    return [
        f"define the potential action<{action_name}> {{",
        f"{_OUTER_INDENT}define the position<start>.",
        *_record_position("record", destructor_reads=destructor_reads),
        *_value_positions(values_per_stage),
        f"{_OUTER_INDENT}it happens when {{",
        f"{_INNER_INDENT}the position<start> has a particle.",
        f"{_OUTER_INDENT}}} and it does {{",
        f"{_INNER_INDENT}define the position<next_processing_stage> {{",
        f"{_DEEP_INDENT}it may only contain particles where {{",
        f"{_DEEPEST_INDENT}it has the action<{next_action}>.",
        f"{_DEEP_INDENT}}}",
        f"{_INNER_INDENT}}}",
        f"{_INNER_INDENT}create a particle in position<next_processing_stage>.",
        f"{_INNER_INDENT}move the particle in position<record> to position<next_processing_stage>::action<{next_action}>::position<record>.",
        *_move_values(
            f"position<next_processing_stage>::action<{next_action}>", values_per_stage
        ),
        f"{_INNER_INDENT}create a particle in position<next_processing_stage>::action<{next_action}>::position<start>.",
        f"{_INNER_INDENT}destroy the particle in position<start>.",
        f"{_OUTER_INDENT}}}",
        "}",
        "",
    ]


def _emit_entry_point(
    prefix: str,
    pipelines: int,
    values_per_stage: int,
    *,
    satisfy_requirements: bool,
    destructor_reads: bool,
) -> list[str]:
    lines = [
        f"define the potential action<{_qualified(prefix, '/test')}> {{",
        f"{_OUTER_INDENT}it happens when {{",
        f"{_INNER_INDENT}this particle is created.",
        f"{_OUTER_INDENT}}} and it does {{",
    ]
    for pipeline in range(pipelines):
        first_action = _action_path("process_stage", pipeline, 0)
        lines.extend(
            [
                f"{_INNER_INDENT}define the position<pipeline_{pipeline}> {{",
                f"{_DEEP_INDENT}it may only contain particles where {{",
                f"{_DEEPEST_INDENT}it has the action<{first_action}>.",
                f"{_DEEP_INDENT}}}",
                f"{_INNER_INDENT}}}",
            ]
        )
        if destructor_reads:
            lines.extend(
                [
                    f"{_INNER_INDENT}define the position<record_{pipeline}> {{",
                    f"{_DEEP_INDENT}it may only contain particles where {{",
                    f"{_DEEPEST_INDENT}it has the position<{_TEMPORARY_METADATA_POSITION}>.",
                    f"{_DEEPEST_INDENT}it has the action<{_AUDIT_DESTRUCTOR}>.",
                    f"{_DEEPEST_INDENT}it has the position<{_AUDIT_READING_POSITION}>.",
                    f"{_DEEP_INDENT}}}",
                    f"{_INNER_INDENT}}}",
                ]
            )

    for pipeline in range(pipelines):
        first_action = _action_path("process_stage", pipeline, 0)
        pipeline_position = f"position<pipeline_{pipeline}>"
        first_record = f"{pipeline_position}::action<{first_action}>::position<record>"
        first_trigger = f"{pipeline_position}::action<{first_action}>::position<start>"
        # References must name explicit quality assignments, so the record is
        # built where its reading child is assigned and then handed over.
        record = f"position<record_{pipeline}>" if destructor_reads else first_record
        lines.extend(
            (
                f"{_INNER_INDENT}create a particle in {pipeline_position}.",
                f"{_INNER_INDENT}create a particle in {record}.",
            )
        )
        if satisfy_requirements:
            lines.append(
                f"{_INNER_INDENT}create a particle in {record}::position<{_TEMPORARY_METADATA_POSITION}>."
            )
        if destructor_reads:
            reading = f"{record}::position<{_AUDIT_READING_POSITION}>"
            lines.extend(
                (
                    f"{_INNER_INDENT}create a particle in {reading}.",
                    f'{_INNER_INDENT}set the value of {reading} from literal<standard:/number>"{pipeline}".',
                    f"{_INNER_INDENT}move the particle in {record} to {first_record}.",
                )
            )
        for value in range(values_per_stage):
            value_position = (
                f"{pipeline_position}::action<{first_action}>::position<value_{value}>"
            )
            lines.extend(
                (
                    f"{_INNER_INDENT}create a particle in {value_position}.",
                    f'{_INNER_INDENT}set the value of {value_position} from literal<standard:/number>"{value}".',
                )
            )
        lines.append(f"{_INNER_INDENT}create a particle in {first_trigger}.")

    lines.extend([f"{_OUTER_INDENT}}}", "}", ""])
    return lines


def generate_source_lines(  # noqa: PLR0913 - Each size scales independently.
    pipelines: int = DEFAULT_PIPELINES,
    processing_stages: int = DEFAULT_PROCESSING_STAGES,
    fqun_prefix: str = DEFAULT_FQUN_PREFIX,
    values_per_stage: int = 0,
    *,
    satisfy_requirements: bool = True,
    destructor_reads: bool = False,
) -> list[str]:
    """Return the generated source as a list of lines without trailing newlines."""
    if pipelines < _MIN_PIPELINES:
        raise ValueError(
            f"pipelines must be at least {_MIN_PIPELINES}, got {pipelines}"
        )
    if processing_stages < _MIN_PROCESSING_STAGES:
        raise ValueError(
            f"processing_stages must be at least {_MIN_PROCESSING_STAGES}, got {processing_stages}"
        )
    if values_per_stage < 0:
        raise ValueError(
            f"values_per_stage must not be negative, got {values_per_stage}"
        )

    lines = _emit_header()
    lines.extend(
        _emit_global_positions(
            fqun_prefix, values_per_stage, destructor_reads=destructor_reads
        )
    )
    if destructor_reads:
        lines.extend(_emit_audit_actions(fqun_prefix))
    for pipeline in range(pipelines):
        lines.extend(
            _emit_finalizer(
                fqun_prefix,
                pipeline,
                values_per_stage,
                destructor_reads=destructor_reads,
            )
        )
        lines.extend(
            _emit_record_preparer(
                fqun_prefix,
                pipeline,
                values_per_stage,
                destructor_reads=destructor_reads,
            )
        )

        next_action = _action_path("prepare_record", pipeline)
        for stage in reversed(range(processing_stages)):
            lines.extend(
                _emit_processing_stage(
                    fqun_prefix,
                    pipeline,
                    stage,
                    next_action,
                    values_per_stage,
                    destructor_reads=destructor_reads,
                )
            )
            next_action = _action_path("process_stage", pipeline, stage)

    lines.extend(
        _emit_entry_point(
            fqun_prefix,
            pipelines,
            values_per_stage,
            satisfy_requirements=satisfy_requirements,
            destructor_reads=destructor_reads,
        )
    )
    return lines[:-1]


def write_to_path(  # noqa: PLR0913 - Each size scales independently.
    output: Path,
    pipelines: int = DEFAULT_PIPELINES,
    processing_stages: int = DEFAULT_PROCESSING_STAGES,
    fqun_prefix: str = DEFAULT_FQUN_PREFIX,
    values_per_stage: int = 0,
    *,
    satisfy_requirements: bool = True,
    destructor_reads: bool = False,
) -> int:
    """Write generated source to ``output`` and return the number of lines."""
    lines = generate_source_lines(
        pipelines=pipelines,
        processing_stages=processing_stages,
        fqun_prefix=fqun_prefix,
        values_per_stage=values_per_stage,
        satisfy_requirements=satisfy_requirements,
        destructor_reads=destructor_reads,
    )
    return generator_io.write_lines(output, lines)


@click.command()
@click.option(
    "--satisfy-requirements/--violate-requirements",
    default=True,
    show_default=True,
    help="Omit required child particles to generate long diagnostic propagation histories.",
)
@click.option(
    "--output", type=generator_cli.OUTPUT_FILE, required=True, help="Generated file."
)
@click.option(
    "--pipelines",
    type=generator_cli.POSITIVE_INTEGER,
    default=DEFAULT_PIPELINES,
    show_default=True,
    help="Independent pipelines to emit.",
)
@click.option(
    "--processing-stages",
    type=generator_cli.POSITIVE_INTEGER,
    default=DEFAULT_PROCESSING_STAGES,
    show_default=True,
    help="Processing actions chained in each pipeline; cost grows quadratically.",
)
@click.option(
    "--values-per-stage",
    type=generator_cli.NONNEGATIVE_INTEGER,
    default=0,
    show_default=True,
    help=(
        "Positions with set values that each action passes to the next; the"
        " final action reads each one, so value requirements propagate through"
        " every caller."
    ),
)
@click.option(
    "--destructor-reads/--no-destructor-reads",
    default=False,
    show_default=True,
    help=(
        "Give the work particle a destructor that reads a value of the"
        " particle being destroyed, which the final action destroys."
    ),
)
@click.option(
    "--fqun-prefix",
    default=DEFAULT_FQUN_PREFIX,
    show_default=True,
    help="Universe prefix for every definition.",
)
def main(  # noqa: PLR0913 - Click passes the declared command options.
    output: Path,
    pipelines: int,
    processing_stages: int,
    values_per_stage: int,
    fqun_prefix: str,
    *,
    satisfy_requirements: bool,
    destructor_reads: bool,
):
    """Generate a Define source file with deep processing pipelines.

    Emits one .dfn holding many independent pipelines, each a chain of specialized
    processing actions. The entry-point action prepares one particle per pipeline,
    each processing action moves that particle into the next action's interface
    position and triggers it, and the final action moves the particle and destroys
    its temporary child particle. This is the requirement-propagation profiling
    shape: it drives Action Requirements up through many callers and exercises
    the Fill Rule's parent-position dependency substitution, which the other shapes
    barely reach.

    Scale it with --processing-stages, by far the more expensive knob: cost grows
    with the pipeline count times the square of the stage count, because every
    stage propagates requirements through every caller below it. --pipelines scales
    it linearly. Do not scale it by chasing a line count: the deepest shape here is
    also the shortest one. The generated source validates to zero diagnostics.

    --values-per-stage adds value requirements that propagate the same way, and
    --destructor-reads adds a destructor requirement that propagates from the
    final action, which destroys the particle, up to the entry point.
    """
    written = generator_cli.invoke(
        lambda: write_to_path(
            output,
            pipelines=pipelines,
            processing_stages=processing_stages,
            fqun_prefix=fqun_prefix,
            values_per_stage=values_per_stage,
            satisfy_requirements=satisfy_requirements,
            destructor_reads=destructor_reads,
        )
    )
    generator_cli.report_written("lines", written, output)


if __name__ == "__main__":
    main()
