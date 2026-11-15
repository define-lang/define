from __future__ import annotations

import tomllib
from pathlib import Path
from typing import cast

from tools import runfiles, rustc_lints


def _named_lints() -> list[str]:
    with Path(runfiles.resolve_from_env("CARGO_TOML")).open("rb") as cargo_file:
        cargo = tomllib.load(cargo_file)
    workspace = cast("dict[str, dict[str, dict[str, object]]]", cargo["workspace"])
    return list(workspace["lints"]["rust"])


def test_cargo_toml_names_every_lint_that_rustc_leaves_off():
    # Deny each new lint, or allow it with the reason that it does not fit.
    assert (
        rustc_lints.unnamed_lints(runfiles.resolve_from_env("RUSTC"), _named_lints())
        == []
    )


def test_lint_missing_from_the_table_is_found():
    named_lints = [lint for lint in _named_lints() if lint != "unused_results"]

    assert rustc_lints.unnamed_lints(
        runfiles.resolve_from_env("RUSTC"), named_lints
    ) == ["unused_results"]
