# pyright: reportUnusedCallResult=false
"""Shared validator test helpers."""

from __future__ import annotations

from pprint import pformat
from typing import TYPE_CHECKING, Protocol

from define.compiler import constants
from define.compiler.data_structures import define_path

if TYPE_CHECKING:
    from pathlib import Path

    from define.compiler.errors import diagnostics


def standard_library_file(relative_path: str) -> str:
    """Return the path of a standard universe file as file results report it."""
    return str(constants.STANDARD_LIBRARY_ROOT / define_path.DefinePath(relative_path))


class _ValidationErrors(Protocol):
    @property
    def all_exceptions(self) -> list[diagnostics.FileLoadFailureDiagnostic]: ...

    @property
    def all_diagnostics(self) -> list[diagnostics.FormattableDiagnostic]: ...


def assert_no_errors(result: _ValidationErrors):
    """Assert that a validation result has no load failures or diagnostics."""
    __tracebackhide__ = True
    load_failures = result.all_exceptions
    assert not load_failures, (
        f"Expected no load failures, but got {len(load_failures)}:\n"
        + "\n".join(f"  {pformat(f)}" for f in load_failures)
    )
    all_diagnostics = result.all_diagnostics
    assert not all_diagnostics, (
        f"Expected no diagnostics, but got {len(all_diagnostics)}:\n"
        + "\n".join(f"  {pformat(d)}" for d in all_diagnostics)
    )


def write_project_config(tmp_path: Path, universe_name: str):
    """Write a .define/project/config.defcl file under tmp_path."""
    config_dir = tmp_path / ".define" / "project"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.defcl").write_text(
        f'project: {{\n  universe_name: "{universe_name}"\n}}\n',
        encoding="utf-8",
        newline="\n",
    )


def write_local_deps_config(tmp_path: Path, deps: dict[str, str]):
    """Write a .define/deps/local.defcl file under tmp_path."""
    deps_dir = tmp_path / ".define" / "deps"
    deps_dir.mkdir(parents=True, exist_ok=True)
    entries = ",\n    ".join(
        f'{{\n      universe_name: "{name}"\n      path: "{path}"\n    }}'
        for name, path in deps.items()
    )
    content = (
        f"deps: {{\n  local: [\n    {entries}\n  ]\n}}\n" if deps else "deps: {}\n"
    )
    (deps_dir / "local.defcl").write_text(content, encoding="utf-8", newline="\n")
