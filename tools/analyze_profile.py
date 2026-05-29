"""Summarize a cProfile run: hotspots overall and with a subtree's cost removed.

The compiler-only view keeps the functions defined in ``--exclude-file`` out
entirely, and for every other function counts only the calls and time that came
from non-excluded callers. Splitting shared functions (notably C builtins that
both the compiler and the bundled lark parser call) by their immediate caller
keeps each one's compiler-driven cost here instead of charging all of it to
lark. For the Define compiler this isolates the compiler's own validation/AST
work from the lark parser+lexer+transformer, which otherwise dominates.

Both views come from the SAME profile — no second profiler run is needed; the
per-caller split is read from pstats' per-edge caller records.

    uv run python tools/analyze_profile.py --prof <file.prof> \
        [--exclude-file lark_standalone.py] [--top 30]
"""

from __future__ import annotations

import argparse
import pstats
from typing import cast

# pstats key: (filename, first_line_number, function_name)
type _ProfKey = tuple[str, int, str]
# pstats per-caller edge: (primitive_calls, total_calls, tottime, cumtime)
type _CallerEdge = tuple[int, int, float, float]
# pstats stats value: (cc, nc, tt, ct, callers_dict)
type _ProfEntry = tuple[int, int, float, float, dict[_ProfKey, _CallerEdge]]
type _StatsDict = dict[_ProfKey, _ProfEntry]
# Per-function (primitive_calls, total_calls, tottime, cumtime) for one view.
type _Metrics = tuple[int, int, float, float]


def short(func: _ProfKey) -> str:
    """Render a profiler function key as ``dir/file.py:line(name)``."""
    file, line, name = func
    parts = file.rsplit("/", 2)
    short_file = "/".join(parts[-2:]) if len(parts) >= 2 else file
    return f"{short_file}:{line}({name})"


def full_view(stats_dict: _StatsDict) -> dict[_ProfKey, _Metrics]:
    """Every function's own (calls, tottime, cumtime), as the profile recorded them."""
    return {func: value[:4] for func, value in stats_dict.items()}


def compiler_view(
    stats_dict: _StatsDict, exclude_file: str
) -> dict[_ProfKey, _Metrics]:
    """Each non-excluded function's calls and time attributable to non-excluded callers.

    Functions defined in ``exclude_file`` are dropped entirely — lark code is
    lark's, whichever side entered it. Every other function is split by its
    immediate caller so a builtin the compiler and lark both call keeps only its
    compiler-driven cost here, rather than being charged wholesale to lark.
    """
    excluded = {f for f in stats_dict if exclude_file in f[0]}
    view: dict[_ProfKey, _Metrics] = {}
    for func, value in stats_dict.items():
        if func in excluded:
            continue
        callers = value[4]
        if not callers:
            # No recorded caller (a top-level entry point): all of it is ours.
            view[func] = value[:4]
            continue
        cc = nc = 0
        tt = ct = 0.0
        for caller, edge in callers.items():
            if caller in excluded:
                continue
            cc += edge[0]
            nc += edge[1]
            tt += edge[2]
            ct += edge[3]
        if nc:
            view[func] = (cc, nc, tt, ct)
    return view


def emit_table(
    view: dict[_ProfKey, _Metrics],
    *,
    key: str,
    n: int,
    title: str,
    total_tt: float,
) -> None:
    """Print the top-n functions in ``view`` ranked by tottime or cumtime."""
    idx = 2 if key == "tottime" else 3
    rows = sorted(view.items(), key=lambda item: item[1][idx], reverse=True)
    print(f"\n=== {title} (top {n} by {key}) ===")
    print(f"{'tottime':>9} {'%tot':>6} {'cumtime':>9} {'ncalls':>11}  function")
    for func, (_cc, nc, tt, ct) in rows[:n]:
        pct = 100.0 * tt / total_tt if total_tt else 0.0
        print(f"{tt:9.3f} {pct:5.1f}% {ct:9.3f} {nc:11d}  {short(func)}")


def main() -> None:
    """Load the profile and print the overall and compiler-only hotspot tables."""
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--prof", required=True)
    _ = parser.add_argument("--exclude-file", default="lark_standalone.py")
    _ = parser.add_argument("--top", type=int, default=30)
    args = parser.parse_args()

    prof_path = cast("str", args.prof)
    exclude_file = cast("str", args.exclude_file)
    top = cast("int", args.top)

    p = pstats.Stats(prof_path)
    sd = cast("_StatsDict", p.stats)  # pyright: ignore[reportAttributeAccessIssue]
    total = cast("float", p.total_tt)  # pyright: ignore[reportAttributeAccessIssue]
    prim_calls = cast("int", p.prim_calls)  # pyright: ignore[reportAttributeAccessIssue]

    print(f"Total time: {total:.3f}s; primitive calls: {prim_calls}")
    print(
        "NOTE: cProfile inflates wall time ~3x; use these figures for relative ranking, not absolute wall time."
    )

    full = full_view(sd)
    compiler = compiler_view(sd, exclude_file)
    compiler_tt = sum(m[2] for m in compiler.values())
    excl_tt = total - compiler_tt
    print(
        f"\n'{exclude_file}' subtree (its functions + shared callees' time entered through it):"
        + f" {excl_tt:.3f}s tottime ({100.0 * excl_tt / total:.1f}%)"
    )
    print(
        f"Compiler's own work: {compiler_tt:.3f}s tottime ({100.0 * compiler_tt / total:.1f}%)"
    )

    emit_table(
        full, key="tottime", n=top, title="ALL (with excluded subtree)", total_tt=total
    )
    emit_table(full, key="cumtime", n=top, title="ALL by cumtime", total_tt=total)
    emit_table(
        compiler,
        key="tottime",
        n=top,
        title=f"WITHOUT {exclude_file} subtree",
        total_tt=total,
    )
    emit_table(
        compiler,
        key="cumtime",
        n=top,
        title=f"WITHOUT {exclude_file} subtree, by cumtime",
        total_tt=total,
    )


if __name__ == "__main__":
    main()
