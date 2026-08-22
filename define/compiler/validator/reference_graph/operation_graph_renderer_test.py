from __future__ import annotations

import pytest

from define.compiler.validator.reference_graph import operation_graph_renderer


def test_assert_transitively_minimal_dependencies_accepts_minimal_graph():
    dependencies = {
        "test.create(shared)": [],
        "test.create(left)": ["test.create(shared)"],
        "test.create(right)": ["test.create(shared)"],
        "test.create(independent)": [],
        "test.destroy(join)": [
            "test.create(left)",
            "test.create(right)",
            "test.create(independent)",
        ],
    }

    operation_graph_renderer.assert_transitively_minimal_dependencies(dependencies)


def test_assert_transitively_minimal_dependencies_rejects_redundant_edge():
    dependencies = {
        "test.create(item)": [],
        "test.move(item, destination)": ["test.create(item)"],
        "test.destroy(destination)": [
            "test.create(item)",
            "test.move(item, destination)",
        ],
    }

    with pytest.raises(AssertionError):
        operation_graph_renderer.assert_transitively_minimal_dependencies(dependencies)
