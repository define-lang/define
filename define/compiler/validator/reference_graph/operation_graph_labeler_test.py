from __future__ import annotations

from typing import TYPE_CHECKING

from define.compiler.validator import test_helpers
from define.compiler.validator.reference_graph import (
    operation_graph_labeler,
    operation_graph_resolver,
)

if TYPE_CHECKING:
    from define.compiler import conftest


def _resolved(
    result: conftest.FullValidationResult,
) -> tuple[
    operation_graph_labeler.OperationGraphLabeler,
    operation_graph_resolver.ResolvedOperationGraph,
]:
    test_helpers.assert_no_errors(result.program_result)
    entry_action = next(
        action
        for action in result.operation_graphs
        if action.name_content.path.name == "/test"
    )
    resolved = operation_graph_resolver.ResolvedOperationGraphBuilder(
        result.operation_graphs,
        entry_action,
    ).build()
    return (
        operation_graph_labeler.OperationGraphLabeler(result.operation_graphs),
        resolved,
    )


def _resolved_labels(result: conftest.FullValidationResult) -> list[str]:
    labels, resolved = _resolved(result)
    return list(labels.resolved_operation_labels(resolved).values())


def test_duplicate_operations_receive_numbered_labels(
    validate_project: conftest.ValidateProject,
):
    result = validate_project(
        {
            "test.dfn": """\
define the potential action<my.domain.com:my_lib:/test> {
    define the position<item>.
    it happens when {
        this particle is created.
    } and it does {
        create a particle in position<item>.
        destroy the particle in position<item>.
        create a particle in position<item>.
    }
}
"""
        }
    )

    assert _resolved_labels(result) == [
        "test.create(item)",
        "test.destroy(item)",
        "test.create(item)#2",
    ]
    labels, resolved = _resolved(result)
    assert [
        labels.operation_label(
            operation.action_execution.action,
            operation.operation,
        )
        for operation in resolved.operations
    ] == [
        operation_graph_labeler.OperationLabel("create", None, "item", 1),
        operation_graph_labeler.OperationLabel("destroy", None, "item", 1),
        operation_graph_labeler.OperationLabel("create", None, "item", 2),
    ]


def test_repeated_action_triggerings_receive_numbered_execution_names(
    validate_project: conftest.ValidateProject,
):
    result = validate_project(
        {
            "test.dfn": """\
define the potential action<my.domain.com:my_lib:/test> {
    define the position<gateway> {
        it may only contain particles where {
            it has the action</other>.
        }
    }
    it happens when {
        this particle is created.
    } and it does {
        create a particle in position<gateway>.
        create a particle in position<gateway>::action</other>::position<trigger_pos>.
        create a particle in position<gateway>::action</other>::position<trigger_pos>.
    }
}
""",
            "other.dfn": """\
define the potential action<my.domain.com:my_lib:/other> {
    define the position<trigger_pos>.
    it happens when {
        the position<trigger_pos> has a particle.
    } and it does {
        destroy the particle in position<trigger_pos>.
    }
}
""",
        }
    )

    assert _resolved_labels(result) == [
        "test.create(gateway)",
        "test.create(gateway::/other::trigger_pos)",
        "test.create(gateway::/other::trigger_pos)#2",
        "other.destroy(trigger_pos)",
        "other#2.destroy(trigger_pos)",
    ]


def test_shared_callee_names_include_the_caller_execution_name(
    validate_project: conftest.ValidateProject,
):
    result = validate_project(
        {
            "test.dfn": """\
define the potential action<my.domain.com:my_lib:/test> {
    define the position<holder_first> {
        it may only contain particles where {
            it has the action</first>.
        }
    }
    define the position<holder_second> {
        it may only contain particles where {
            it has the action</second>.
        }
    }
    it happens when {
        this particle is created.
    } and it does {
        create a particle in position<holder_first>.
        create a particle in position<holder_first>::action</first>::position<trigger_pos>.
        create a particle in position<holder_second>.
        create a particle in position<holder_second>::action</second>::position<trigger_pos>.
    }
}
""",
            "first.dfn": """\
define the potential action<my.domain.com:my_lib:/first> {
    define the position<trigger_pos>.
    it happens when {
        the position<trigger_pos> has a particle.
    } and it does {
        define the position<gateway> {
            it may only contain particles where {
                it has the action</worker>.
            }
        }
        create a particle in position<gateway>.
        create a particle in position<gateway>::action</worker>::position<trigger_pos>.
    }
}
""",
            "second.dfn": """\
define the potential action<my.domain.com:my_lib:/second> {
    define the position<trigger_pos>.
    it happens when {
        the position<trigger_pos> has a particle.
    } and it does {
        define the position<gateway> {
            it may only contain particles where {
                it has the action</worker>.
            }
        }
        create a particle in position<gateway>.
        create a particle in position<gateway>::action</worker>::position<trigger_pos>.
    }
}
""",
            "worker.dfn": """\
define the potential action<my.domain.com:my_lib:/worker> {
    define the position<trigger_pos>.
    it happens when {
        the position<trigger_pos> has a particle.
    } and it does {
        define the position<work>.
        create a particle in position<work>.
    }
}
""",
        }
    )

    assert _resolved_labels(result) == [
        "test.create(holder_first)",
        "test.create(holder_first::/first::trigger_pos)",
        "test.create(holder_second)",
        "test.create(holder_second::/second::trigger_pos)",
        "first.create(gateway)",
        "first.create(gateway::/worker::trigger_pos)",
        "first.destroy(gateway::/worker::trigger_pos)",
        "first.destroy(gateway)",
        "first:worker.create(work)",
        "first:worker.destroy(work)",
        "second.create(gateway)",
        "second.create(gateway::/worker::trigger_pos)",
        "second.destroy(gateway::/worker::trigger_pos)",
        "second.destroy(gateway)",
        "second:worker.create(work)",
        "second:worker.destroy(work)",
    ]
