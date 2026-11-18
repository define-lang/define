from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tools.bazel_mutation_testing import results

if TYPE_CHECKING:
    import pathlib

_RUN = results.Run(commit="0123abcd", area=["//crates/..."], test_timeout=60)
_KILLED = results.Result(
    name="crates/example/lib.rs:5:10: replace > with == in is_larger",
    outcome=results.Outcome.KILLED,
    culprit="//crates/example:example_test",
    seconds=0.5,
)
_SURVIVED = results.Result(
    name="crates/example/lib.rs:5:10: replace > with >= in is_larger",
    outcome=results.Outcome.SURVIVED,
    culprit=None,
    seconds=0.4,
)


def test_new_store_is_empty(tmp_path: pathlib.Path):
    with results.Store(tmp_path / "store/results.jsonl", _RUN) as store:
        assert store.results == {}


def test_reopened_store_resumes(tmp_path: pathlib.Path):
    path = tmp_path / "results.jsonl"
    with results.Store(path, _RUN) as store:
        store.add(_KILLED)
        store.add(_SURVIVED)

    with results.Store(path, _RUN) as reopened:
        assert reopened.results == {_KILLED.name: _KILLED, _SURVIVED.name: _SURVIVED}


def test_store_of_another_run_is_refused(tmp_path: pathlib.Path):
    path = tmp_path / "results.jsonl"
    with results.Store(path, _RUN):
        pass
    with pytest.raises(results.MismatchedRunError):
        _ = results.Store(
            path, results.Run(commit="0123abcd", area=["//crates/..."], test_timeout=10)
        )


def test_unfinished_last_result_is_dropped(tmp_path: pathlib.Path):
    path = tmp_path / "results.jsonl"
    with results.Store(path, _RUN) as store:
        store.add(_KILLED)
    complete = path.read_bytes()
    with path.open("ab") as unfinished:
        _ = unfinished.write(b'{"name":"crates/exam')

    with results.Store(path, _RUN) as reopened:
        assert reopened.results == {_KILLED.name: _KILLED}
    assert path.read_bytes() == complete


def test_duplicate_results_are_refused(tmp_path: pathlib.Path):
    path = tmp_path / "results.jsonl"
    with results.Store(path, _RUN) as store:
        store.add(_KILLED)
        store.add(_KILLED)
    with pytest.raises(results.DuplicateResultError):
        _ = results.Store(path, _RUN)
