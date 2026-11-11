"""Helpers shared by the project configuration tests."""

from __future__ import annotations

from pathlib import PurePosixPath

from crates.source_rendering.python import rendering
from define.compiler import config, constants
from define.compiler.data_structures import define_path


def load_project_root_config(
    root: define_path.DefinePath = constants.PROJECT_ROOT,
    declaring_entry: config.LocalDependencyEntry | None = None,
) -> config.RootConfigResult:
    """Load the configuration of the project at root."""
    return config.ConfigLoader(root, rendering.SourceMap()).load_project_root_config(
        declaring_entry
    )


def declaring_entry(universe: str, path: str) -> config.LocalDependencyEntry:
    """Return the first local dependency entry of the project's local deps config."""
    return config.LocalDependencyEntry(
        deps_path=str(config.LOCAL_DEPS_PATH),
        index=0,
        universe=universe,
        path=define_path.DefinePathFromPosix(PurePosixPath(path)),
    )
