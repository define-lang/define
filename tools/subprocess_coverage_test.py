from __future__ import annotations

import os
from typing import TYPE_CHECKING

import coverage

from tools import subprocess_coverage

if TYPE_CHECKING:
    import pytest


def test_environment_is_unchanged_without_coverage(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(coverage.Coverage, "current", lambda: None)
    original_environment = dict(os.environ)

    with subprocess_coverage.measure_subprocesses():
        assert dict(os.environ) == original_environment
