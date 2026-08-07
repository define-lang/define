"""Summarize a py-spy speedscope profile with and without a sampled subtree.

The non-Lark view removes every stack sample that passes through
``--exclude-file``. Shared callees therefore remain attributed to compiler work
when reached directly, while samples of the same callees reached through the
bundled lark parser are removed with that subtree.

    uv run python tools/analyze_profile.py --profile <profile.json> \
        [--exclude-file lark_standalone.py] [--top 30]
"""

from __future__ import annotations

import json
import pathlib
from typing import TypedDict, cast

import click

type _ProfileKey = tuple[str, int, str]
type _Sample = tuple[tuple[_ProfileKey, ...], float]
# Per-function (self samples, cumulative samples, self time, cumulative time).
type _Metrics = tuple[int, int, float, float]


class _Frame(TypedDict):
    name: str
    file: str
    line: int


class _Profile(TypedDict):
    type: str
    samples: list[list[int]]
    weights: list[float]


class _Shared(TypedDict):
    frames: list[_Frame]


class _SpeedscopeProfile(TypedDict):
    profiles: list[_Profile]
    shared: _Shared


def short(function: _ProfileKey) -> str:
    """Render a sampled function as ``dir/file.py:line(name)``."""
    file, line, name = function
    parts = file.rsplit("/", 2)
    short_file = "/".join(parts[-2:]) if len(parts) >= 2 else file
    return f"{short_file}:{line}({name})"


def load_samples(profile_path: pathlib.Path) -> list[_Sample]:
    """Load stack samples from a py-spy speedscope profile."""
    with profile_path.open(encoding="utf-8") as profile_file:
        profile = cast("_SpeedscopeProfile", json.load(profile_file))

    frames = [
        (frame["file"], frame["line"], frame["name"])
        for frame in profile["shared"]["frames"]
    ]
    samples: list[_Sample] = []
    for thread_profile in profile["profiles"]:
        for stack, weight in zip(
            thread_profile["samples"], thread_profile["weights"], strict=True
        ):
            samples.append((tuple(frames[index] for index in stack), weight))
    return samples


def aggregate(samples: list[_Sample]) -> dict[_ProfileKey, _Metrics]:
    """Aggregate sampled stacks into per-function self and cumulative metrics."""
    metrics: dict[_ProfileKey, _Metrics] = {}
    for stack, weight in samples:
        if not stack:
            continue
        leaf = stack[-1]
        self_samples, cumulative_samples, self_time, cumulative_time = metrics.get(
            leaf, (0, 0, 0.0, 0.0)
        )
        metrics[leaf] = (
            self_samples + 1,
            cumulative_samples,
            self_time + weight,
            cumulative_time,
        )

        for function in set(stack):
            self_samples, cumulative_samples, self_time, cumulative_time = metrics.get(
                function, (0, 0, 0.0, 0.0)
            )
            metrics[function] = (
                self_samples,
                cumulative_samples + 1,
                self_time,
                cumulative_time + weight,
            )
    return metrics


def without_file(samples: list[_Sample], excluded_file: str) -> list[_Sample]:
    """Remove samples whose stack passes through ``excluded_file``."""
    return [
        sample
        for sample in samples
        if sample[0] and all(excluded_file not in function[0] for function in sample[0])
    ]


def emit_table(
    view: dict[_ProfileKey, _Metrics],
    *,
    key: str,
    n: int,
    title: str,
    total_time: float,
) -> None:
    """Print the top sampled functions ranked by self or cumulative time."""
    index = 2 if key == "self time" else 3
    rows = sorted(view.items(), key=lambda item: item[1][index], reverse=True)
    print(f"\n=== {title} (top {n} by {key}) ===")
    print(f"{'self':>9} {'%tot':>6} {'cumulative':>10} {'samples':>9}  function")
    for function, (
        self_samples,
        _cumulative_samples,
        self_time,
        cumulative_time,
    ) in rows[:n]:
        percent = 100.0 * self_time / total_time if total_time else 0.0
        print(
            f"{self_time:9.3f} {percent:5.1f}% {cumulative_time:10.3f} "
            + f"{self_samples:9d}  {short(function)}"
        )


@click.command()
@click.option(
    "--profile",
    "profile_path",
    type=click.Path(path_type=pathlib.Path),
    required=True,
    help="Speedscope JSON profile to analyze.",
)
@click.option(
    "--exclude-file",
    "excluded_file",
    default="lark_standalone.py",
    show_default=True,
    help="Remove samples whose stacks pass through this filename.",
)
@click.option("--top", type=int, default=30, show_default=True)
def main(profile_path: pathlib.Path, excluded_file: str, top: int) -> None:
    """Print overall and non-Lark sampled hotspot tables."""
    samples = load_samples(profile_path)
    non_lark_samples = without_file(samples, excluded_file)
    total_time = sum(weight for _stack, weight in samples)
    classified_time = sum(weight for stack, weight in samples if stack)
    non_lark_time = sum(weight for _stack, weight in non_lark_samples)
    excluded_time = classified_time - non_lark_time
    unclassified_time = total_time - classified_time

    print(f"Sampled time: {total_time:.3f}s; samples: {len(samples)}")
    print(
        "NOTE: py-spy estimates CPU distribution from periodic stack samples; "
        + "use an unprofiled run for absolute wall time."
    )
    print(
        f"\n'{excluded_file}' subtree: {excluded_time:.3f}s sampled time "
        + f"({100.0 * excluded_time / total_time:.1f}%)"
    )
    print(
        f"Non-Lark work: {non_lark_time:.3f}s sampled time "
        + f"({100.0 * non_lark_time / total_time:.1f}%)"
    )
    if unclassified_time:
        print(
            f"No Python frame: {unclassified_time:.3f}s sampled time "
            + f"({100.0 * unclassified_time / total_time:.1f}%)"
        )

    full = aggregate(samples)
    non_lark = aggregate(non_lark_samples)
    emit_table(
        full,
        key="self time",
        n=top,
        title="ALL (with excluded subtree)",
        total_time=total_time,
    )
    emit_table(
        full,
        key="cumulative time",
        n=top,
        title="ALL by cumulative time",
        total_time=total_time,
    )
    emit_table(
        non_lark,
        key="self time",
        n=top,
        title=f"WITHOUT {excluded_file} subtree",
        total_time=total_time,
    )
    emit_table(
        non_lark,
        key="cumulative time",
        n=top,
        title=f"WITHOUT {excluded_file} subtree, by cumulative time",
        total_time=total_time,
    )


if __name__ == "__main__":
    main()
