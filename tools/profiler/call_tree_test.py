from __future__ import annotations

import pytest

from tools.profiler import call_tree

_REPORT = call_tree.Report(denominator_ns=10_000_000_000, shows_working=True)


def _stack(
    *functions: str, thread_id: int = 1, seconds: int = 1, working: bool = True
) -> call_tree.WeightedStack:
    duration_ns = seconds * 1_000_000_000
    return call_tree.WeightedStack(
        thread_id=thread_id,
        functions=functions,
        total_ns=duration_ns,
        working_ns=duration_ns if working else 0,
    )


_STACKS = [
    _stack("main", "validate", "check", seconds=4),
    _stack("main", "validate", "validate", seconds=2),
    _stack("main", "generate", seconds=1, working=False),
    _stack(thread_id=2, seconds=3, working=False),
]


def test_names_module_code_by_its_file():
    assert call_tree.function_name("<module>", "/repo/define/config.py") == (
        "<module config.py>"
    )
    assert call_tree.function_name("Driver.run", "/repo/driver.py") == "Driver.run"


@pytest.mark.parametrize(
    ("filename", "module"),
    [
        (
            "/out/main.runfiles/_main/define/compiler/config.py",
            "define.compiler.config",
        ),
        (
            "/venv/lib/python3.15t/site-packages/protovalidate/__init__.py",
            "protovalidate",
        ),
        ("/usr/lib/python3.15t/json/decoder.py", "json.decoder"),
    ],
)
def test_names_module_code_by_its_module_below_an_import_root(
    filename: str, module: str
):
    assert call_tree.function_name("<module>", filename) == f"<module {module}>"


def test_focus_starts_each_stack_at_its_outermost_matching_function():
    assert call_tree.focused(_STACKS, "valid") == [
        _stack("validate", "check", seconds=4),
        _stack("validate", "validate", seconds=2),
    ]


def test_prints_threads_with_their_dominant_functions(
    capsys: pytest.CaptureFixture[str],
):
    call_tree.emit_threads(_STACKS, _REPORT, {1: "(main)"})

    assert capsys.readouterr().out == (
        "Threads, with the deepest function holding most of each one's time:\n"
        + "     7.000 s  70.0%  work  86%  1 (main): check\n"
        + "     3.000 s  30.0%  work   0%  2: (no Python frame)\n"
    )


def test_charges_cumulative_time_once_per_stack_and_self_time_to_the_leaf(
    capsys: pytest.CaptureFixture[str],
):
    call_tree.emit_functions(_STACKS, _REPORT, 2)

    assert capsys.readouterr().out == (
        "\nCumulative:\n"
        + "     7.000 s  70.0%  work  86%  main\n"
        + "     6.000 s  60.0%  work 100%  validate\n"
        + "\nSelf:\n"
        + "     4.000 s  40.0%  work 100%  check\n"
        + "     3.000 s  30.0%  work   0%  (no Python frame)\n"
    )


def test_prints_the_call_tree_without_calls_below_the_minimum_share(
    capsys: pytest.CaptureFixture[str],
):
    call_tree.emit_tree(
        _STACKS,
        call_tree.Report(denominator_ns=10_000_000_000, shows_working=False),
        15.0,
    )

    assert capsys.readouterr().out == (
        "\nCall tree, with each function's own self time:\n"
        + "     7.000 s  70.0%  self  0.0%  main\n"
        + "     6.000 s  60.0%  self  0.0%    validate\n"
        + "     4.000 s  40.0%  self 40.0%      check\n"
        + "     2.000 s  20.0%  self 20.0%      validate\n"
        + "     3.000 s  30.0%  self 30.0%  (no Python frame)\n"
    )


def test_a_thread_without_a_dominant_function_names_none(
    capsys: pytest.CaptureFixture[str],
):
    call_tree.emit_threads(
        [_stack("first"), _stack("second"), _stack("third")], _REPORT, {}
    )

    assert capsys.readouterr().out.splitlines()[1] == (
        "     3.000 s  30.0%  work 100%  1"
    )


def test_callers_invert_the_paths_to_a_function(capsys: pytest.CaptureFixture[str]):
    stacks = [
        _stack("main", "validate", "check", "check", seconds=4),
        _stack("main", "generate", "check", seconds=2),
        _stack("main", "generate", seconds=1),
    ]

    call_tree.emit_callers(stacks, _REPORT, "check", 0.0, 2)

    assert capsys.readouterr().out == (
        "\nCallers of the outermost function containing 'check', each indented "
        + "under the function it calls:\n"
        + "     6.000 s  60.0%  work 100%  check\n"
        + "     4.000 s  40.0%  work 100%    validate\n"
        + "     4.000 s  40.0%  work 100%      main\n"
        + "     2.000 s  20.0%  work 100%    generate\n"
        + "     2.000 s  20.0%  work 100%      main\n"
    )


def test_callers_need_a_matching_function():
    with pytest.raises(ValueError, match=r"^no selected stack contains 'absent'$"):
        call_tree.emit_callers(_STACKS, _REPORT, "absent", 0.0, 2)


def test_callers_stop_at_the_requested_level(capsys: pytest.CaptureFixture[str]):
    call_tree.emit_callers(
        [_stack("main", "validate", "check", seconds=4)], _REPORT, "check", 0.0, 1
    )

    assert capsys.readouterr().out.splitlines()[2:] == [
        "     4.000 s  40.0%  work 100%  check",
        "     4.000 s  40.0%  work 100%    validate",
    ]


def test_call_counts_list_the_matching_functions_called_most(
    capsys: pytest.CaptureFixture[str],
):
    call_tree.emit_call_counts(
        {"validate": 10, "check": 30, "validate_name": 20, "other": 40}, "valid", 5
    )

    assert capsys.readouterr().out.splitlines()[1:] == [
        "             20  validate_name",
        "             10  validate",
    ]
