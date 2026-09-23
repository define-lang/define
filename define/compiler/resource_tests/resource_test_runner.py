"""Measure one isolated command and enforce per-case resource budgets."""

from __future__ import annotations

import contextlib
import os
import resource
import signal
import subprocess
import time
from pathlib import Path

import click
import msgspec


class ResourceTestError(Exception):
    """A resource test failed to complete within its required limits."""


class CpuSafetyLimitExceededError(ResourceTestError):
    """The command exhausted its CPU safety limit before completing."""


class CpuGrowthExceededError(ResourceTestError):
    """CPU usage exceeded the allowance relative to the control workload."""


class MemoryBudgetExceededError(ResourceTestError):
    """The command exceeded its peak resident memory allowance."""


class WallDeadlineExceededError(ResourceTestError):
    """The command did not complete before its wall deadline."""


class CommandFailedError(ResourceTestError):
    """The command failed independently of an identified budget violation."""


class Measurement(msgspec.Struct):
    """Resource usage of one command, including its interpreter startup."""

    returncode: int
    cpu_seconds: float
    peak_rss_bytes: int
    wall_seconds: float
    timed_out: bool

    def check(self, *, rss_bytes: int, stderr: str):
        """Require successful completion within the memory budget."""
        description = (
            f"CPU {self.cpu_seconds:.3f}s; "
            f"RSS {self.peak_rss_bytes / 1024**2:.1f} / {rss_bytes / 1024**2:.1f} MiB; "
            f"wall {self.wall_seconds:.3f}s; exit {self.returncode}"
        )
        if self.timed_out:
            raise WallDeadlineExceededError(description)
        if self.returncode not in (0, -signal.SIGXCPU):
            raise CommandFailedError(f"{description}\n{stderr}")
        # A known CPU regression must not conceal a new memory regression.
        if self.peak_rss_bytes > rss_bytes:
            raise MemoryBudgetExceededError(description)
        if self.returncode == -signal.SIGXCPU:
            raise CpuSafetyLimitExceededError(description)

    def check_cpu_growth(
        self, control: Measurement, *, maximum_ratio: float, rss_bytes: int, stderr: str
    ):
        """Require bounded CPU growth relative to a successfully measured control."""
        allowance = control.cpu_seconds * maximum_ratio
        try:
            self.check(rss_bytes=rss_bytes, stderr=stderr)
        except CpuSafetyLimitExceededError:
            # A stopped run proves excessive growth only if its measured lower
            # bound already exceeds the relative allowance.
            if self.cpu_seconds <= allowance:
                raise
        if self.cpu_seconds > allowance:
            raise CpuGrowthExceededError(
                f"CPU {self.cpu_seconds:.3f}s exceeds {maximum_ratio:g} times "
                + f"control {control.cpu_seconds:.3f}s ({allowance:.3f}s); "
                + f"RSS {self.peak_rss_bytes / 1024**2:.1f} MiB"
            )


def run(
    command: list[str],
    *,
    supervisor: Path,
    limiter: Path,
    directory: Path,
    artifacts: Path,
    source: Path | None,
    cpu_seconds: int,
    data_bytes: int,
    wall_seconds: float,
) -> Measurement:
    """Run a command through a fresh supervisor so child accounting is per-case."""
    artifacts.mkdir()
    source_args = ["--source", str(source)] if source is not None else []
    _ = subprocess.run(
        [
            str(supervisor),
            "--artifacts",
            str(artifacts),
            *source_args,
            "--wall-seconds",
            str(wall_seconds),
            "--",
            str(limiter),
            str(data_bytes),
            str(cpu_seconds),
            *command,
        ],
        cwd=directory,
        check=True,
    )
    return msgspec.json.decode(
        (artifacts / "usage.json").read_bytes(), type=Measurement
    )


def supervise(
    command: list[str], *, source: Path | None, artifacts: Path, wall_seconds: float
):
    """Record the usage of this supervisor's only child, even when it is killed."""
    started = time.monotonic()
    timed_out = False
    with (
        source.open("rb") if source is not None else contextlib.nullcontext() as stdin,
        (artifacts / "stdout").open("wb") as stdout,
        (artifacts / "stderr").open("wb") as stderr,
        subprocess.Popen(
            command, stdin=stdin, stdout=stdout, stderr=stderr, start_new_session=True
        ) as process,
    ):
        try:
            returncode = process.wait(timeout=wall_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGKILL)
            returncode = process.wait()
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    measurement = Measurement(
        returncode=returncode,
        cpu_seconds=usage.ru_utime + usage.ru_stime,
        peak_rss_bytes=usage.ru_maxrss * 1024,
        wall_seconds=time.monotonic() - started,
        timed_out=timed_out,
    )
    _ = (artifacts / "usage.json").write_bytes(msgspec.json.encode(measurement))


@click.command()
@click.option("--artifacts", type=click.Path(path_type=Path), required=True)
@click.option("--source", type=click.Path(path_type=Path))
@click.option(
    "--wall-seconds", type=click.FloatRange(min=0, min_open=True), required=True
)
@click.argument("command", nargs=-1, required=True)
def main(
    artifacts: Path, source: Path | None, wall_seconds: float, command: tuple[str, ...]
):
    """Supervise one resource-limited command."""
    supervise(
        list(command),
        source=source,
        artifacts=artifacts,
        wall_seconds=wall_seconds,
    )


if __name__ == "__main__":
    main()
