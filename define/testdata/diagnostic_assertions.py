"""Find the diagnostic fields that a test function does not assert on."""

from __future__ import annotations

import ast
import copy
import functools
import inspect
from typing import TYPE_CHECKING, cast, override

from define.compiler import diagnostics

if TYPE_CHECKING:
    from collections.abc import Sequence

_DIAGNOSTICS_MODULE = "diagnostics"
_DIAGNOSTIC_LISTS = frozenset({"all_diagnostics", "diagnostics"})
_MESSAGE_PROPERTY = "message"
_LOCATION_TYPE = "SourceLocation"
_LOCATION_FIELDS = ("line", "column", "file_path")

# These helpers assert the complete value of a diagnostic field, so passing a
# diagnostic as their first argument covers that field.
_FIELD_ASSERTION_HELPERS = {"assert_propagation_chain": "propagation_chain"}

# A loop variable stands for this subscript of the list it iterates, so that
# assertions in the loop body apply to every element of the list.
_EACH_ELEMENT = ast.Starred(value=ast.Name(id="each"))
_EACH_ELEMENT_SUFFIX = "[*each]"

type FieldPath = tuple[str, ...]


@functools.cache
def diagnostic_fields() -> dict[str, dict[str, str]]:
    """Return the annotation text of each field of each diagnostic class, by class name."""
    fields_by_class: dict[str, dict[str, str]] = {}
    pending: list[type[diagnostics.Diagnostic]] = [diagnostics.Diagnostic]
    while pending:
        diagnostic_class = pending.pop()
        pending.extend(diagnostic_class.__subclasses__())
        annotations: dict[str, str] = {}
        for ancestor in reversed(diagnostic_class.__mro__):
            annotations.update(inspect.get_annotations(ancestor))
        fields: dict[str, str] = {}
        for field_name in diagnostic_class.__struct_fields__:
            fields[field_name] = annotations[field_name]
        fields_by_class[diagnostic_class.__name__] = fields
    return fields_by_class


def _is_not_none_check(test: ast.Compare) -> bool:
    return (
        len(test.ops) == 1
        and isinstance(test.ops[0], ast.IsNot)
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value is None
    )


class _AliasExpander(ast.NodeTransformer):
    _aliases: dict[str, ast.expr]

    def __init__(self, aliases: dict[str, ast.expr]):
        self._aliases = aliases

    @override
    def visit_Name(self, node: ast.Name) -> ast.expr:
        return copy.deepcopy(self._aliases.get(node.id, node))


class _TestFunctionAssertions:
    """The diagnostics that one test function checks and the fields it asserts on."""

    def __init__(self):
        self._aliases: dict[str, ast.expr] = {}
        self._checked_classes: dict[str, tuple[str, int]] = {}
        self._asserted_paths: dict[str, set[FieldPath]] = {}
        self._diagnostic_uses: dict[str, int] = {}
        self._message_uses: dict[str, int] = {}

    def _expand(self, node: ast.expr) -> ast.expr:
        return cast(
            "ast.expr", _AliasExpander(self._aliases).visit(copy.deepcopy(node))
        )

    def _key(self, node: ast.expr) -> str:
        return ast.unparse(self._expand(node))

    def visit_statements(self, statements: Sequence[ast.stmt]):
        for statement in statements:
            match statement:
                case ast.Assign(targets=[target], value=value):
                    self._assign(target, self._expand(value))
                case ast.For(target=ast.Name(id=name), iter=iterable):
                    self._aliases[name] = ast.Subscript(
                        value=self._expand(iterable), slice=_EACH_ELEMENT
                    )
                    self.visit_statements(statement.body)
                case ast.If() | ast.With():
                    self.visit_statements(statement.body)
                case ast.Assert(test=test):
                    self._visit_assertion(test, statement.lineno)
                case ast.Expr(
                    value=ast.Call(func=ast.Name(id=name), args=[first, *_])
                ) if name in _FIELD_ASSERTION_HELPERS:
                    self._record(first, (_FIELD_ASSERTION_HELPERS[name],))
                case _:
                    pass

    def _assign(self, target: ast.expr, value: ast.expr):
        match target:
            case ast.Name(id=name):
                self._aliases[name] = value
            case ast.Tuple(elts=elements):
                for index, element in enumerate(elements):
                    if isinstance(element, ast.Name):
                        self._aliases[element.id] = ast.Subscript(
                            value=value, slice=ast.Constant(value=index)
                        )
            case _:
                pass

    def _visit_assertion(self, test: ast.expr, line: int):
        self._find_diagnostic_uses(test, line)
        match test:
            case ast.Call(
                func=ast.Name(id="isinstance"),
                args=[
                    checked,
                    ast.Attribute(value=ast.Name(id=module_name), attr=class_name),
                ],
            ) if (
                module_name == _DIAGNOSTICS_MODULE and class_name in diagnostic_fields()
            ):
                self._checked_classes[self._key(checked)] = (class_name, line)
            case ast.Call(func=ast.Name(id="isinstance"), args=[checked, _]):
                self._record_operand(checked)
            case ast.Compare() if _is_not_none_check(test):
                pass
            case ast.Compare(left=left, comparators=comparators):
                for operand in [left, *comparators]:
                    self._record_operand(operand)
            case ast.UnaryOp(op=ast.Not(), operand=operand):
                self._record_operand(operand)
            case ast.BoolOp(op=ast.And(), values=values):
                for value in values:
                    self._visit_assertion(value, line)
            case _:
                self._record_operand(test)

    def _find_diagnostic_uses(self, test: ast.expr, line: int):
        for node in ast.walk(test):
            if not isinstance(node, ast.Attribute):
                continue
            if node.attr == _MESSAGE_PROPERTY:
                _ = self._message_uses.setdefault(self._key(node.value), line)
            match self._expand(node.value):
                case ast.Subscript(value=ast.Attribute(attr=list_name)) as element if (
                    list_name in _DIAGNOSTIC_LISTS
                ):
                    _ = self._diagnostic_uses.setdefault(ast.unparse(element), line)
                case _:
                    pass

    def _record_operand(self, operand: ast.expr):
        self._record(operand, ())
        node = operand
        path: FieldPath = ()
        while isinstance(node, ast.Attribute):
            path = (node.attr, *path)
            node = node.value
            self._record(node, path)

    def _record(self, node: ast.expr, path: FieldPath):
        self._asserted_paths.setdefault(self._key(node), set()).add(path)

    def _paths_for(self, key: str) -> set[FieldPath]:
        paths = set(self._asserted_paths.get(key, set()))
        match ast.parse(key, mode="eval").body:
            case ast.Subscript(value=list_node, slice=ast.Constant()):
                each_key = ast.unparse(
                    ast.Subscript(value=list_node, slice=_EACH_ELEMENT)
                )
                paths |= self._asserted_paths.get(each_key, set())
                if () in self._asserted_paths.get(ast.unparse(list_node), set()):
                    paths.add(())
            case _:
                pass
        return paths

    def _has_indexed_check(self, each_key: str) -> bool:
        list_key = each_key.removesuffix(_EACH_ELEMENT_SUFFIX)
        for key in self._checked_classes:
            if key != each_key and key.startswith(f"{list_key}["):
                return True
        return False

    def field_problems(self) -> list[str]:
        problems: list[str] = []
        for key, line in self._diagnostic_uses.items():
            if key in self._checked_classes:
                continue
            if key.endswith(_EACH_ELEMENT_SUFFIX) and self._has_indexed_check(key):
                continue
            problems.append(
                f"line {line}: assert isinstance({key}, diagnostics.<class>) before asserting on its fields"
            )
        for key, (class_name, line) in self._checked_classes.items():
            # Assertions on each indexed element already include the loop's
            # assertions, so the loop element needs no check of its own.
            if key.endswith(_EACH_ELEMENT_SUFFIX) and self._has_indexed_check(key):
                continue
            missing = _missing_fields(class_name, self._paths_for(key))
            if missing:
                problems.append(
                    f"line {line}: {key} is a {class_name}, but the test does not assert on {', '.join(missing)}"
                )
        return problems

    def message_problems(self) -> list[str]:
        problems: list[str] = []
        for key, line in self._message_uses.items():
            if key in self._checked_classes or key in self._diagnostic_uses:
                problems.append(
                    f"line {line}: assert on the fields of {key} instead of its message"
                )
        return problems


def _missing_fields(class_name: str, paths: set[FieldPath]) -> list[str]:
    if () in paths:
        return []
    missing: list[str] = []
    for field_name, annotation in diagnostic_fields()[class_name].items():
        if (field_name,) in paths:
            continue
        if _LOCATION_TYPE not in annotation:
            missing.append(field_name)
            continue
        for location_field in _LOCATION_FIELDS:
            if (field_name, location_field) not in paths:
                missing.append(f"{field_name}.{location_field}")
    return missing


def unasserted_diagnostic_fields(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[str]:
    """Describe each diagnostic checked by `function` that it does not fully assert on."""
    assertions = _TestFunctionAssertions()
    assertions.visit_statements(function.body)
    return assertions.field_problems()


def diagnostic_message_assertions(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[str]:
    """Describe each assertion in `function` on a diagnostic's message."""
    assertions = _TestFunctionAssertions()
    assertions.visit_statements(function.body)
    return assertions.message_problems()
