"""The survivors report: each mutant that no test killed, with its patch."""

from __future__ import annotations

import collections
from typing import TYPE_CHECKING

from tools.bazel_mutation_testing import results

if TYPE_CHECKING:
    import pathlib
    from collections.abc import Iterable, Mapping

    from tools.bazel_mutation_testing import mutant

# A mutant that a time or memory limit killed may only have made a test slower
# or larger, so the report lists it with the survivors.
REPORTED = frozenset(
    {
        results.Outcome.SURVIVED,
        results.Outcome.TIMED_OUT,
        results.Outcome.OUT_OF_MEMORY,
    }
)


def _fence(patch: str) -> str:
    """Return a code fence longer than every run of backticks in `patch`."""
    fence = "```"
    while fence in patch:
        fence += "`"
    return fence


def render(
    run: results.Run,
    mutants: Iterable[mutant.Mutant],
    outcomes: Mapping[str, results.Result],
) -> str:
    """Return the report of `run`, whose `mutants` have the results `outcomes`."""
    counts = collections.Counter(result.outcome for result in outcomes.values())
    lines = [
        "# Mutation Testing Survivors",
        "",
        f"- Commit: `{run.commit}`",
        f"- Area: `{' '.join(run.area)}`",
        f"- Mutants: {len(outcomes)}: "
        + ", ".join(f"{counts[outcome]} {outcome}" for outcome in results.Outcome),
    ]
    by_path: dict[str, list[mutant.Mutant]] = {}
    for listed in mutants:
        if outcomes[listed.name].outcome in REPORTED:
            by_path.setdefault(listed.path, []).append(listed)
    for path in sorted(by_path):
        lines.extend(["", f"## {path}"])
        for listed in by_path[path]:
            result = outcomes[listed.name]
            fence = _fence(listed.patch)
            lines.extend(["", f"### {listed.name}", ""])
            if result.outcome == results.Outcome.TIMED_OUT:
                lines.extend([f"Timed out: {result.culprit}", ""])
            elif result.outcome == results.Outcome.OUT_OF_MEMORY:
                lines.extend([f"Ran out of memory: {result.culprit}", ""])
            lines.extend([f"{fence}diff", listed.patch.rstrip("\n"), fence])
    return "\n".join(lines) + "\n"


def write(
    path: pathlib.Path,
    run: results.Run,
    mutants: Iterable[mutant.Mutant],
    outcomes: Mapping[str, results.Result],
):
    """Write the report of `run` to `path`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(render(run, mutants, outcomes), encoding="utf-8", newline="\n")
