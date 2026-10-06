from __future__ import annotations

import threading
import typing

import pytest

from define.compiler import ast
from define.compiler.graphs import reference_graph_executor
from define.compiler.validator import test_helpers
from define.compiler.validator.structural import program_validator

if typing.TYPE_CHECKING:
    from define.compiler.graphs import reference_graph_order

_SOURCE = """\
define the potential position<my.domain.com:lib:/base>.
define the potential action<my.domain.com:lib:/left> {
    it happens when {
        this particle is created.
    } and it does {
        define the position<source> {
            it may only contain particles where {
                it has the position</base>.
            }
        }
        create a particle in position<source>.
    }
}
define the potential action<my.domain.com:lib:/right> {
    it happens when {
        this particle is created.
    } and it does {
        define the position<source> {
            it may only contain particles where {
                it has the position</base>.
            }
        }
        create a particle in position<source>.
    }
}
define the potential position<my.domain.com:lib:/joined> {
    it may only contain particles where {
        it has the action</left>.
        it has the action</right>.
    }
}
define the potential position<my.domain.com:lib:/independent>.
"""


def _order() -> reference_graph_order.ReferenceGraphOrder:
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            _SOURCE, max_workers=1
        )
    )
    test_helpers.assert_no_errors(result)
    return result.definition_order


def _is_position(
    definition: ast.GlobalDefinition,
) -> typing.TypeIs[ast.PositionDefinition]:
    return isinstance(definition, ast.PositionDefinition)


def _is_operation(
    definition: ast.GlobalDefinition,
) -> typing.TypeIs[ast.OperationDefinition]:
    return isinstance(definition, ast.OperationDefinition)


@pytest.mark.parametrize("max_workers", [1, 4])
def test_failed_shared_dependency_prevents_both_paths(max_workers: int):
    order = _order()
    processed: set[str] = set()
    lock = threading.Lock()
    failure = RuntimeError("base processing failed")

    def process(definition: ast.GlobalDefinition) -> str:
        name = definition.typed_name.full_typed_name
        with lock:
            processed.add(name)
        if name == "position<my.domain.com:lib:/base>":
            raise failure
        return name

    with pytest.raises(RuntimeError, match="base processing failed") as raised:
        _ = reference_graph_executor.process_definitions(
            order, process, max_workers=max_workers
        )
    assert raised.value is failure
    assert processed == {
        "position<my.domain.com:lib:/base>",
        "position<my.domain.com:lib:/independent>",
    }


@pytest.mark.parametrize("max_workers", [1, 4])
def test_order_can_be_reused_for_multiple_passes(max_workers: int):
    order = _order()
    dependencies: dict[str, set[str]] = {
        "position<my.domain.com:lib:/base>": set(),
        "action<my.domain.com:lib:/left>": {"position<my.domain.com:lib:/base>"},
        "action<my.domain.com:lib:/right>": {"position<my.domain.com:lib:/base>"},
        "position<my.domain.com:lib:/joined>": {
            "action<my.domain.com:lib:/left>",
            "action<my.domain.com:lib:/right>",
        },
        "position<my.domain.com:lib:/independent>": set(),
    }

    def assert_pass_results(pass_number: int):
        processed: set[str] = set()
        lock = threading.Lock()

        def process(definition: ast.GlobalDefinition) -> tuple[int, str]:
            name = definition.typed_name.full_typed_name
            with lock:
                assert name not in processed
                assert dependencies[name] <= processed
                processed.add(name)
            return pass_number, name

        results = reference_graph_executor.process_definitions(
            order, process, max_workers=max_workers
        )
        expected: list[tuple[int, str]] = []
        for definition in order.definitions:
            expected.append((pass_number, definition.typed_name.full_typed_name))
        assert results == expected
        assert processed == set(dependencies)

    assert_pass_results(0)
    assert_pass_results(1)


@pytest.mark.parametrize("max_workers", [1, 4])
def test_failed_dependency_prevents_dependents_of_unprocessed_definitions(
    max_workers: int,
):
    order = _order()
    processed: set[str] = set()
    lock = threading.Lock()
    failure = RuntimeError("base processing failed")

    def process(definition: ast.PositionDefinition) -> str:
        name = definition.typed_name.full_typed_name
        with lock:
            processed.add(name)
        if name == "position<my.domain.com:lib:/base>":
            raise failure
        return name

    with pytest.raises(RuntimeError, match="base processing failed") as raised:
        _ = reference_graph_executor.process_selected_definitions(
            order, _is_position, process, max_workers=max_workers
        )
    assert raised.value is failure
    assert processed == {
        "position<my.domain.com:lib:/base>",
        "position<my.domain.com:lib:/independent>",
    }


@pytest.mark.parametrize("max_workers", [1, 4])
def test_unprocessed_definitions_preserve_reference_order(max_workers: int):
    order = _order()
    processed: set[str] = set()
    lock = threading.Lock()

    def process(definition: ast.PositionDefinition) -> str:
        name = definition.typed_name.full_typed_name
        with lock:
            assert name not in processed
            if name == "position<my.domain.com:lib:/joined>":
                assert "position<my.domain.com:lib:/base>" in processed
            processed.add(name)
        return name

    results = reference_graph_executor.process_selected_definitions(
        order, _is_position, process, max_workers=max_workers
    )
    assert results == [
        "position<my.domain.com:lib:/base>",
        "position<my.domain.com:lib:/joined>",
        "position<my.domain.com:lib:/independent>",
    ]


def test_no_definitions_require_processing():
    order = _order()

    def process(definition: ast.OperationDefinition) -> str:
        raise AssertionError(definition.typed_name.full_typed_name)

    results = reference_graph_executor.process_selected_definitions(
        order, _is_operation, process, max_workers=1
    )
    assert results == []


def test_none_is_a_processed_result():
    order = _order()
    processed: list[str] = []

    def process(definition: ast.GlobalDefinition):
        processed.append(definition.typed_name.full_typed_name)

    results = reference_graph_executor.process_definitions(
        order, process, max_workers=1
    )
    assert results == [None, None, None, None, None]
    assert sorted(processed) == [
        "action<my.domain.com:lib:/left>",
        "action<my.domain.com:lib:/right>",
        "position<my.domain.com:lib:/base>",
        "position<my.domain.com:lib:/independent>",
        "position<my.domain.com:lib:/joined>",
    ]
