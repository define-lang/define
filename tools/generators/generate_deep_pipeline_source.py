"""Generate a Define source file with deep, independent processing pipelines.

Emits a single ``.dfn`` that compiles to zero diagnostics, whose shape drives
Position Requirements up through long chains of callers rather than stressing
parse volume or graph density.

Each pipeline is one application workflow:

  * The entry-point action prepares the particles every stage uses.
  * Each processing action triggers the next stage, so a requirement inferred
    at the deepest stage propagates back through every caller above it.
  * The last two actions create a particle in a temporary child position of a
    caller-created work particle, then move the work particle and destroy the
    child particle.

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

_TEMPORARY_METADATA_POSITION = "/temporary_metadata"


def _action_path(kind: str, pipeline: int, stage: int | None = None) -> str:
    pipeline_path = f"/pipeline_{pipeline}"
    if stage is None:
        return f"{pipeline_path}/{kind}"
    return f"{pipeline_path}/{kind}_{stage}"


def _qualified(prefix: str, path: str) -> str:
    return f"{prefix}:{path}"


def _emit_header() -> list[str]:
    return [
        "# Generated Define source. Deep, independent processing pipelines.",
        "",
    ]


def _emit_finalizer(prefix: str, pipeline: int) -> list[str]:
    action_name = _qualified(prefix, _action_path("finalize_record", pipeline))
    return [
        f"define the potential action<{action_name}> {{",
        f"{_OUTER_INDENT}define the position<start>.",
        f"{_OUTER_INDENT}define the position<pending_record> {{",
        f"{_INNER_INDENT}it may only contain particles where {{",
        f"{_DEEP_INDENT}it has the position<{_TEMPORARY_METADATA_POSITION}>.",
        f"{_INNER_INDENT}}}",
        f"{_OUTER_INDENT}}}",
        f"{_OUTER_INDENT}define the position<completed_record> {{",
        f"{_INNER_INDENT}it may only contain particles where {{",
        f"{_DEEP_INDENT}it has the position<{_TEMPORARY_METADATA_POSITION}>.",
        f"{_INNER_INDENT}}}",
        f"{_OUTER_INDENT}}}",
        f"{_OUTER_INDENT}it happens when {{",
        f"{_INNER_INDENT}the position<start> has a particle.",
        f"{_OUTER_INDENT}}} and it does {{",
        f"{_INNER_INDENT}move the particle in position<pending_record> to position<completed_record>.",
        f"{_INNER_INDENT}destroy the particle in position<completed_record>::position<{_TEMPORARY_METADATA_POSITION}>.",
        f"{_OUTER_INDENT}}}",
        "}",
        "",
    ]


def _emit_record_preparer(prefix: str, pipeline: int) -> list[str]:
    action_name = _qualified(prefix, _action_path("prepare_record", pipeline))
    finalizer = _action_path("finalize_record", pipeline)
    return [
        f"define the potential action<{action_name}> {{",
        f"{_OUTER_INDENT}define the position<start>.",
        f"{_OUTER_INDENT}define the position<record_processing> {{",
        f"{_INNER_INDENT}it may only contain particles where {{",
        f"{_DEEP_INDENT}it has the action<{finalizer}>.",
        f"{_INNER_INDENT}}}",
        f"{_OUTER_INDENT}}}",
        f"{_OUTER_INDENT}it happens when {{",
        f"{_INNER_INDENT}the position<start> has a particle.",
        f"{_OUTER_INDENT}}} and it does {{",
        f"{_INNER_INDENT}create a particle in position<record_processing>::action<{finalizer}>::position<pending_record>::position<{_TEMPORARY_METADATA_POSITION}>.",
        f"{_INNER_INDENT}create a particle in position<record_processing>::action<{finalizer}>::position<start>.",
        f"{_OUTER_INDENT}}}",
        "}",
        "",
    ]


def _emit_processing_stage(
    prefix: str, pipeline: int, stage: int, next_action: str
) -> list[str]:
    action_name = _qualified(prefix, _action_path("process_stage", pipeline, stage))
    return [
        f"define the potential action<{action_name}> {{",
        f"{_OUTER_INDENT}define the position<start>.",
        f"{_OUTER_INDENT}define the position<next_processing_stage> {{",
        f"{_INNER_INDENT}it may only contain particles where {{",
        f"{_DEEP_INDENT}it has the action<{next_action}>.",
        f"{_INNER_INDENT}}}",
        f"{_OUTER_INDENT}}}",
        f"{_OUTER_INDENT}it happens when {{",
        f"{_INNER_INDENT}the position<start> has a particle.",
        f"{_OUTER_INDENT}}} and it does {{",
        f"{_INNER_INDENT}create a particle in position<next_processing_stage>::action<{next_action}>::position<start>.",
        f"{_OUTER_INDENT}}}",
        "}",
        "",
    ]


def _emit_entry_point(prefix: str, pipelines: int, processing_stages: int) -> list[str]:
    lines = [f"define the potential action<{_qualified(prefix, '/test')}> {{"]
    for pipeline in range(pipelines):
        first_action = _action_path("process_stage", pipeline, 0)
        lines.extend(
            [
                f"{_OUTER_INDENT}define the position<pipeline_{pipeline}> {{",
                f"{_INNER_INDENT}it may only contain particles where {{",
                f"{_DEEP_INDENT}it has the action<{first_action}>.",
                f"{_INNER_INDENT}}}",
                f"{_OUTER_INDENT}}}",
            ]
        )
    lines.extend(
        [
            f"{_OUTER_INDENT}it happens when {{",
            f"{_INNER_INDENT}this particle is created.",
            f"{_OUTER_INDENT}}} and it does {{",
        ]
    )

    for pipeline in range(pipelines):
        current_position = f"position<pipeline_{pipeline}>"
        lines.append(f"{_INNER_INDENT}create a particle in {current_position}.")

        for stage in range(processing_stages):
            processing_action = _action_path("process_stage", pipeline, stage)
            current_position += (
                f"::action<{processing_action}>::position<next_processing_stage>"
            )
            lines.append(f"{_INNER_INDENT}create a particle in {current_position}.")

        preparer = _action_path("prepare_record", pipeline)
        current_position += f"::action<{preparer}>::position<record_processing>"
        lines.append(f"{_INNER_INDENT}create a particle in {current_position}.")

        finalizer = _action_path("finalize_record", pipeline)
        current_position += f"::action<{finalizer}>::position<pending_record>"
        lines.append(f"{_INNER_INDENT}create a particle in {current_position}.")

        first_action = _action_path("process_stage", pipeline, 0)
        first_trigger = (
            f"position<pipeline_{pipeline}>::action<{first_action}>::position<start>"
        )
        lines.append(f"{_INNER_INDENT}create a particle in {first_trigger}.")

    lines.extend([f"{_OUTER_INDENT}}}", "}", ""])
    return lines


def generate_source_lines(
    pipelines: int = DEFAULT_PIPELINES,
    processing_stages: int = DEFAULT_PROCESSING_STAGES,
    fqun_prefix: str = DEFAULT_FQUN_PREFIX,
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

    lines = _emit_header()
    lines.extend(
        [
            f"define the potential position<{_qualified(prefix=fqun_prefix, path=_TEMPORARY_METADATA_POSITION)}>.",
            "",
        ]
    )
    for pipeline in range(pipelines):
        lines.extend(_emit_finalizer(fqun_prefix, pipeline))
        lines.extend(_emit_record_preparer(fqun_prefix, pipeline))

        next_action = _action_path("prepare_record", pipeline)
        for stage in reversed(range(processing_stages)):
            lines.extend(
                _emit_processing_stage(fqun_prefix, pipeline, stage, next_action)
            )
            next_action = _action_path("process_stage", pipeline, stage)

    lines.extend(_emit_entry_point(fqun_prefix, pipelines, processing_stages))
    return lines


def write_to_path(
    output: Path,
    pipelines: int = DEFAULT_PIPELINES,
    processing_stages: int = DEFAULT_PROCESSING_STAGES,
    fqun_prefix: str = DEFAULT_FQUN_PREFIX,
) -> int:
    """Write generated source to ``output`` and return the number of lines."""
    lines = generate_source_lines(
        pipelines=pipelines,
        processing_stages=processing_stages,
        fqun_prefix=fqun_prefix,
    )
    return generator_io.write_lines(output, lines)


@click.command()
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
    "--fqun-prefix",
    default=DEFAULT_FQUN_PREFIX,
    show_default=True,
    help="Universe prefix for every definition.",
)
def main(output: Path, pipelines: int, processing_stages: int, fqun_prefix: str):
    """Generate a Define source file with deep processing pipelines.

    Emits one .dfn holding many independent pipelines, each a chain of specialized
    processing actions. The entry-point action prepares the particles every stage
    uses, each processing action triggers the next stage, and the last two actions
    create a particle in a temporary child position of a caller-created work
    particle, then move the work particle and destroy the child particle. This is
    the requirement-propagation profiling shape: it drives Position Requirements up
    through many callers and exercises the Fill Rule's parent-position dependency
    substitution, which the other shapes barely reach.

    Scale it with --processing-stages, by far the more expensive knob: cost grows
    with the pipeline count times the square of the stage count, because every
    stage propagates requirements through every caller below it. --pipelines scales
    it linearly. Do not scale it by chasing a line count: the deepest shape here is
    also the shortest one. The generated source validates to zero diagnostics.
    """
    written = generator_cli.invoke(
        lambda: write_to_path(
            output,
            pipelines=pipelines,
            processing_stages=processing_stages,
            fqun_prefix=fqun_prefix,
        )
    )
    generator_cli.report_written("lines", written, output)


if __name__ == "__main__":
    main()
