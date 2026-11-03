"""Describes the classes in `define.compiler.ast` for the parser's Rust generators.

The description is made in three steps:

1. Collect every `msgspec.Struct` class defined in `define.compiler.ast`, and
   every parameterization of a generic one, such as
   `OperationExecutionStatement[PositionReference | Literal]`, that a parsed
   program can contain. Each is a node type, and a parameterization's name is
   its generic class's name, "Of", and its type argument's name, such as
   `OperationExecutionStatementOfPositionReferenceOrLiteral`.
2. Name a union of AST classes after a type alias for it, wherever one
   exists, so that the same union written out in a field annotation gets the
   alias's name.
3. Describe each class: the AST classes it inherits from, and for each class
   that can be constructed, its constructor's parameters.

Each field of a class, derived ones included, is a constructor parameter,
except a field computed on first use, which the constructor sets to `None`. A
`ParsedOrComputedOnFirstUse` field is a parameter that may not be `None`, since
the parser always passes it.
Each parameter's annotation becomes a `FieldType`:

- An AST class, or a parameterization of a generic one, becomes `Node`.
- A union of AST classes, or a type alias for one, becomes `Node` with the
  union's name.
- `tuple[X, ...]`, where `X` is a node type or a union of them, becomes
  `Tuple`, and `tuple[str, ...]` or a `typing.NewType` of it becomes
  `StringTuple`.
- `frozenset[str]` becomes `StringSet`, and `dict[str, X]`, where `X` is an
  AST class, becomes `Dict`.
- `str`, `int`, `bool`, and `pathlib.PurePosixPath` become `String`, `Integer`,
  `Boolean`, and `FilePath`.
- An `enum.Enum` becomes `Enum`.

An annotation of the form `X | None` makes the parameter optional.
"""

from __future__ import annotations

import enum
import inspect
import pathlib
import types
import typing

import msgspec

from define.compiler import ast
from define.compiler.parsing.rust_generators import rust_names, rust_renderer

if typing.TYPE_CHECKING:
    from collections.abc import Callable

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


def _is_parameterization(annotation: object) -> bool:
    """Return whether `annotation` is a generic AST class with type arguments."""
    origin = typing.get_origin(annotation)
    return (
        isinstance(origin, type)
        and issubclass(origin, msgspec.Struct)
        and bool(_type_arguments(annotation))
    )


def _node_class(node_type: object) -> type:
    """Return the class that instances of `node_type` are."""
    if _is_parameterization(node_type):
        return typing.cast("type", typing.get_origin(node_type))
    return typing.cast("type", node_type)


def _node_name(node_type: object) -> str:
    """Return the Rust name of `node_type`."""
    if not _is_parameterization(node_type):
        return _node_class(node_type).__name__
    argument_names: list[str] = []
    for argument in _type_arguments(node_type):
        members = (
            _type_arguments(argument)
            if typing.get_origin(argument) is types.UnionType
            else (argument,)
        )
        argument_names.append("Or".join(_node_name(member) for member in members))
    return _node_class(node_type).__name__ + "Of" + "And".join(argument_names)


def _is_node_subtype(node_type: object, member: object) -> bool:
    """Return whether every instance of `node_type` is an instance of `member`."""
    if node_type == member:
        return True
    return (
        isinstance(member, type)
        and not _is_parameterization(member)
        and issubclass(_node_class(node_type), member)
    )


def _node_type_variable_values(
    node_type: object, namespace: dict[str, object]
) -> dict[typing.TypeVar, object]:
    """Map each type variable of `node_type`'s class and the generic classes it inherits from to its value for `node_type`."""
    cls = _node_class(node_type)
    values = _type_variable_values(cls, namespace)
    if _is_parameterization(node_type):
        parameters = typing.cast(
            "tuple[typing.TypeVar, ...]", getattr(cls, "__parameters__", ())
        )
        values.update(zip(parameters, _type_arguments(node_type), strict=True))
    return values


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


def _is_computed_on_first_use(parameter: inspect.Parameter) -> bool:
    return (
        typing.get_origin(typing.cast("object", parameter.annotation))
        is ast.ComputedOnFirstUse
    )


def _field_annotation(
    parameter: inspect.Parameter, type_variable_values: dict[typing.TypeVar, object]
) -> object:
    """Return the annotation of `parameter` without `Final`, `Derived`, or `ParsedOrComputedOnFirstUse`, with the value of each type variable in it.

    A `ParsedOrComputedOnFirstUse` field is `None` only until Python code
    computes it, so its annotation is the one type other than `None` in its
    union.
    """
    annotation = typing.cast("object", parameter.annotation)
    origin = typing.get_origin(annotation)
    if origin in {typing.Final, ast.Derived, ast.ParsedOrComputedOnFirstUse}:
        annotation = _type_arguments(annotation)[0]
    if origin is ast.ParsedOrComputedOnFirstUse:
        (annotation,) = [
            member
            for member in _type_arguments(annotation)
            if member is not types.NoneType
        ]
    return _type_variable_value(annotation, type_variable_values)


def _type_variable_value(
    annotation: object, type_variable_values: dict[typing.TypeVar, object]
) -> object:
    """Return `annotation` with the value of each type variable in place of it, itself or as a type argument of a tuple or a generic AST class."""
    if isinstance(annotation, typing.TypeVar):
        return type_variable_values[annotation]
    arguments = tuple(
        _type_variable_value(argument, type_variable_values)
        for argument in _type_arguments(annotation)
    )
    if typing.get_origin(annotation) is tuple:
        return types.GenericAlias(tuple, arguments)
    if _is_parameterization(annotation):
        parameterize = typing.cast(
            "Callable[[tuple[object, ...]], object]",
            typing.cast("typing.Any", _node_class(annotation)).__class_getitem__,
        )
        return parameterize(arguments)
    return annotation


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


def describe(module: types.ModuleType) -> rust_renderer.AstDescription:
    """Describe the AST classes in `module` that a parsed `Program` can contain."""
    classes = _parsed_node_types(module)
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


def _parsed_node_types(module: types.ModuleType) -> list[object]:
    """Return the node types in `module` that a parsed `Program` can contain.

    These are `Program`, and every node type that a constructor parameter of
    one of them names, with the subclasses of each class among them. Classes
    come in the order `module` defines them, followed by parameterizations in
    the order they were found.
    """
    classes = _ast_classes(module)
    reachable: list[object] = []
    pending: list[object] = [ast.Program]
    while pending:
        node_type = pending.pop()
        if node_type in reachable:
            continue
        reachable.append(node_type)
        if not _is_parameterization(node_type):
            pending.extend(
                subclass
                for subclass in classes
                if issubclass(subclass, typing.cast("type", node_type))
            )
        pending.extend(_constructor_node_types(node_type, classes, module))
    parameterizations = [
        node_type for node_type in reachable if _is_parameterization(node_type)
    ]
    return [cls for cls in classes if cls in reachable] + parameterizations


def _constructor_node_types(
    node_type: object, classes: list[type], module: types.ModuleType
) -> list[object]:
    """Return the node types that the annotations of `node_type`'s constructor parameters name."""
    cls = _node_class(node_type)
    if inspect.isabstract(cls) or not _is_constructed(node_type):
        return []
    type_variable_values = _node_type_variable_values(node_type, vars(module))
    named: list[object] = []
    for parameter in inspect.signature(cls).parameters.values():
        if _is_computed_on_first_use(parameter):
            continue
        annotation = _field_annotation(parameter, type_variable_values)
        named.extend(_annotation_classes(annotation, classes))
    return named


def _is_constructed(node_type: object) -> bool:
    """Return whether `node_type` is a class without type variables or a parameterization of one with them."""
    return _is_parameterization(node_type) or not getattr(
        node_type, "__parameters__", ()
    )


def _annotation_classes(annotation: object, classes: list[type]) -> list[object]:
    """Return the node types whose classes are in `classes` that `annotation` names."""
    if isinstance(annotation, type) and annotation in classes:
        return [annotation]
    if _is_parameterization(annotation) and _node_class(annotation) in classes:
        return [annotation]
    if isinstance(annotation, typing.TypeAliasType):
        return _annotation_classes(typing.cast("object", annotation.__value__), classes)
    named: list[object] = []
    for argument in _type_arguments(annotation):
        named.extend(_annotation_classes(argument, classes))
    return named


def _describe_class(
    node_type: object,
    classes: list[object],
    field_types: _FieldTypes,
    module: types.ModuleType,
) -> rust_renderer.NodeClass:
    cls = _node_class(node_type)
    ancestors = [base.__name__ for base in cls.__mro__[1:] if base in classes]
    constructor = None
    # A class that has subclasses is only ever a base of the classes the
    # parser builds.
    has_subclasses = any(
        other != node_type and _is_node_subtype(other, node_type) for other in classes
    )
    if (
        not inspect.isabstract(cls)
        and _is_constructed(node_type)
        and not has_subclasses
    ):
        constructor = _describe_constructor(node_type, field_types, module)
    name = _node_name(node_type)
    return rust_renderer.NodeClass(
        name=name,
        python_name=cls.__name__,
        snake_case_name=rust_names.snake_case_name(name),
        ancestors=ancestors,
        constructor=constructor,
        # Syntax errors build a SourceLocation without an AstBuilder.
        has_standalone_constructor=cls is ast.SourceLocation,
    )


def _describe_constructor(
    node_type: object, field_types: _FieldTypes, module: types.ModuleType
) -> rust_renderer.Constructor:
    cls = _node_class(node_type)
    # The constructor writes each field into its instance without calling the
    # class, which leaves an instance of a class that the garbage collector
    # tracks untracked.
    if typing.cast("msgspec.structs.StructConfig", cls.__struct_config__).gc:
        raise ValueError(f"{cls.__name__} must have gc=False")
    signature_parameters = list(inspect.signature(cls).parameters.values())
    struct_fields = typing.cast("tuple[str, ...]", cls.__struct_fields__)
    # An unset field would raise an error on every later read of it.
    if {parameter.name for parameter in signature_parameters} != set(struct_fields):
        raise ValueError(f"{cls.__name__}'s constructor does not take every field")
    type_variable_values = _node_type_variable_values(node_type, vars(module))
    parameters: list[rust_renderer.Parameter] = []
    computed_on_first_use: list[str] = []
    for parameter in signature_parameters:
        if _is_computed_on_first_use(parameter):
            if typing.cast("object", parameter.default) is not None:
                raise ValueError(
                    f"{cls.__name__}.{parameter.name} is computed on first use but"
                    + " does not default to None"
                )
            computed_on_first_use.append(parameter.name)
            continue
        annotation = _field_annotation(parameter, type_variable_values)
        parameters.append(
            field_types.parameter(parameter.name, annotation, type_variable_values)
        )
    return rust_renderer.Constructor(
        parameters=parameters, computed_on_first_use=computed_on_first_use
    )


class _FieldTypes:
    """Turns annotations into field types, naming each union and enum they use."""

    def __init__(self, classes: list[object]):
        self._classes: list[object] = classes
        self._alias_names: dict[frozenset[object], str] = {}
        self._unions: dict[frozenset[object], rust_renderer.NodeUnion] = {}
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

    def parameter(
        self,
        name: str,
        annotation: object,
        type_variable_values: dict[typing.TypeVar, object],
    ) -> rust_renderer.Parameter:
        """Return the parameter `name` with `annotation`, whose type variables have the values in `type_variable_values`."""
        arguments = _type_arguments(annotation)
        if (
            typing.get_origin(annotation) is not types.UnionType
            or types.NoneType not in arguments
        ):
            return rust_renderer.Parameter(
                name=name, field_type=self._field_type(annotation), is_optional=False
            )
        value_types: list[object] = []
        for argument in arguments:
            if argument is not types.NoneType:
                value_types.append(_type_variable_value(argument, type_variable_values))
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
        if annotation in self._classes:
            return rust_renderer.FieldType.Node(name=_node_name(annotation))
        if annotation in _SIMPLE_FIELD_TYPES:
            return _SIMPLE_FIELD_TYPES[annotation]
        if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
            return rust_renderer.FieldType.Enum(name=self._enum(annotation).name)
        if isinstance(annotation, typing.TypeAliasType):
            return self._union_type(
                self._union_members(typing.cast("object", annotation.__value__)),
                annotation.__name__,
            )
        if isinstance(annotation, typing.NewType):
            return self._field_type(typing.cast("object", annotation.__supertype__))
        if origin is tuple and arguments == (str, Ellipsis):
            return rust_renderer.FieldType.StringTuple()
        if origin is frozenset and arguments == (str,):
            return rust_renderer.FieldType.StringSet()
        if (
            origin is dict
            and len(arguments) == 2
            and arguments[0] is str
            and isinstance(arguments[1], type)
            and arguments[1] in self._classes
        ):
            return rust_renderer.FieldType.Dict()
        if origin is tuple and len(arguments) == 2 and arguments[1] is Ellipsis:
            element_type = self._field_type(arguments[0])
            if not isinstance(element_type, rust_renderer.FieldType.Node):
                raise ValueError(f"unsupported tuple element type: {arguments[0]!r}")
            return rust_renderer.FieldType.Tuple(element_name=element_type.name)
        if origin is types.UnionType:
            return self._union_type(self._union_members(*arguments), None)
        raise ValueError(f"unsupported field type: {annotation!r}")

    def _union_members(self, *types_in_union: object) -> list[object]:
        """Return the node types in a union of `types_in_union`, expanding unions and type aliases."""
        members: list[object] = []
        for member in types_in_union:
            if isinstance(member, typing.TypeAliasType):
                members.extend(
                    self._union_members(typing.cast("object", member.__value__))
                )
            elif typing.get_origin(member) is types.UnionType:
                members.extend(self._union_members(*_type_arguments(member)))
            elif member in self._classes:
                members.append(member)
            else:
                raise ValueError(f"unsupported union member: {member!r}")
        return members

    def _union_type(
        self, members: list[object], alias_name: str | None
    ) -> rust_renderer.FieldType.Node:
        """Return the union of `members`, registering it the first time it is seen.

        The union is named after `alias_name`, or the type alias registered
        for the same classes, and otherwise by joining its members' names
        with "Or".
        """
        key = frozenset(members)
        if key not in self._unions:
            alias_name = alias_name or self._alias_names.get(key)
            name = alias_name or "Or".join(_node_name(member) for member in members)
            member_classes: list[str] = []
            for node_type in self._classes:
                if any(_is_node_subtype(node_type, member) for member in members):
                    member_classes.append(_node_name(node_type))
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
                value = typing.cast("object", member.value)
                if not isinstance(value, str):
                    raise TypeError(f"{member!r} does not have a string value")
                members.append(
                    rust_renderer.EnumMember(
                        python_name=member.name,
                        rust_name=_rust_enum_variant_name(member.name),
                        value=value,
                    )
                )
            self._enums[enum_class] = rust_renderer.FieldEnum(
                name=enum_class.__name__,
                snake_case_name=rust_names.snake_case_name(enum_class.__name__),
                module_name=enum_class.__module__,
                members=members,
            )
        return self._enums[enum_class]
