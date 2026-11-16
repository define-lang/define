"""Concurrent resolution of Value Operations."""

# This file exists only to test that concurrent resolution is safe, which
# tests that validate whole programs cannot do, because they cannot make two
# threads resolve the same key at the same time. Do not add tests of what
# resolution produces here. Add them as testdata cases instead.

from __future__ import annotations

import threading
import typing
from collections import UserDict

from define.compiler.association_resolution import (
    associations,
    concrete_program,
    literal_encoder,
    value_operation_resolver,
)
from define.compiler.data_structures import typed_name_dict
from define.compiler.parsing import test_helpers

if typing.TYPE_CHECKING:
    import pytest

    from define.compiler import ast
    from define.compiler.validator import validation_result


_SOURCE = (
    "define the operation<my.domain.com:my_lib:/copy> {\n"
    "    define the view<source> {\n"
    "        it is read.\n"
    "        it may only contain particles where {\n"
    "            it has the value<standard:/number/natural>.\n"
    "        }\n"
    "    }\n"
    "\n"
    "    it does {\n"
    "        set the value of view<source> from view<source>.\n"
    "    }\n"
    "}\n"
)


def test_concurrent_resolutions_work_out_each_key_once(
    monkeypatch: pytest.MonkeyPatch,
):
    [definition] = test_helpers.parse(_SOURCE).definitions
    value_operation = typing.cast("ast.ValueOperationDefinition", definition)
    [view] = value_operation.views
    value_quality = view.quality_assignment_block.value_quality
    assert value_quality is not None
    view_encodings = {view.typed_name.source_typed_name: value_quality}
    definition_results: typed_name_dict.TypedNameDict[
        ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
        validation_result.DefinitionValidationResult,
    ] = typed_name_dict.TypedNameDict()
    resolver = value_operation_resolver.ValueOperationResolver(
        associations.Associations(definition_results),
        literal_encoder.LiteralEncoder(definition_results),
    )
    first_is_resolving = threading.Event()
    finish_first = threading.Event()
    resolutions: list[ast.ValueOperationDefinition] = []
    composite = concrete_program.CompositeValueOperation(
        definition=value_operation, view_encodings=view_encodings, steps=[]
    )
    resolved = concrete_program.OperationExecution(
        runtime_operation=composite, arguments=[]
    )

    def resolve_slowly(
        operation: ast.ValueOperationDefinition,
        _view_encodings: dict[str, ast.GlobalTypedNameReference],
    ) -> tuple[
        value_operation_resolver.ResolvedValueOperation,
        concrete_program.CompositeValueOperation | None,
    ]:
        resolutions.append(operation)
        first_is_resolving.set()
        _ = finish_first.wait()
        return resolved, composite

    monkeypatch.setattr(resolver, "_resolve_uncached_value_operation", resolve_slowly)
    second_found_no_resolution = threading.Event()

    class _Locks(UserDict[object, threading.Lock]):
        """Signals when a thread that found no resolution gets a key's lock."""

        @typing.override
        def setdefault(self, key: object, default: threading.Lock) -> threading.Lock:
            lock = super().setdefault(key, default)
            if first_is_resolving.is_set():
                second_found_no_resolution.set()
            return lock

    monkeypatch.setattr(resolver, "_resolution_locks", _Locks())
    results: list[value_operation_resolver.ResolvedValueOperation] = []

    def resolve():
        results.append(resolver.resolve(value_operation, view_encodings))

    first = threading.Thread(target=resolve)
    first.start()
    _ = first_is_resolving.wait()
    # The second thread finds no resolution yet, so it waits for the first
    # thread's lock, and then finds the resolution the first thread stored.
    second = threading.Thread(target=resolve)
    second.start()
    _ = second_found_no_resolution.wait()
    finish_first.set()
    first.join()
    second.join()

    assert resolutions == [value_operation]
    assert results == [resolved, resolved]
