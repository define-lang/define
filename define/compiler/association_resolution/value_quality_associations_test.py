"""Concurrent lookups of value qualities' encodings."""

# This file exists only to test that concurrent lookups are safe, which tests
# that validate whole programs cannot do, because they cannot make two threads
# look up the same value quality at the same time. Do not add tests of what a
# lookup finds here. Add them as testdata cases instead.

from __future__ import annotations

import threading
import typing
from collections import UserDict

from crates.source_rendering.python import rendering
from define.compiler.association_resolution import value_quality_associations
from define.compiler.config import project_roots
from define.compiler.parsing import test_helpers

if typing.TYPE_CHECKING:
    import pytest

    from define.compiler import ast
    from define.compiler.errors import diagnostics
    from define.compiler.graphs import reference_graph


_SOURCE = (
    "define the potential value<my.domain.com:my_lib:/count> {\n"
    "    it supports the logical_operation<standard:/text/less_than> {\n"
    "        it may be read.\n"
    "    }\n"
    "}\n"
    "define the potential position<my.domain.com:my_lib:/count> {\n"
    "    it may only contain particles where {\n"
    "        it has the value</count>.\n"
    "    }\n"
    "}\n"
)


def test_concurrent_lookups_look_up_each_value_encoding_once(
    monkeypatch: pytest.MonkeyPatch,
):
    value, position = test_helpers.parse(_SOURCE).definitions
    value_definition = typing.cast("ast.ValueDefinition", value)
    quality_assignment_block = typing.cast(
        "ast.PositionDefinition", position
    ).quality_assignment_block
    assert quality_assignment_block is not None
    value_quality = quality_assignment_block.value_quality
    assert value_quality is not None
    associations = value_quality_associations.ValueQualityAssociations(
        {value_definition.typed_name.full_typed_name: value_definition},
        project_roots.ProjectRoots(rendering.SourceMap()),
    )
    first_is_looking_up = threading.Event()
    finish_first = threading.Event()
    second_found_no_encoding = threading.Event()
    lookups: list[ast.ValueDefinition] = []

    def look_up_slowly(
        definition: ast.ValueDefinition,
    ) -> tuple[reference_graph.ReferenceEdge | None, list[diagnostics.Diagnostic]]:
        lookups.append(definition)
        first_is_looking_up.set()
        _ = finish_first.wait()
        return None, []

    monkeypatch.setattr(associations, "_value_encoding_edge", look_up_slowly)

    class _Locks(UserDict[str, threading.Lock]):
        """Signals when a thread that found no encoding gets a value quality's lock."""

        @typing.override
        def setdefault(self, key: str, default: threading.Lock) -> threading.Lock:
            lock = super().setdefault(key, default)
            if first_is_looking_up.is_set():
                second_found_no_encoding.set()
            return lock

    monkeypatch.setattr(associations, "_value_encoding_locks", _Locks())
    results: list[ast.GlobalTypedNameReference | None] = []

    def look_up():
        results.append(associations.value_encoding(value_quality))

    first = threading.Thread(target=look_up)
    first.start()
    _ = first_is_looking_up.wait()
    # The second thread finds no encoding yet, so it waits for the first
    # thread's lock, and then finds what the first thread recorded.
    second = threading.Thread(target=look_up)
    second.start()
    _ = second_found_no_encoding.wait()
    finish_first.set()
    first.join()
    second.join()

    assert lookups == [value_definition]
    assert results == [None, None]
