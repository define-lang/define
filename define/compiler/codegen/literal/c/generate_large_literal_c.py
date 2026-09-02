"""Generate large pointer-free literal C programs for code-layout measurements."""

from __future__ import annotations

import argparse
import os
import pathlib
import tempfile
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Sequence

CodeShape = Literal["compact", "direct", "functions", "regions", "switch"]

DEFAULT_OPERATIONS = 4096
DEFAULT_REGION_SIZE = 64
DEFAULT_SHAPE: CodeShape = "regions"
_PARTICLE_COUNT = 64
_SHAPES: tuple[CodeShape, ...] = (
    "compact",
    "direct",
    "functions",
    "regions",
    "switch",
)


def _constant(operation: int) -> int:
    value = operation + 0x9E3779B97F4A7C15
    value = (value ^ (value >> 30)) * 0xBF58476D1CE4E5B9
    value &= (1 << 64) - 1
    value = (value ^ (value >> 27)) * 0x94D049BB133111EB
    value &= (1 << 64) - 1
    return value ^ (value >> 31)


def _operation_line(operation: int) -> str:
    particle = operation % _PARTICLE_COUNT
    dependency = (operation * 17 + 13) % _PARTICLE_COUNT
    constant = _constant(operation)
    return (
        f"execution->particles[{particle}] = rotate_left("
        f"execution->particles[{particle}] + UINT64_C(0x{constant:016x}))"
        f" ^ execution->particles[{dependency}];"
    )


def _header(operations: int) -> list[str]:
    return [
        "#define _POSIX_C_SOURCE 200809L",
        "",
        "#include <errno.h>",
        "#include <stdint.h>",
        "#include <stdio.h>",
        "#include <stdlib.h>",
        "#include <time.h>",
        "",
        "#if defined(LITERAL_C_GEM5_ROI)",
        "#include <gem5/m5ops.h>",
        "#endif",
        "",
        f"enum {{ particle_count = {_PARTICLE_COUNT}, operation_count = {operations} }};",
        "",
        "typedef struct {",
        "    uint64_t particles[particle_count];",
        "} ActionExecution;",
        "",
        "static uint64_t rotate_left(uint64_t value) {",
        "    return (value << 17) | (value >> 47);",
        "}",
        "",
    ]


def _emit_direct(operations: int) -> list[str]:
    lines = ["static void run_operations(ActionExecution *restrict execution) {"]
    for operation in range(operations):
        lines.append(f"    {_operation_line(operation)}")
    lines.extend(["}", ""])
    return lines


def _emit_regions(operations: int, region_size: int) -> list[str]:
    lines = [
        "#if defined(__GNUC__) || defined(__clang__)",
        "#define NOINLINE __attribute__((noinline))",
        "#else",
        "#define NOINLINE",
        "#endif",
        "",
    ]
    region_count = (operations + region_size - 1) // region_size
    for region in range(region_count):
        lines.append(
            f"static NOINLINE void run_region_{region}(ActionExecution *restrict execution) {{"
        )
        first_operation = region * region_size
        end_operation = min(first_operation + region_size, operations)
        for operation in range(first_operation, end_operation):
            lines.append(f"    {_operation_line(operation)}")
        lines.extend(["}", ""])
    lines.append("static void run_operations(ActionExecution *restrict execution) {")
    for region in range(region_count):
        lines.append(f"    run_region_{region}(execution);")
    lines.extend(["}", ""])
    return lines


def _emit_switch(operations: int) -> list[str]:
    lines = [
        "static void run_operations(ActionExecution *restrict execution) {",
        "    for (size_t operation = 0; operation < operation_count; ++operation) {",
        "        switch (operation) {",
    ]
    for operation in range(operations):
        lines.extend(
            [
                f"            case {operation}:",
                f"                {_operation_line(operation)}",
                "                break;",
            ]
        )
    lines.extend(["        }", "    }", "}", ""])
    return lines


def _emit_functions(operations: int) -> list[str]:
    lines: list[str] = []
    for operation in range(operations):
        lines.extend(
            [
                f"static void operation_{operation}(ActionExecution *restrict execution) {{",
                f"    {_operation_line(operation)}",
                "}",
                "",
            ]
        )
    lines.extend(
        [
            "typedef void (*ParticleOperation)(ActionExecution *);",
            "",
            "static const ParticleOperation operations[operation_count] = {",
        ]
    )
    for operation in range(operations):
        lines.append(f"    operation_{operation},")
    lines.extend(
        [
            "};",
            "",
            "static void run_operations(ActionExecution *restrict execution) {",
            "    for (size_t operation = 0; operation < operation_count; ++operation) {",
            "        operations[operation](execution);",
            "    }",
            "}",
            "",
        ]
    )
    return lines


def _emit_compact(operations: int) -> list[str]:
    lines = ["static const uint64_t constants[operation_count] = {"]
    for operation in range(operations):
        lines.append(f"    UINT64_C(0x{_constant(operation):016x}),")
    lines.extend(
        [
            "};",
            "",
            "static void run_operations(ActionExecution *restrict execution) {",
            "    for (size_t operation = 0; operation < operation_count; ++operation) {",
            "        size_t particle = operation % particle_count;",
            "        size_t dependency = (operation * 17 + 13) % particle_count;",
            "        execution->particles[particle] = rotate_left(",
            "            execution->particles[particle] + constants[operation]",
            "        ) ^ execution->particles[dependency];",
            "    }",
            "}",
            "",
        ]
    )
    return lines


def _footer(shape: CodeShape) -> list[str]:
    return [
        "static uint64_t parse_value(const char *text, const char *name) {",
        "    char *end = NULL;",
        "    errno = 0;",
        "    unsigned long long value = strtoull(text, &end, 10);",
        "    if (errno != 0 || end == text || *end != '\\0') {",
        '        fprintf(stderr, "invalid %s: %s\\n", name, text);',
        "        exit(EXIT_FAILURE);",
        "    }",
        "    return (uint64_t)value;",
        "}",
        "",
        "static double monotonic_seconds(void) {",
        "    struct timespec now;",
        "    if (clock_gettime(CLOCK_MONOTONIC, &now) != 0) {",
        '        perror("clock_gettime");',
        "        exit(EXIT_FAILURE);",
        "    }",
        "    return (double)now.tv_sec + (double)now.tv_nsec / 1000000000.0;",
        "}",
        "",
        "int main(int argc, char **argv) {",
        "    if (argc != 3) {",
        '        fprintf(stderr, "usage: %s ROUNDS RUNTIME_SEED\\n", argv[0]);',
        "        return EXIT_FAILURE;",
        "    }",
        '    uint64_t rounds = parse_value(argv[1], "round count");',
        '    uint64_t seed = parse_value(argv[2], "runtime seed");',
        "    if (rounds == 0) {",
        '        fputs("round count must be positive\\n", stderr);',
        "        return EXIT_FAILURE;",
        "    }",
        "",
        "    ActionExecution execution;",
        "    for (size_t particle = 0; particle < particle_count; ++particle) {",
        "        execution.particles[particle] = rotate_left(seed + particle + 1);",
        "    }",
        "",
        "    double start = monotonic_seconds();",
        "#if defined(LITERAL_C_GEM5_ROI)",
        "    m5_work_begin(0, 0);",
        "#endif",
        "    for (uint64_t round = 0; round < rounds; ++round) {",
        "        run_operations(&execution);",
        "    }",
        "#if defined(LITERAL_C_GEM5_ROI)",
        "    m5_work_end(0, 0);",
        "#endif",
        "    double elapsed = monotonic_seconds() - start;",
        "",
        "    uint64_t checksum = 0;",
        "    for (size_t particle = 0; particle < particle_count; ++particle) {",
        "        checksum ^= execution.particles[particle];",
        "    }",
        "    printf(",
        f'        "shape={shape} operations=%d rounds=%llu elapsed_ns=%.0f "',
        '        "ns_per_operation=%.6f checksum=%llu\\n",',
        "        operation_count,",
        "        (unsigned long long)rounds,",
        "        elapsed * 1.0e9,",
        "        elapsed * 1.0e9 / ((double)rounds * (double)operation_count),",
        "        (unsigned long long)checksum",
        "    );",
        "    return EXIT_SUCCESS;",
        "}",
    ]


def generate_source_lines(
    operations: int = DEFAULT_OPERATIONS,
    shape: CodeShape = DEFAULT_SHAPE,
    region_size: int = DEFAULT_REGION_SIZE,
) -> list[str]:
    """Return one standalone C benchmark as lines without trailing newlines."""
    if operations < 1:
        raise ValueError(f"operations must be positive, got {operations}")
    if region_size < 1:
        raise ValueError(f"region_size must be positive, got {region_size}")

    lines = _header(operations)
    if shape == "compact":
        lines.extend(_emit_compact(operations))
    elif shape == "direct":
        lines.extend(_emit_direct(operations))
    elif shape == "functions":
        lines.extend(_emit_functions(operations))
    elif shape == "regions":
        lines.extend(_emit_regions(operations, region_size))
    else:
        lines.extend(_emit_switch(operations))
    lines.extend(_footer(shape))
    return lines


def write_to_path(
    output: pathlib.Path,
    operations: int = DEFAULT_OPERATIONS,
    shape: CodeShape = DEFAULT_SHAPE,
    region_size: int = DEFAULT_REGION_SIZE,
) -> int:
    """Write a generated standalone C benchmark and return its line count."""
    lines = generate_source_lines(
        operations=operations, shape=shape, region_size=region_size
    )
    temporary_path: pathlib.Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=output.parent, delete=False
        ) as temporary_file:
            temporary_path = pathlib.Path(temporary_file.name)
            for line in lines:
                _ = temporary_file.write(line)
                _ = temporary_file.write("\n")
        os.replace(temporary_path, output)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return len(lines)


class Arguments(argparse.Namespace):
    """Command-line arguments for the large-code generator."""

    def __init__(self):
        """Initialize values that argument parsing replaces."""
        super().__init__()
        self.output: pathlib.Path = pathlib.Path()
        self.operations: int = DEFAULT_OPERATIONS
        self.shape: CodeShape = DEFAULT_SHAPE
        self.region_size: int = DEFAULT_REGION_SIZE


def _positive_integer(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError(f"expected a positive integer, got {text}")
    return value


def main(arguments: Sequence[str] | None = None) -> int:
    """Generate a large pointer-free literal C benchmark."""
    parser = argparse.ArgumentParser(description=main.__doc__)
    _ = parser.add_argument("--output", type=pathlib.Path, required=True)
    _ = parser.add_argument(
        "--operations", type=_positive_integer, default=DEFAULT_OPERATIONS
    )
    _ = parser.add_argument("--shape", choices=_SHAPES, default=DEFAULT_SHAPE)
    _ = parser.add_argument(
        "--region-size", type=_positive_integer, default=DEFAULT_REGION_SIZE
    )
    parsed = parser.parse_args(arguments, namespace=Arguments())
    written = write_to_path(
        parsed.output,
        operations=parsed.operations,
        shape=parsed.shape,
        region_size=parsed.region_size,
    )
    print(f"Wrote {written} lines to {parsed.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
