from __future__ import annotations

import typing

from tools import runfiles, sync_agent_permissions

if typing.TYPE_CHECKING:
    import pytest


def test_agent_permissions_match_claude_settings(capsys: pytest.CaptureFixture[str]):
    base_dir = runfiles.resolve_from_env("CLAUDE_SETTINGS").parent.parent
    sync_agent_permissions.check_permissions(base_dir)
    assert capsys.readouterr().out == ""
