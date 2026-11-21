"""The program's project roots, used from several threads.

These tests cover only what happens when several threads load at once. The
tests that compile testdata projects cover what loading does.
"""

from __future__ import annotations

import threading
import typing

from crates.source_rendering.python import rendering
from define.compiler import constants
from define.compiler.config import project_config, project_roots

if typing.TYPE_CHECKING:
    import types
    from collections.abc import Callable
    from pathlib import Path

    import pytest

    from define.compiler.config import (
        association_config,
        config_loader,
        local_deps_config,
    )
    from define.compiler.data_structures import define_path


@typing.final
class _SignalingLock:
    """A reentrant lock that signals when a thread starts to wait for it while another thread loads."""

    def __init__(self, first_is_loading: threading.Event):
        self._lock = threading.RLock()
        self._first_is_loading = first_is_loading
        self.second_is_waiting = threading.Event()

    def __enter__(self) -> bool:
        if self._first_is_loading.is_set():
            self.second_is_waiting.set()
        return self._lock.__enter__()

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: types.TracebackType | None,
    ):
        self._lock.__exit__(exception_type, exception, traceback)


def _read_while_first_loads(
    read: Callable[[], None],
    first_is_loading: threading.Event,
    lock: _SignalingLock,
    finish_first: threading.Event,
):
    """Read from two threads, where the second waits for the lock while the first loads."""

    def read_then_set(finished: threading.Event):
        # A thread that ends without reaching the step that sets its event
        # still sets the event, so that the test fails instead of hanging.
        try:
            read()
        finally:
            finished.set()

    first = threading.Thread(target=read_then_set, args=(first_is_loading,))
    first.start()
    _ = first_is_loading.wait()
    # The second thread finds nothing loaded yet, so it waits for the first
    # thread's lock, and then finds what the first thread stored.
    second = threading.Thread(target=read_then_set, args=(lock.second_is_waiting,))
    second.start()
    _ = lock.second_is_waiting.wait()
    finish_first.set()
    first.join()
    second.join()


def test_concurrent_reads_load_each_association_table_once(
    monkeypatch: pytest.MonkeyPatch,
):
    roots = project_roots.ProjectRoots(rendering.SourceMap())
    first_is_loading = threading.Event()
    finish_first = threading.Event()
    loads: list[str] = []
    table = project_roots.NoProjectConfig()

    def load_slowly(
        universe: str,
    ) -> association_config.AssociationTable | project_roots.NoProjectConfig:
        loads.append(universe)
        # A second load fails the test, so only the first load waits.
        if len(loads) == 1:
            first_is_loading.set()
            _ = finish_first.wait()
        return table

    monkeypatch.setattr(roots, "_read_association_table", load_slowly)
    lock = _SignalingLock(first_is_loading)
    monkeypatch.setattr(roots, "_lock", lock)
    results: list[
        association_config.AssociationTable | project_roots.NoProjectConfig
    ] = []

    def read():
        results.append(roots.get_association_table("my.domain.com:my_lib"))

    _read_while_first_loads(read, first_is_loading, lock, finish_first)

    assert loads == ["my.domain.com:my_lib"]
    assert results == [table, table]


def test_concurrent_reads_load_the_project_root_config_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    config_path = tmp_path / str(project_config.CONFIG_FILE.path)
    config_path.parent.mkdir(parents=True)
    config_path.touch()
    monkeypatch.chdir(tmp_path)
    roots = project_roots.ProjectRoots(rendering.SourceMap())
    first_is_loading = threading.Event()
    finish_first = threading.Event()
    loads: list[define_path.DefinePath] = []
    config = typing.cast("config_loader.Config", object())
    configs: dict[define_path.DefinePath, config_loader.Config] = {}
    monkeypatch.setattr(roots, "_configs", configs)

    def load_slowly(
        root: define_path.DefinePath,
        _declaring_entry: local_deps_config.LocalDependencyEntry | None,
    ) -> config_loader.Config | None:
        loads.append(root)
        # A second load fails the test, so only the first load waits.
        if len(loads) == 1:
            first_is_loading.set()
            _ = finish_first.wait()
        configs[root] = config
        return config

    monkeypatch.setattr(roots, "_load", load_slowly)
    lock = _SignalingLock(first_is_loading)
    monkeypatch.setattr(roots, "_lock", lock)
    results: list[config_loader.Config | project_roots.NoProjectConfig | None] = []

    def read():
        results.append(roots.load_project_root_config())

    _read_while_first_loads(read, first_is_loading, lock, finish_first)

    assert len(loads) == 1
    assert results == [config, config]


def test_concurrent_reads_load_each_sub_root_config_once(
    monkeypatch: pytest.MonkeyPatch,
):
    roots = project_roots.ProjectRoots(rendering.SourceMap())
    first_is_loading = threading.Event()
    finish_first = threading.Event()
    loads: list[define_path.DefinePath] = []
    config = typing.cast("config_loader.Config", object())
    configs: dict[define_path.DefinePath, config_loader.Config] = {}
    monkeypatch.setattr(roots, "_configs", configs)

    def load_slowly(
        root: define_path.DefinePath,
        _declaring_entry: local_deps_config.LocalDependencyEntry | None,
    ) -> config_loader.Config | None:
        loads.append(root)
        # A second load fails the test, so only the first load waits.
        if len(loads) == 1:
            first_is_loading.set()
            _ = finish_first.wait()
        configs[root] = config
        return config

    monkeypatch.setattr(roots, "_load", load_slowly)
    lock = _SignalingLock(first_is_loading)
    monkeypatch.setattr(roots, "_lock", lock)
    results: list[tuple[define_path.DefinePath, config_loader.Config] | None] = []

    def read():
        results.append(
            roots.load_sub_root_config(
                constants.STANDARD_UNIVERSE, constants.PROJECT_ROOT
            )
        )

    _read_while_first_loads(read, first_is_loading, lock, finish_first)

    assert loads == [constants.STANDARD_LIBRARY_ROOT]
    assert results == [
        (constants.STANDARD_LIBRARY_ROOT, config),
        (constants.STANDARD_LIBRARY_ROOT, config),
    ]
