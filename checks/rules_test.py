from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import cast

import yaml
from python.runfiles import runfiles  # pyright: ignore[reportMissingTypeStubs]

_RULES = Path("checks/rules")
_RULE_TESTS = Path("checks/rule-tests")


def _ids_by_path(directory: Path) -> dict[Path, str]:
    ids: dict[Path, str] = {}
    for path in sorted(directory.glob("*.yml")):
        document = cast("dict[str, object]", yaml.safe_load(path.read_text()))
        ids[path] = cast("str", document["id"])
    return ids


def _ast_grep() -> str:
    runfiles_resolver = runfiles.Runfiles.Create()
    if runfiles_resolver is None:
        raise RuntimeError("Bazel runfiles are unavailable")
    resolved = runfiles_resolver.Rlocation(os.environ["AST_GREP"])
    if resolved is None:
        raise FileNotFoundError(os.environ["AST_GREP"])
    return resolved


def test_rule_ids_match_file_names():
    for path, rule_id in _ids_by_path(_RULES).items():
        assert path.stem == rule_id


def test_rule_test_ids_match_file_names():
    for path, rule_id in _ids_by_path(_RULE_TESTS).items():
        assert path.stem == f"{rule_id}-test"


def test_every_rule_has_rule_tests():
    # ast-grep test silently passes a rule that has no rule tests.
    rule_ids = sorted(_ids_by_path(_RULES).values())
    tested_ids = sorted(_ids_by_path(_RULE_TESTS).values())
    assert tested_ids == rule_ids


def test_rule_tests_pass():
    completed = subprocess.run(
        [_ast_grep(), "test", "--color=never"],
        capture_output=True,
        text=True,
        check=False,
    )
    rule_count = len(_ids_by_path(_RULES))
    # ast-grep test passes without testing anything when it cannot load the rules.
    assert f"test result: ok. {rule_count} passed; 0 failed;" in completed.stdout
    assert completed.returncode == 0
