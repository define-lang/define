# Rejected: ruff:RUF100
# Rejected in mutation runs: nothing
"""An assignment whose value became None, which leaves a noqa comment unused."""

from __future__ import annotations


def guest_login() -> dict[str, str | None]:
    """Return the login that a guest uses."""
    token = None  # noqa: S105
    return {"user": "guest", "token": token}
