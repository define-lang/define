from __future__ import annotations

from tools.bazel_mutation_testing import diagnostics


def _diagnostic(code: str | None, message: str = "message") -> str:
    code_json = f'{{"code":"{code}","explanation":null}}' if code else "null"
    return (
        f'{{"$message_type":"diagnostic","message":"{message}","code":{code_json},'
        + '"level":"error","spans":[],"children":[],"rendered":""}\n'
    )


_ABORTING = _diagnostic(None, "aborting due to 1 previous error")


def test_rust_lints_and_errors():
    stderr = _diagnostic("unused_variables") + _diagnostic("E0277") + _ABORTING
    assert diagnostics.action_rejections("Rustc", stderr) == {
        "unused_variables",
        "E0277",
    }


def test_clippy_lints():
    stderr = _diagnostic("clippy::missing_const_for_fn") + _ABORTING
    assert diagnostics.action_rejections("Clippy", stderr) == {
        "clippy::missing_const_for_fn"
    }


def test_lint_action_without_errors_is_unidentified():
    assert diagnostics.action_rejections("Clippy", "") == {diagnostics.UNIDENTIFIED}


def test_other_actions_name_nothing():
    assert diagnostics.action_rejections("Genrule", "generator failed\n") == set()


def test_ast_grep_rules():
    stderr = (
        '{"text":"time.sleep(1)","file":"lib.py","ruleId":"no-sleep",'
        + '"severity":"error","message":"Do not call `sleep`."}\n'
        + '{"text":"x","file":"lib.py","ruleId":"a-hint","severity":"hint",'
        + '"message":"Consider."}\n'
        + "error: 1 error found\n"
    )
    assert diagnostics.action_rejections("AstGrep", stderr) == {"ast-grep:no-sleep"}


def test_ruff_rules():
    stderr = (
        '{"code":"F401","message":"`os` imported but unused","filename":"a.py"}\n'
        + '{"code":null,"message":"unexpected EOF while parsing","filename":"a.py"}\n'
        + "Found 2 errors.\n"
    )
    assert diagnostics.action_rejections("Ruff", stderr) == {
        "ruff:F401",
        diagnostics.UNIDENTIFIED,
    }


def test_error_without_a_code_is_unidentified():
    output = _diagnostic(None, "expected one of `,` or `}`") + _ABORTING
    assert diagnostics.rust_rejections(output) == {diagnostics.UNIDENTIFIED}


def test_rustc_reports_emitted_files_too():
    output = (
        '{"$message_type":"artifact","artifact":"libexample.rmeta","emit":"metadata"}\n'
    )
    assert diagnostics.rust_rejections(output) == set()


def test_pyright_rules():
    log = (
        "Executing tests from //define/compiler:pyright_test\n"
        + '{"pyright": {"file": "a.py", "severity": "error", '
        + '"message": "x is not accessed", "rule": "reportUnusedVariable"}}\n'
        + '{"pyright": {"file": "a.py", "severity": "error", '
        + '"message": "Expected expression"}}\n'
    )
    assert diagnostics.test_rejections(log) == {
        "pyright:reportUnusedVariable",
        diagnostics.UNIDENTIFIED,
    }


def test_other_test_logs_name_nothing():
    assert diagnostics.test_rejections("FAILED test_one - assert 1 == 2\n") == set()
