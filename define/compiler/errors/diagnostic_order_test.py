"""The order of the definitions in each diagnostics module."""

from __future__ import annotations

import ast
import inspect
import typing

import pytest

from define.compiler.errors import (
    association_resolution_diagnostics,
    config_diagnostics,
    diagnostics,
    parser_diagnostics,
    reference_graph_diagnostics,
    structural_diagnostics,
)

if typing.TYPE_CHECKING:
    import types

_DIAGNOSTIC_MODULES = (
    association_resolution_diagnostics,
    config_diagnostics,
    diagnostics,
    parser_diagnostics,
    reference_graph_diagnostics,
    structural_diagnostics,
)


def _definition_names(module: types.ModuleType) -> list[str]:
    names: list[str] = []
    for statement in ast.parse(inspect.getsource(module)).body:
        if isinstance(statement, (ast.ClassDef, ast.FunctionDef)):
            names.append(statement.name)
        elif isinstance(statement, ast.TypeAlias):
            names.append(statement.name.id)
    return names


def _is_concrete_diagnostic(value: object) -> bool:
    return (
        isinstance(value, type)
        and issubclass(value, diagnostics.BaseDiagnostic)
        and not value.__subclasses__()
    )


@pytest.mark.parametrize(
    "module",
    _DIAGNOSTIC_MODULES,
    ids=[module.__name__ for module in _DIAGNOSTIC_MODULES],
)
def test_base_classes_and_helpers_then_diagnostics_alphabetically(
    module: types.ModuleType,
):
    names = _definition_names(module)
    namespace: dict[str, object] = dict(vars(module))
    base_classes_and_helpers = sorted(
        name for name in names if not _is_concrete_diagnostic(namespace[name])
    )
    concrete_diagnostics = sorted(
        name for name in names if _is_concrete_diagnostic(namespace[name])
    )
    assert names == base_classes_and_helpers + concrete_diagnostics
