"""Writes the parser's Rust types for the classes in `define.compiler.ast`.

The generator works in four steps:

1. Collect every `msgspec.Struct` class defined in `define.compiler.ast`.
2. Name a union of AST classes after a type alias for it, wherever one
   exists, so that the same union written out in a field annotation gets the
   alias's name.
3. Describe each class: the AST classes it inherits from, and for each class
   that can be constructed, its constructor's parameters.
4. Render the description as Rust with `rust_renderer`.

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
import sys
import types
import typing

import msgspec

from define.compiler import ast
from define.compiler.parsing.rust_generators import rust_names, rust_renderer

_SIMPLE_FIELD_TYPES: dict[object, rust_renderer.FieldType] = {
    str: rust_renderer.FieldType.String(),
    int: rust_renderer.FieldType.Integer(),
    bool: rust_renderer.FieldType.Boolean(),
    pathlib.PurePosixPath: rust_renderer.FieldType.FilePath(),
}


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


def _describe(module: types.ModuleType) -> rust_renderer.AstDescription:
    classes = _parsed_classes(module)
    field_types = _FieldTypes(classes)
    # Type aliases come first, so that a union written out in a field
    # annotation takes the name of an alias for the same classes.
    field_types.register_type_aliases(module)
    node_classes = [
        _describe_class(cls, classes, field_types, module) for cls in classes
    ]
    return rust_renderer.AstDescription(
        module_name=module.__name__,
        classes=node_classes,
        unions=field_types.unions(),
        enums=field_types.enums(),
    )


def _parsed_classes(module: types.ModuleType) -> list[type]:
    """Return the AST classes in `module` that a parsed `Program` can contain.

    These are `Program`, and every class that a constructor parameter of one
    of them names, with its subclasses.
    """
    classes = _ast_classes(module)
    reachable: set[type] = set()
    pending: list[type] = [ast.Program]
    while pending:
        cls = pending.pop()
        if cls in reachable:
            continue
        reachable.add(cls)
        pending.extend(subclass for subclass in classes if issubclass(subclass, cls))
        pending.extend(_constructor_classes(cls, classes, module))
    return [cls for cls in classes if cls in reachable]


def _constructor_classes(
    cls: type, classes: list[type], module: types.ModuleType
) -> list[type]:
    """Return the AST classes that the annotations of `cls`'s constructor parameters name."""
    if inspect.isabstract(cls) or getattr(cls, "__parameters__", ()):
        return []
    type_variable_values = _type_variable_values(cls, vars(module))
    named: list[type] = []
    for parameter in inspect.signature(cls).parameters.values():
        if _is_derived(parameter):
            continue
        annotation = typing.cast("object", parameter.annotation)
        if typing.get_origin(annotation) is typing.Final:
            annotation = _type_arguments(annotation)[0]
        if isinstance(annotation, typing.TypeVar):
            annotation = type_variable_values[annotation]
        named.extend(_annotation_classes(annotation, classes))
    return named


def _annotation_classes(annotation: object, classes: list[type]) -> list[type]:
    """Return the AST classes in `classes` that `annotation` names."""
    if isinstance(annotation, type) and annotation in classes:
        return [annotation]
    if isinstance(annotation, typing.TypeAliasType):
        return _annotation_classes(typing.cast("object", annotation.__value__), classes)
    named: list[type] = []
    for argument in _type_arguments(annotation):
        named.extend(_annotation_classes(argument, classes))
    return named


def _describe_class(
    cls: type,
    classes: list[type],
    field_types: _FieldTypes,
    module: types.ModuleType,
) -> rust_renderer.NodeClass:
    ancestors = [base.__name__ for base in cls.__mro__[1:] if base in classes]
    constructor = None
    # A class that has subclasses is only ever a base of the classes the
    # parser builds.
    has_subclasses = any(
        other is not cls and issubclass(other, cls) for other in classes
    )
    if (
        not inspect.isabstract(cls)
        and not getattr(cls, "__parameters__", ())
        and not has_subclasses
    ):
        constructor = _describe_constructor(cls, field_types, module)
    return rust_renderer.NodeClass(
        name=cls.__name__,
        snake_case_name=rust_names.snake_case_name(cls.__name__),
        ancestors=ancestors,
        constructor=constructor,
        # Syntax errors build a SourceLocation without an AstBuilder.
        has_standalone_constructor=cls is ast.SourceLocation,
    )


def _describe_constructor(
    cls: type, field_types: _FieldTypes, module: types.ModuleType
) -> rust_renderer.Constructor:
    signature_parameters = list(inspect.signature(cls).parameters.values())
    type_variable_values = _type_variable_values(cls, vars(module))
    parameters: list[rust_renderer.Parameter] = []
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
    return rust_renderer.Constructor(
        parameters=parameters,
        positional_count=_positional_count(signature_parameters),
    )


class _FieldTypes:
    """Turns annotations into field types, naming each union and enum they use."""

    def __init__(self, classes: list[type]):
        self._classes: list[type] = classes
        self._alias_names: dict[frozenset[type], str] = {}
        self._unions: dict[frozenset[type], rust_renderer.NodeUnion] = {}
        self._enums: dict[type, rust_renderer.FieldEnum] = {}

    def register_type_aliases(self, module: types.ModuleType):
        """Name each union of AST classes that a type alias in `module` stands for after the alias."""
        namespace: dict[str, object] = vars(module)
        for value in namespace.values():
            if not isinstance(value, typing.TypeAliasType) or value.__type_params__:
                continue
            members = _annotation_classes(
                typing.cast("object", value.__value__), _ast_classes(module)
            )
            # An alias that names a class a parsed program cannot contain names
            # no union that a parameter can have.
            if all(member in self._classes for member in members):
                self._alias_names[frozenset(members)] = value.__name__

    def unions(self) -> list[rust_renderer.NodeUnion]:
        return list(self._unions.values())

    def enums(self) -> list[rust_renderer.FieldEnum]:
        return list(self._enums.values())

    def parameter(self, name: str, annotation: object) -> rust_renderer.Parameter:
        arguments = _type_arguments(annotation)
        if (
            typing.get_origin(annotation) is not types.UnionType
            or types.NoneType not in arguments
        ):
            return rust_renderer.Parameter(
                name=name, field_type=self._field_type(annotation), is_optional=False
            )
        value_types = [
            argument for argument in arguments if argument is not types.NoneType
        ]
        if len(value_types) == 1:
            field_type = self._field_type(value_types[0])
        else:
            field_type = self._union_type(self._union_members(*value_types), None)
        return rust_renderer.Parameter(
            name=name, field_type=field_type, is_optional=True
        )

    def _field_type(self, annotation: object) -> rust_renderer.FieldType:
        origin = typing.get_origin(annotation)
        arguments = _type_arguments(annotation)
        if isinstance(annotation, type) and annotation in self._classes:
            return rust_renderer.FieldType.Node(name=annotation.__name__)
        if annotation in _SIMPLE_FIELD_TYPES:
            return _SIMPLE_FIELD_TYPES[annotation]
        if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
            return rust_renderer.FieldType.Enum(name=self._enum(annotation).name)
        if isinstance(annotation, typing.TypeAliasType):
            return self._union_type(
                self._union_members(typing.cast("object", annotation.__value__)),
                annotation.__name__,
            )
        if origin is tuple and len(arguments) == 2 and arguments[1] is Ellipsis:
            element_type = self._field_type(arguments[0])
            if not isinstance(element_type, rust_renderer.FieldType.Node):
                raise ValueError(f"unsupported tuple element type: {arguments[0]!r}")
            return rust_renderer.FieldType.Tuple(element_name=element_type.name)
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
    ) -> rust_renderer.FieldType.Node:
        """Return the union of `members`, registering it the first time it is seen.

        The union is named after `alias_name`, or the type alias registered
        for the same classes, and otherwise by joining its members' names
        with "Or".
        """
        key = frozenset(members)
        if key not in self._unions:
            alias_name = alias_name or self._alias_names.get(key)
            name = alias_name or "Or".join(member.__name__ for member in members)
            member_classes: list[str] = []
            for cls in self._classes:
                if any(issubclass(cls, member) for member in members):
                    member_classes.append(cls.__name__)
            self._unions[key] = rust_renderer.NodeUnion(
                name=name,
                is_type_alias=alias_name is not None,
                member_classes=member_classes,
            )
        return rust_renderer.FieldType.Node(name=self._unions[key].name)

    def _enum(self, enum_class: type[enum.Enum]) -> rust_renderer.FieldEnum:
        if enum_class not in self._enums:
            members: list[rust_renderer.EnumMember] = []
            for member in enum_class:
                members.append(
                    rust_renderer.EnumMember(
                        python_name=member.name,
                        rust_name=_rust_enum_variant_name(member.name),
                    )
                )
            self._enums[enum_class] = rust_renderer.FieldEnum(
                name=enum_class.__name__,
                snake_case_name=rust_names.snake_case_name(enum_class.__name__),
                module_name=enum_class.__module__,
                members=members,
            )
        return self._enums[enum_class]


def main():
    """Write the Rust types to the path given as the only argument."""
    (output_path,) = sys.argv[1:]
    description = _describe(ast)
    _ = pathlib.Path(output_path).write_text(
        rust_renderer.render_ast_nodes(description), encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    main()
