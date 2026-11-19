"""Name what rejected a mutant in the diagnostics of a failed action."""

from __future__ import annotations

import msgspec

UNIDENTIFIED = "unidentified error"
"""What rejected a mutant when an error names no lint, error code or rule."""


class _Code(msgspec.Struct, frozen=True):
    code: str


class _Message(msgspec.Struct, frozen=True, rename={"message_type": "$message_type"}):
    message_type: str
    # Only diagnostics have these. rustc also reports the files it emits.
    message: str = ""
    level: str = ""
    code: _Code | None = None


_DECODER = msgspec.json.Decoder(_Message)


class _AstGrepMatch(msgspec.Struct, frozen=True, rename="camel"):
    rule_id: str
    severity: str


class _RuffViolation(msgspec.Struct, frozen=True):
    # Ruff gives a syntax error no code.
    code: str | None


class _PyrightDiagnostic(msgspec.Struct, frozen=True):
    # basedpyright gives some errors, such as syntax errors, no rule.
    rule: str | None = None


class _PyrightLine(msgspec.Struct, frozen=True):
    pyright: _PyrightDiagnostic


def _ast_grep_rejections(output: str) -> frozenset[str]:
    decoder = msgspec.json.Decoder(_AstGrepMatch)
    found: set[str] = set()
    for line in output.splitlines():
        if line.startswith("{"):
            match = decoder.decode(line)
            if match.severity == "error":
                found.add(f"ast-grep:{match.rule_id}")
    return frozenset(found)


def _ruff_rejections(output: str) -> frozenset[str]:
    decoder = msgspec.json.Decoder(_RuffViolation)
    found: set[str] = set()
    for line in output.splitlines():
        if line.startswith("{"):
            violation = decoder.decode(line)
            found.add(f"ruff:{violation.code}" if violation.code else UNIDENTIFIED)
    return frozenset(found)


def rust_rejections(output: str) -> frozenset[str]:
    """Return what the errors in rustc's or clippy's JSON `output` name.

    A lint is named as rustc names it in `#[allow(...)]`, and an error by its
    code. An error that names neither is `UNIDENTIFIED`.
    """
    found: set[str] = set()
    for line in output.splitlines():
        if not line.startswith('{"$message_type":'):
            continue
        message = _DECODER.decode(line)
        if (
            message.message_type != "diagnostic"
            or message.level != "error"
            or message.message.startswith("aborting due to")
        ):
            continue
        found.add(message.code.code if message.code else UNIDENTIFIED)
    return frozenset(found)


# What each mutation run's lint actions report, as JSON lines.
_READERS = {
    "AstGrep": _ast_grep_rejections,
    "Clippy": rust_rejections,
    "Ruff": _ruff_rejections,
    "Rustc": rust_rejections,
}


def action_rejections(mnemonic: str, output: str) -> frozenset[str]:
    """Return what rejected a failed action `mnemonic`, from its `output`.

    Rust lints and errors are named as `rust_rejections` names them, an
    ast-grep rule as `ast-grep:<rule id>`, and a Ruff rule as `ruff:<code>`.
    A lint action whose errors name nothing gives `UNIDENTIFIED`; any other
    action gives nothing.
    """
    reader = _READERS.get(mnemonic)
    if reader is None:
        return frozenset()
    return reader(output) or frozenset({UNIDENTIFIED})


def test_rejections(log: str) -> frozenset[str]:
    """Return the rules that a failed test's `log` names.

    Only pyright_test names rules, as `pyright:<rule>`, and only when it reports
    JSON lines. A diagnostic that names no rule is `UNIDENTIFIED`.
    """
    decoder = msgspec.json.Decoder(_PyrightLine)
    found: set[str] = set()
    for line in log.splitlines():
        if line.startswith('{"pyright":'):
            rule = decoder.decode(line).pyright.rule
            found.add(f"pyright:{rule}" if rule else UNIDENTIFIED)
    return frozenset(found)
