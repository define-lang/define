from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec
import pytest

from tools.profiler import call_tree, tachyon_profile, wall_model, wall_timeline

if TYPE_CHECKING:
    import collections.abc

_MAIN = 42
_WORKER = 43
_WAITER = 44
_FRAMES = [
    wall_model.Frame("/repo/define/compiler/driver.py", "Driver.compile_source", 10),
    wall_model.Frame("/repo/define/compiler/driver.py", "Driver.validate", 20),
    wall_model.Frame("/repo/define/compiler/codegen.py", "generate", 30),
    wall_model.Frame("/repo/define/compiler/main.py", "<module>", 1),
    wall_model.Frame("/usr/lib/python3.15t/threading.py", "Condition.wait", 355),
    wall_model.Frame("/repo/define/compiler/work_pool.py", "WorkPool.run", 40),
]
_COMPILE: tuple[int, ...] = (3, 0)
_VALIDATE: tuple[int, ...] = (3, 0, 1)
_GENERATE: tuple[int, ...] = (3, 0, 2)
_POOL_WAIT: tuple[int, ...] = (3, 0, 5, 4)


def _profile(
    samples_by_thread: collections.abc.Mapping[
        int, collections.abc.Sequence[tuple[bool, tuple[int, ...]] | None]
    ],
) -> tachyon_profile.WallProfile:
    """Build a profile whose samples are one millisecond apart, None where a thread was absent."""
    observation_count = max(len(samples) for samples in samples_by_thread.values())
    return tachyon_profile.WallProfile(
        python_version="3.15.2",
        sample_interval_ns=1_000_000,
        failed_sample_percent=0.0,
        main_thread_id=_MAIN,
        started_ns=0,
        ended_ns=observation_count * 1_000_000,
        frames=_FRAMES,
        observation_count=observation_count,
        samples_by_thread={
            thread_id: [
                wall_model.ThreadSample(
                    interval=wall_model.Interval(
                        index * 1_000_000, (index + 1) * 1_000_000
                    ),
                    running=sample[0],
                    stack=sample[1],
                )
                for index, sample in enumerate(samples)
                if sample is not None
            ]
            for thread_id, samples in samples_by_thread.items()
        },
    )


_SHARED = ("<module main.py>", "Driver.compile_source")
_OPTIONS = wall_timeline.TimelineOptions(depth=1, minimum_run_ns=3_000_000)


def _runs(
    profile: tachyon_profile.WallProfile,
    options: wall_timeline.TimelineOptions = _OPTIONS,
) -> dict[int, list[wall_timeline.Run]]:
    return wall_timeline.thread_runs(profile, options)


def _summary(runs: list[wall_timeline.Run]) -> list[tuple[int, int, int, str]]:
    return [
        (
            run.start_ns // 1_000_000,
            run.end_ns // 1_000_000,
            run.working_ns // 1_000_000,
            wall_timeline.run_label(run.path, _SHARED, 1),
        )
        for run in runs
    ]


def test_consecutive_samples_in_one_state_at_one_label_form_one_run():
    profile = _profile(
        {_MAIN: [(True, _VALIDATE)] * 4 + [(False, _POOL_WAIT)] * 4},
    )

    assert _summary(_runs(profile)[_MAIN]) == [
        (0, 4, 4, "Driver.validate"),
        (4, 8, 0, "WorkPool.run > [Condition.wait]"),
    ]


def test_runs_follow_the_compiler_functions_of_their_stacks():
    profile = _profile(
        {
            _MAIN: [(True, (3,))] * 4 + [(True, _VALIDATE)] * 4,
            _WORKER: [(False, (4,))] * 4 + [(True, ())] * 4,
        },
    )

    runs = _runs(profile)

    assert [run.path for run in runs[_MAIN]] == [
        ("<module main.py>",),
        ("<module main.py>", "Driver.compile_source", "Driver.validate"),
    ]
    assert [run.path for run in runs[_WORKER]] == [
        ("[Condition.wait]",),
        ("(no Python stack)",),
    ]


def test_a_short_change_of_state_joins_its_neighbor_at_the_same_label():
    profile = _profile(
        {
            _MAIN: [(False, _POOL_WAIT)] * 5
            + [(True, _POOL_WAIT)]
            + [(False, _POOL_WAIT)] * 5
        },
    )

    assert _summary(_runs(profile)[_MAIN]) == [
        (0, 11, 1, "WorkPool.run > [Condition.wait]")
    ]


def test_a_short_interruption_joins_the_activity_around_it():
    profile = _profile(
        {
            _MAIN: [(False, _POOL_WAIT)] * 5
            + [(True, _GENERATE)]
            + [(False, _POOL_WAIT)] * 5
        },
    )

    runs = _runs(profile)[_MAIN]

    assert _summary(runs) == [(0, 11, 1, "WorkPool.run > [Condition.wait]")]
    assert wall_timeline.run_breakdown(runs[0], 1) == [
        ("(self)", 10_000_000),
        ("Driver.compile_source > generate", 1_000_000),
    ]


def test_consecutive_short_runs_fold_under_the_label_with_most_of_their_time():
    profile = _profile(
        {
            _MAIN: [(True, _VALIDATE), (True, _GENERATE)] * 3
            + [(True, _VALIDATE)]
            + [(False, _POOL_WAIT)] * 4
        },
    )

    runs = _runs(profile)[_MAIN]

    assert _summary(runs) == [
        (0, 7, 7, "Driver.validate"),
        (7, 11, 0, "WorkPool.run > [Condition.wait]"),
    ]
    assert wall_timeline.run_breakdown(runs[0], 1) == [
        ("(self)", 4_000_000),
        ("Driver.compile_source > generate", 3_000_000),
    ]


def test_short_runs_without_a_majority_call_end_at_the_function_they_share():
    profile = _profile(
        {_MAIN: [(True, _VALIDATE), (True, _GENERATE), (True, _COMPILE)] * 2},
    )

    assert _summary(_runs(profile)[_MAIN]) == [(0, 6, 6, "Driver.compile_source")]


def test_long_work_and_long_waiting_at_one_label_stay_separate():
    profile = _profile(
        {_MAIN: [(True, _POOL_WAIT)] * 4 + [(False, _POOL_WAIT)] * 4},
    )

    assert _summary(_runs(profile)[_MAIN]) == [
        (0, 4, 4, "WorkPool.run > [Condition.wait]"),
        (4, 8, 0, "WorkPool.run > [Condition.wait]"),
    ]


def test_a_lone_short_run_keeps_its_label():
    profile = _profile(
        {
            _MAIN: [(True, _VALIDATE)] * 4
            + [(True, _GENERATE)]
            + [(False, _POOL_WAIT)] * 4
        },
    )

    assert _summary(_runs(profile)[_MAIN]) == [
        (0, 4, 4, "Driver.validate"),
        (4, 5, 1, "generate"),
        (5, 9, 0, "WorkPool.run > [Condition.wait]"),
    ]


def test_options_select_a_time_window_and_threads_with_the_main_thread_first():
    profile = _profile(
        {
            _WORKER: [(True, _GENERATE)] * 8,
            _MAIN: [(True, _VALIDATE)] * 8,
        },
    )

    assert list(_runs(profile)) == [_MAIN, _WORKER]
    window = msgspec.structs.replace(_OPTIONS, start_ns=2_000_000, end_ns=6_000_000)
    assert _summary(_runs(profile, window)[_WORKER]) == [(2, 6, 4, "generate")]
    worker_only = msgspec.structs.replace(_OPTIONS, thread_ids=frozenset({_WORKER}))
    assert list(_runs(profile, worker_only)) == [_WORKER]
    after_samples = msgspec.structs.replace(_OPTIONS, start_ns=20_000_000)
    assert _runs(profile, after_samples) == {}


def test_runs_do_not_span_a_gap_in_a_threads_samples():
    # A later thread can reuse a finished thread's ID.
    profile = _profile(
        {
            _MAIN: [(True, _VALIDATE)] * 4
            + [None, (True, _GENERATE)]
            + [(True, _VALIDATE)] * 4
        },
    )

    assert _summary(_runs(profile)[_MAIN]) == [
        (0, 4, 4, "Driver.validate"),
        (5, 6, 1, "generate"),
        (6, 10, 4, "Driver.validate"),
    ]


def test_report_shows_each_run_with_its_state_and_labels(
    capsys: pytest.CaptureFixture[str],
):
    profile = _profile(
        {
            _MAIN: [(True, _VALIDATE)] * 4
            + [(False, _POOL_WAIT)] * 2
            + [(True, _POOL_WAIT)] * 2,
            _WORKER: [(True, ())] * 4 + [(True, _GENERATE), (True, _VALIDATE)] * 2,
            _WAITER: [(False, _POOL_WAIT)] * 8,
        },
    )

    wall_timeline.emit_report(profile, _runs(profile), 1, 1)

    output = capsys.readouterr().out
    assert output.startswith(
        "Profile: Tachyon wall samples; Python 3.15.2; interval 1.0 ms; "
        + "8 observations; failed samples 0.0%\n"
        + "Wall window: 0.008 s; 3 threads\n"
    )
    assert output.endswith(
        "\nThread 42 (main): 0.000-0.008\n"
        + "  0.000-0.004  work  Driver.validate\n"
        + "  0.004-0.008   50%  WorkPool.run > [Condition.wait]\n"
        + "\nThread 43: 0.000-0.008\n"
        + "  0.000-0.004        (no Python stack)\n"
        + "  0.004-0.008  work  Driver.compile_source\n"
        + "                    2.0 ms  generate\n"
        + "\nThread 44: 0.000-0.008\n"
        + "  0.000-0.008  wait  WorkPool.run > [Condition.wait]\n"
    )


@pytest.mark.parametrize(
    ("filename", "is_compiler"),
    [
        ("/repo/define/compiler/driver.py", True),
        ("/out/main.runfiles/_main/define/compiler/driver.py", True),
        (
            "/out/main.runfiles/_main/define/compiler/._main.venv/lib/python3.15t/"
            + "site-packages/click/core.py",
            False,
        ),
        ("/out/main.runfiles/_main/tools/runfiles.py", False),
        ("/usr/lib/python3.15t/threading.py", False),
    ],
)
def test_compiler_code_excludes_the_compilers_installed_packages(
    filename: str,
    is_compiler: bool,  # noqa: FBT001 - pytest passes parameters positionally.
):
    assert wall_timeline.is_compiler_filename(filename) is is_compiler


def test_weighted_stacks_cover_the_selected_threads_within_the_window():
    profile = _profile(
        {
            _MAIN: [(True, _VALIDATE), (False, _POOL_WAIT), (True, _GENERATE)],
            _WORKER: [(True, _GENERATE)],
        }
    )

    stacks = tachyon_profile.weighted_stacks(
        profile, frozenset({_MAIN}), 500_000, 2_500_000
    )

    assert stacks == [
        call_tree.WeightedStack(
            thread_id=_MAIN,
            functions=("<module main.py>", "Driver.compile_source", "Driver.validate"),
            total_ns=500_000,
            working_ns=500_000,
        ),
        call_tree.WeightedStack(
            thread_id=_MAIN,
            functions=(
                "<module main.py>",
                "Driver.compile_source",
                "WorkPool.run",
                "Condition.wait",
            ),
            total_ns=1_000_000,
            working_ns=0,
        ),
        call_tree.WeightedStack(
            thread_id=_MAIN,
            functions=("<module main.py>", "Driver.compile_source", "generate"),
            total_ns=500_000,
            working_ns=500_000,
        ),
    ]


def test_weighted_stacks_without_a_window_cover_every_sample_of_every_thread():
    profile = _profile({_MAIN: [(True, _COMPILE)], _WORKER: [None, (True, ())]})

    stacks = tachyon_profile.weighted_stacks(profile, frozenset(), None, None)

    assert stacks == [
        call_tree.WeightedStack(
            thread_id=_MAIN,
            functions=("<module main.py>", "Driver.compile_source"),
            total_ns=1_000_000,
            working_ns=1_000_000,
        ),
        call_tree.WeightedStack(
            thread_id=_WORKER, functions=(), total_ns=1_000_000, working_ns=0
        ),
    ]


def test_weighted_stacks_omit_samples_outside_the_window():
    profile = _profile({_MAIN: [(True, _COMPILE), (True, _VALIDATE)]})

    stacks = tachyon_profile.weighted_stacks(profile, frozenset(), 1_000_000, None)

    assert [stack.functions[-1] for stack in stacks] == ["Driver.validate"]


def test_a_short_last_run_joins_its_neighbor_at_the_same_label():
    profile = _profile({_MAIN: [(True, _VALIDATE)] * 4 + [(False, _VALIDATE)]})

    assert _summary(_runs(profile)[_MAIN]) == [(0, 5, 4, "Driver.validate")]


def test_an_interrupted_activity_joins_a_long_run_at_its_label():
    profile = _profile(
        {
            _MAIN: [(True, _VALIDATE)] * 3
            + [(False, _GENERATE)]
            + [(True, _VALIDATE)] * 3
            + [(False, _VALIDATE)] * 3
        },
    )

    runs = _runs(profile)[_MAIN]

    assert _summary(runs) == [(0, 10, 6, "Driver.validate")]
    assert wall_timeline.run_breakdown(runs[0], 1) == [
        ("(self)", 9_000_000),
        ("Driver.compile_source > generate", 1_000_000),
    ]


@pytest.mark.parametrize(
    ("path", "label"),
    [
        (("main", "Driver.run", "validate", "check"), "validate > check"),
        (
            ("main", "Driver.run", "validate", "resolve", "check"),
            "validate > … > check",
        ),
        (("main", "Driver.run"), "Driver.run"),
        (("[Condition.wait]",), "[Condition.wait]"),
        (("main", "Driver.run", "validate", "[Path.open]"), "validate > [Path.open]"),
        (
            ("main", "Driver.run", "validate", "write", "[Path.open]"),
            "validate > write > [Path.open]",
        ),
        (("main", "Driver.run", "[Path.open]"), "Driver.run > [Path.open]"),
        ((), "(mixed)"),
    ],
)
def test_labels_start_below_the_shared_path_and_end_at_the_innermost_function(
    path: tuple[str, ...], label: str
):
    assert wall_timeline.run_label(path, ("main", "Driver.run"), 1) == label


def test_the_shared_path_is_what_nearly_all_of_a_threads_time_shares():
    profile = _profile(
        {_MAIN: [(True, _VALIDATE)] * 9 + [(True, _GENERATE)] * 9 + [(True, (3,))]}
    )

    assert wall_timeline.shared_prefix(_runs(profile)[_MAIN]) == (
        "<module main.py>",
        "Driver.compile_source",
    )


def test_breakdown_names_calls_outside_the_runs_path_from_where_they_leave_it():
    run = wall_timeline.Run(
        start_ns=0,
        end_ns=10,
        working_ns=10,
        path=("main", "validate"),
        path_durations={
            ("main", "validate"): 6,
            ("main", "generate", "write", "flush", "[Path.open]"): 3,
            ("[Condition.wait]",): 1,
        },
        path_working={
            ("main", "validate"): 6,
            ("main", "generate", "write", "flush", "[Path.open]"): 3,
            ("[Condition.wait]",): 0,
        },
    )

    assert wall_timeline.run_breakdown(run, 1) == [
        ("(self)", 6),
        ("main > generate > … > flush > [Path.open]", 3),
        ("[Condition.wait]", 1),
    ]


def _after_legend(output: str) -> list[str]:
    return output.split("Other labels are as in the timeline.\n")[1].splitlines()


def test_critical_path_follows_the_threads_the_main_thread_waits_on(
    capsys: pytest.CaptureFixture[str],
):
    profile = _profile(
        {
            _MAIN: [(True, _VALIDATE)] * 4 + [(False, _POOL_WAIT)] * 8,
            _WORKER: [None] * 6 + [(True, _GENERATE)] * 4,
            _WAITER: [(False, _POOL_WAIT)] * 12,
        },
    )

    wall_timeline.emit_critical_path(profile, _runs(profile), 1)

    assert _after_legend(capsys.readouterr().out) == [
        "",
        "0.000-0.006   0.006 s  thread main  work  67%  Driver.validate",
        "        6.0 ms 100%  work  67%  <module main.py> > Driver.compile_source",
        "          4.0 ms  67%  work 100%  Driver.validate",
        "          2.0 ms  33%  work   0%  WorkPool.run > [Condition.wait]",
        "",
        "0.006-0.010   0.004 s  thread 43  work 100%  generate",
        "        4.0 ms 100%  work 100%  <module main.py> > … > generate",
        "",
        "0.010-0.012   0.002 s  thread main  work   0%  WorkPool.run > [Condition.wait]",
        "        2.0 ms 100%  work   0%  <module main.py> > … > WorkPool.run > [Condition.wait]",
    ]


def test_critical_path_calls_omit_small_calls_and_show_self_time_beside_others(
    capsys: pytest.CaptureFixture[str],
):
    profile = _profile(
        {_MAIN: [(True, _COMPILE)] * 2 + [(True, _VALIDATE)] * 8 + [(True, _GENERATE)]}
    )

    wall_timeline.emit_critical_path(profile, _runs(profile), 1)

    assert _after_legend(capsys.readouterr().out)[1:] == [
        "0.000-0.011   0.011 s  thread main  work 100%  Driver.validate",
        "       11.0 ms 100%  work 100%  <module main.py> > Driver.compile_source",
        "          8.0 ms  73%  work 100%  Driver.validate",
        "          2.0 ms  18%  work 100%  (self)",
    ]


def test_recursive_calls_count_toward_the_outermost_call():
    frames = [
        *_FRAMES,
        wall_model.Frame("/repo/define/compiler/expand.py", "expand", 50),
    ]
    expand = len(frames) - 1
    profile = msgspec.structs.replace(
        _profile({_MAIN: [(True, (3, 0, expand, 1, expand, expand))]}), frames=frames
    )

    assert _runs(profile)[_MAIN][0].path == (
        "<module main.py>",
        "Driver.compile_source",
        "expand",
    )


def test_critical_path_names_other_threads_working_during_a_phase(
    capsys: pytest.CaptureFixture[str],
):
    profile = _profile(
        {
            _MAIN: [(True, _VALIDATE)] * 10,
            _WORKER: [(True, _GENERATE)] * 5 + [(False, _POOL_WAIT)] * 5,
            _WAITER: [(False, _POOL_WAIT)] * 10,
        },
    )

    wall_timeline.emit_critical_path(profile, _runs(profile), 1)

    assert _after_legend(capsys.readouterr().out)[1:] == [
        "0.000-0.010   0.010 s  thread main  work 100%  Driver.validate",
        "       10.0 ms 100%  work 100%  <module main.py> > … > Driver.validate",
        "  meanwhile thread 43 worked 50% of this phase in generate",
    ]
