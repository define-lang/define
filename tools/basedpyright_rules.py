"""Find basedpyright settings that turn rules off for the whole repository."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

# Warnings fail type checking too, because failOnWarnings is on by default.
_ENABLED_RULE_SEVERITIES = (True, "error", "warning")
# These are the modes that enable every rule.
_FULL_TYPE_CHECKING_MODES = ("recommended", "all")


def _disables_rules(name: str, value: object) -> bool:
    if name.startswith("report"):
        return value not in _ENABLED_RULE_SEVERITIES
    if name == "typeCheckingMode":
        return value not in _FULL_TYPE_CHECKING_MODES
    if name == "failOnWarnings":
        return value is not True
    return False


def rule_disabling_settings(basedpyright_config: Mapping[str, object]) -> list[str]:
    """Return each top-level setting that turns off or weakens a rule."""
    settings: list[str] = []
    for name, value in basedpyright_config.items():
        if _disables_rules(name, value):
            settings.append(f"{name} = {value!r}")
    return settings
