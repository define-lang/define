from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import pytest

from define.compiler.graphs import reference_graph_executor
from define.compiler.validator import test_helpers
from define.compiler.validator.structural import program_validator

if TYPE_CHECKING:
    from define.compiler import ast

_SOURCE = """\
define the potential position<my.domain.com:lib:/base>.
define the potential position<my.domain.com:lib:/left> {
    it may only contain particles where {
        it has the position</base>.
    }
}
define the potential position<my.domain.com:lib:/right> {
    it may only contain particles where {
        it has the position</base>.
    }
}
define the potential position<my.domain.com:lib:/joined> {
    it may only contain particles where {
        it has the position</left>.
        it has the position</right>.
    }
}
define the potential position<my.domain.com:lib:/independent>.
"""


def _order() -> reference_graph_executor.ReferenceGraphOrder:
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            _SOURCE, max_workers=1
        )
    )
    test_helpers.assert_no_errors(result)
    return reference_graph_executor.ReferenceGraphOrder(result.reference_graph)


@pytest.mark.parametrize("max_workers", [1, 4])
def test_failed_shared_dependency_prevents_both_paths(max_workers: int):
    order = _order()
    processed: set[str] = set()
    lock = threading.Lock()
    failure = RuntimeError("base processing failed")

    def process(definition: ast.QualityDefinition) -> str:
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
        "position<my.domain.com:lib:/left>": {"position<my.domain.com:lib:/base>"},
        "position<my.domain.com:lib:/right>": {"position<my.domain.com:lib:/base>"},
        "position<my.domain.com:lib:/joined>": {
            "position<my.domain.com:lib:/left>",
            "position<my.domain.com:lib:/right>",
        },
        "position<my.domain.com:lib:/independent>": set(),
    }

    def run_pass(pass_number: int):
        processed: set[str] = set()
        lock = threading.Lock()

        def process(definition: ast.QualityDefinition) -> tuple[int, str]:
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

    run_pass(0)
    run_pass(1)
