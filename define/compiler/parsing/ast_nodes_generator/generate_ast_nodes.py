"""Writes the parser's Rust types for the classes in `define.compiler.ast`.

The generator works in four steps:

1. Collect every `msgspec.Struct` class defined in `define.compiler.ast`.
2. Name a union of AST classes after a type alias for it, wherever one
   exists, so that the same union written out in a field annotation gets the
   alias's name.
3. Describe each class: the AST classes it inherits from, and for each class
   that can be constructed, its constructor's parameters.
4. Render the description as Rust with `ast_nodes_renderer`.

Each constructor parameter's annotation becomes a `FieldType`:

- An AST class becomes `Node`.
- A union of AST classes, or a type alias for one, becomes `Node` with the
  union's name.
- `tuple[X, ...]`, where `X` is an AST class or a union of them, becomes
  `Tuple`.
- `str`, `int`, `bool`, and `pathlib.PurePosixPath` become `String`, `Integer`,
  `Boolean`, and `FilePath`.
- An `enum.Enum` becomes `Enum`.

An annotation of the form `X | None` makes the parameter optional.
"""

from __future__ import annotations

import enum
import inspect
import pathlib
import re
import sys
import types
import typing

import msgspec

from define.compiler import ast
from define.compiler.parsing.ast_nodes_generator import ast_nodes_renderer

_WORD_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")

_SIMPLE_FIELD_TYPES: dict[object, ast_nodes_renderer.FieldType] = {
    str: ast_nodes_renderer.FieldType.String(),
    int: ast_nodes_renderer.FieldType.Integer(),
    bool: ast_nodes_renderer.FieldType.Boolean(),
    pathlib.PurePosixPath: ast_nodes_renderer.FieldType.FilePath(),
}


def _snake_case_name(class_name: str) -> str:
    return _WORD_BOUNDARY.sub("_", class_name).lower()


def _rust_enum_variant_name(member_name: str) -> str:
    return "".join(word.capitalize() for word in member_name.split("_"))


def _type_arguments(annotation: object) -> tuple[object, ...]:
    return typing.cast("tuple[object, ...]", typing.get_args(annotation))


def _type_variable_values(
    cls: type, namespace: dict[str, object]
) -> dict[typing.TypeVar, object]:
    """Map each type variable of the generic classes that `cls` inherits from to its value for `cls`.

    For example, `GlobalTypedNameInDefinition` inherits from
    `GlobalTypedName[DefinitionGlobalNameContent]`, and `GlobalTypedName`
    inherits from `TypedName[GlobalNameContentT_co]`. So for
    `GlobalTypedNameInDefinition`, both `GlobalNameContentT_co` and the type
    variable of `TypedName.name_content` map to `DefinitionGlobalNameContent`.
    A value written as a string, such as `"ReferenceGlobalNameContent"`, is
    looked up in `namespace`.
    """
    values: dict[typing.TypeVar, object] = {}
    original_bases = typing.cast("tuple[object, ...]", types.get_original_bases(cls))
    for base in original_bases:
        origin = typing.get_origin(base)
        if origin is None or origin is typing.Generic:
            continue
        generic_class = typing.cast("type", origin)
        base_values: dict[typing.TypeVar, object] = {}
        parameters = typing.cast(
            "tuple[typing.TypeVar, ...]", getattr(generic_class, "__parameters__", ())
        )
        for parameter, argument in zip(parameters, _type_arguments(base), strict=True):
            if isinstance(argument, typing.ForwardRef):
                base_values[parameter] = typing.evaluate_forward_ref(
                    argument, globals=namespace
                )
            else:
                base_values[parameter] = argument
        # The generic class's own generic bases may take its type variables as
        # their values, which this class's arguments then decide.
        for variable, value in _type_variable_values(generic_class, namespace).items():
            if isinstance(value, typing.TypeVar):
                values[variable] = base_values.get(value, value)
            else:
                values[variable] = value
        values.update(base_values)
    return values


def _positional_count(parameters: list[inspect.Parameter]) -> int:
    """Return how many of the constructor's `parameters` are passed by position.

    Parameters are passed by position up to the first keyword-only or derived
    one, since passing a later parameter by position would also pass every
    parameter before it, including a derived one.
    """
    count = 0
    for parameter in parameters:
        if parameter.kind is not inspect.Parameter.POSITIONAL_OR_KEYWORD or _is_derived(
            parameter
        ):
            break
        count += 1
    return count


def _is_derived(parameter: inspect.Parameter) -> bool:
    return typing.get_origin(typing.cast("object", parameter.annotation)) is ast.Derived


def _ast_classes(module: types.ModuleType) -> list[type]:
    """Return the `msgspec.Struct` classes defined in `module`."""
    namespace: dict[str, object] = vars(module)
    classes: list[type] = []
    for value in namespace.values():
        if (
            isinstance(value, type)
            and issubclass(value, msgspec.Struct)
            and value.__module__ == module.__name__
        ):
            classes.append(value)
    return classes


def _describe(module: types.ModuleType) -> ast_nodes_renderer.AstDescription:
    classes = _ast_classes(module)
    field_types = _FieldTypes(classes)
    # Type aliases come first, so that a union written out in a field
    # annotation takes the name of an alias for the same classes.
    field_types.register_type_aliases(module)
    node_classes = [
        _describe_class(cls, classes, field_types, module) for cls in classes
    ]
    return ast_nodes_renderer.AstDescription(
        module_name=module.__name__,
        classes=node_classes,
        unions=field_types.unions(),
        enums=field_types.enums(),
    )


def _describe_class(
    cls: type,
    classes: list[type],
    field_types: _FieldTypes,
    module: types.ModuleType,
) -> ast_nodes_renderer.NodeClass:
    ancestors = [base.__name__ for base in cls.__mro__[1:] if base in classes]
    constructor = None
    if not inspect.isabstract(cls) and not getattr(cls, "__parameters__", ()):
        constructor = _describe_constructor(cls, field_types, module)
    return ast_nodes_renderer.NodeClass(
        name=cls.__name__,
        snake_case_name=_snake_case_name(cls.__name__),
        ancestors=ancestors,
        constructor=constructor,
    )


def _describe_constructor(
    cls: type, field_types: _FieldTypes, module: types.ModuleType
) -> ast_nodes_renderer.Constructor:
    signature_parameters = list(inspect.signature(cls).parameters.values())
    type_variable_values = _type_variable_values(cls, vars(module))
    parameters: list[ast_nodes_renderer.Parameter] = []
    for parameter in signature_parameters:
        if _is_derived(parameter):
            if typing.cast("object", parameter.default) is inspect.Parameter.empty:
                raise ValueError(
                    f"{cls.__name__}.{parameter.name} is derived but has no default"
                )
            continue
        annotation = typing.cast("object", parameter.annotation)
        if typing.get_origin(annotation) is typing.Final:
            annotation = _type_arguments(annotation)[0]
        if isinstance(annotation, typing.TypeVar):
            annotation = type_variable_values[annotation]
        parameters.append(field_types.parameter(parameter.name, annotation))
    return ast_nodes_renderer.Constructor(
        parameters=parameters,
        positional_count=_positional_count(signature_parameters),
    )


class _FieldTypes:
    """Turns annotations into field types, naming each union and enum they use."""

    def __init__(self, classes: list[type]):
        self._classes: list[type] = classes
        self._unions: dict[frozenset[type], ast_nodes_renderer.NodeUnion] = {}
        self._enums: dict[type, ast_nodes_renderer.FieldEnum] = {}

    def register_type_aliases(self, module: types.ModuleType):
        """Name the union of AST classes that each type alias in `module` stands for after the alias."""
        namespace: dict[str, object] = vars(module)
        for value in namespace.values():
            if isinstance(value, typing.TypeAliasType) and not value.__type_params__:
                _ = self._union_type(
                    self._union_members(typing.cast("object", value.__value__)),
                    value.__name__,
                )

    def unions(self) -> list[ast_nodes_renderer.NodeUnion]:
        return list(self._unions.values())

    def enums(self) -> list[ast_nodes_renderer.FieldEnum]:
        return list(self._enums.values())

    def parameter(self, name: str, annotation: object) -> ast_nodes_renderer.Parameter:
        arguments = _type_arguments(annotation)
        if (
            typing.get_origin(annotation) is not types.UnionType
            or types.NoneType not in arguments
        ):
            return ast_nodes_renderer.Parameter(
                name=name, field_type=self._field_type(annotation), is_optional=False
            )
        value_types = [
            argument for argument in arguments if argument is not types.NoneType
        ]
        if len(value_types) == 1:
            field_type = self._field_type(value_types[0])
        else:
            field_type = self._union_type(self._union_members(*value_types), None)
        return ast_nodes_renderer.Parameter(
            name=name, field_type=field_type, is_optional=True
        )

    def _field_type(self, annotation: object) -> ast_nodes_renderer.FieldType:
        origin = typing.get_origin(annotation)
        arguments = _type_arguments(annotation)
        if isinstance(annotation, type) and annotation in self._classes:
            return ast_nodes_renderer.FieldType.Node(name=annotation.__name__)
        if annotation in _SIMPLE_FIELD_TYPES:
            return _SIMPLE_FIELD_TYPES[annotation]
        if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
            return ast_nodes_renderer.FieldType.Enum(name=self._enum(annotation).name)
        if isinstance(annotation, typing.TypeAliasType):
            return self._union_type(
                self._union_members(typing.cast("object", annotation.__value__)),
                annotation.__name__,
            )
        if origin is tuple and len(arguments) == 2 and arguments[1] is Ellipsis:
            element_type = self._field_type(arguments[0])
            if not isinstance(element_type, ast_nodes_renderer.FieldType.Node):
                raise ValueError(f"unsupported tuple element type: {arguments[0]!r}")
            return ast_nodes_renderer.FieldType.Tuple(element_name=element_type.name)
        if origin is types.UnionType:
            return self._union_type(self._union_members(*arguments), None)
        raise ValueError(f"unsupported field type: {annotation!r}")

    def _union_members(self, *types_in_union: object) -> list[type]:
        """Return the AST classes in a union of `types_in_union`, expanding unions and type aliases."""
        members: list[type] = []
        for member in types_in_union:
            if isinstance(member, typing.TypeAliasType):
                members.extend(
                    self._union_members(typing.cast("object", member.__value__))
                )
            elif typing.get_origin(member) is types.UnionType:
                members.extend(self._union_members(*_type_arguments(member)))
            elif isinstance(member, type) and member in self._classes:
                members.append(member)
            else:
                raise ValueError(f"unsupported union member: {member!r}")
        return members

    def _union_type(
        self, members: list[type], alias_name: str | None
    ) -> ast_nodes_renderer.FieldType.Node:
        """Return the union of `members`, registering it under `alias_name` the first time it is seen.

        A union without a type alias is named by joining its members' names
        with "Or".
        """
        key = frozenset(members)
        if key not in self._unions:
            name = alias_name or "Or".join(member.__name__ for member in members)
            member_classes: list[str] = []
            for cls in self._classes:
                if any(issubclass(cls, member) for member in members):
                    member_classes.append(cls.__name__)
            self._unions[key] = ast_nodes_renderer.NodeUnion(
                name=name,
                is_type_alias=alias_name is not None,
                member_classes=member_classes,
            )
        return ast_nodes_renderer.FieldType.Node(name=self._unions[key].name)

    def _enum(self, enum_class: type[enum.Enum]) -> ast_nodes_renderer.FieldEnum:
        if enum_class not in self._enums:
            members: list[ast_nodes_renderer.EnumMember] = []
            for member in enum_class:
                members.append(
                    ast_nodes_renderer.EnumMember(
                        python_name=member.name,
                        rust_name=_rust_enum_variant_name(member.name),
                    )
                )
            self._enums[enum_class] = ast_nodes_renderer.FieldEnum(
                name=enum_class.__name__,
                snake_case_name=_snake_case_name(enum_class.__name__),
                module_name=enum_class.__module__,
                members=members,
            )
        return self._enums[enum_class]


def main():
    """Write the Rust types to the path given as the only argument."""
    (output_path,) = sys.argv[1:]
    description = _describe(ast)
    _ = pathlib.Path(output_path).write_text(
        ast_nodes_renderer.render(description), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
