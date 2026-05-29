"""Run cProfile over the Define compiler compiling a source file.

Profiles ``driver.compile_source`` — the in-process, non-filesystem compile
path, the same code that ``main compile`` runs when source is piped on stdin.
Profiling in-process (rather than spawning the CLI) keeps cProfile's view free
of process-startup and click-dispatch noise.

Requires the repo root on PYTHONPATH so ``define.compiler`` imports resolve, and
that ``uv run tools/setup_local_dev.py`` has been run at least once. Invoke as:

    PYTHONPATH=<repo-root> uv run python tools/run_profile.py \
        --source <file.dfn> --out <file.prof>
"""

from __future__ import annotations

import argparse
import contextlib
import cProfile
import pathlib
import tempfile
from typing import cast

from define.compiler import driver


def main() -> None:
    """Parse arguments, profile the compile, and write the .prof file."""
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--source", type=pathlib.Path, required=True)
    _ = parser.add_argument("--out", type=pathlib.Path, required=True)
    _ = parser.add_argument(
        "--output-dir",
        type=pathlib.Path,
        default=None,
        help="Codegen output dir (defaults to a throwaway temp dir).",
    )
    args = parser.parse_args()
    source_path = cast("pathlib.Path", args.source)
    out_path = cast("pathlib.Path", args.out)
    output_dir = cast("pathlib.Path | None", args.output_dir)

    source = source_path.read_text(encoding="utf-8")

    # A passed --output-dir is left in place; the default throwaway dir is
    # removed once profiling is done so repeated runs don't leak codegen output.
    out_dir_ctx = (
        contextlib.nullcontext(output_dir)
        if output_dir is not None
        else tempfile.TemporaryDirectory(prefix="cg_profile_")
    )
    with out_dir_ctx as out_dir_name:
        out_dir = pathlib.Path(out_dir_name)
        d = driver.Driver()
        profiler = cProfile.Profile()
        profiler.enable()
        result = d.compile_source(source, out_dir)
        profiler.disable()
    profiler.dump_stats(str(out_path))

    # A clean (0-diagnostic) compile means the profile reflects the full
    # pipeline; a failed one may have short-circuited and is not comparable.
    print(f"has_errors={result.result.has_errors()}")
    print(f"profile written to {out_path}")


if __name__ == "__main__":
    main()
