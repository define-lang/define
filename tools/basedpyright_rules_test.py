from __future__ import annotations

import tomllib
from pathlib import Path
from typing import cast

from tools import basedpyright_rules, runfiles


def test_pyproject_enables_every_basedpyright_rule():
    with Path(runfiles.resolve_from_env("PYPROJECT")).open("rb") as pyproject_file:
        pyproject = tomllib.load(pyproject_file)
    tool_config = cast("dict[str, dict[str, object]]", pyproject["tool"])

    # Fix type errors in source code instead of disabling rules.
    assert basedpyright_rules.rule_disabling_settings(tool_config["basedpyright"]) == []


def test_settings_that_enable_rules_are_allowed():
    assert (
        basedpyright_rules.rule_disabling_settings(
            {
                "stubPath": "typestubs",
                "typeCheckingMode": "all",
                "failOnWarnings": True,
                "reportAny": True,
                "reportUnusedCallResult": "error",
                "reportImplicitOverride": "warning",
            }
        )
        == []
    )


def test_settings_that_disable_or_weaken_rules_are_found():
    assert basedpyright_rules.rule_disabling_settings(
        {
            "typeCheckingMode": "strict",
            "failOnWarnings": False,
            "reportAny": False,
            "reportUnusedCallResult": "none",
            "reportImplicitOverride": "information",
            "reportMissingTypeStubs": "hint",
        }
    ) == [
        "typeCheckingMode = 'strict'",
        "failOnWarnings = False",
        "reportAny = False",
        "reportUnusedCallResult = 'none'",
        "reportImplicitOverride = 'information'",
        "reportMissingTypeStubs = 'hint'",
    ]
