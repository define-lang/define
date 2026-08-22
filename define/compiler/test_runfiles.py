"""Resolve Bazel runfiles for compiler tests."""

from __future__ import annotations

import os
from pathlib import Path

from python.runfiles import runfiles  # pyright: ignore[reportMissingTypeStubs]


def resolve_from_env(variable: str) -> Path:
    """Resolve the runfile named by an environment variable."""
    location = os.environ[variable]
    candidate = Path(location)
    if candidate.exists():
        return candidate
    runfiles_resolver = runfiles.Runfiles.Create()
    if runfiles_resolver is None:
        raise RuntimeError("Bazel runfiles are unavailable")
    resolved = runfiles_resolver.Rlocation(location)
    if resolved is None:
        raise FileNotFoundError(location)
    return Path(resolved)
