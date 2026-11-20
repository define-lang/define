"""The program's resolved associations: each value quality's encoding, and each Abstract Operation's Encoding Operations."""

from __future__ import annotations

import typing

import msgspec

from define.compiler.config import project_config, project_roots
from define.compiler.errors import association_resolution_diagnostics
from define.compiler.graphs import reference_graph

if typing.TYPE_CHECKING:
    from collections.abc import Collection, Mapping

    from define.compiler import ast
    from define.compiler.config import config_loader, encoding_operations_config
    from define.compiler.data_structures import define_path
    from define.compiler.errors import config_diagnostics, diagnostics


class ChosenEncodingOperation(msgspec.Struct, frozen=True):
    """An Encoding Operation that association resolution chose for an execution of an Abstract Operation."""

    abstract_operation: ast.AbstractOperationDefinition
    # The association of the Abstract Operation that names the Encoding
    # Operation.
    encoding_operation_association: (
        encoding_operations_config.AssociatedEncodingOperation
    )


@typing.final
class Associations:
    """The program's resolved associations, which association resolution reads.

    Each value quality and logical operation is added once, concurrently with
    others, and only after everything that reads its associations is added.
    Each Value Operation is added whenever resolution executes it.
    """

    def __init__(self, roots: project_roots.ProjectRoots):
        """Initialize with the program's project roots, whose configs have the associations, and nothing added."""
        self._project_roots = roots
        # The edge to each value quality's one encoding, by the value
        # quality's full typed name.
        self._value_encodings: dict[str, reference_graph.ReferenceEdge] = {}
        # Each Abstract Operation, and its associations, by the full typed
        # names of the encodings that they list, in order, by the Abstract
        # Operation's full typed name.
        self._encoding_operations: dict[
            str,
            tuple[
                ast.AbstractOperationDefinition,
                dict[
                    tuple[str, ...],
                    encoding_operations_config.AssociatedEncodingOperation,
                ],
            ],
        ] = {}
        # The full typed names of the Abstract Operations whose associations a
        # diagnostic in their project's config files keeps from being used.
        self._unusable_abstract_operations: set[str] = set()
        # The diagnostics about each added Value Operation's associations, by
        # the Value Operation's full typed name.
        self._value_operation_diagnostics: dict[str, list[diagnostics.Diagnostic]] = {}
        # Each Encoding Operation that resolution chose, by the full typed
        # names of its Abstract Operation and of the encodings that its
        # association lists, which identify the association, so that each
        # association is checked once however many executions choose it.
        self._chosen_encoding_operations: dict[
            tuple[str, tuple[str, ...]], ChosenEncodingOperation
        ] = {}

    def add_value(
        self, definition: ast.ValueDefinition
    ) -> list[diagnostics.Diagnostic]:
        """Find the one encoding associated with a value quality, and return a diagnostic if it has none."""
        name_content = definition.typed_name.name_content
        table = self._project_roots.get_association_table(name_content.fqun.canonical)
        if isinstance(table, project_roots.NoProjectConfig):
            return [
                association_resolution_diagnostics.NoProjectRootForAssociationsDiagnostic(
                    location=definition.typed_name.location,
                    value_quality=definition.typed_name.source_typed_name,
                    config_path=str(project_config.CONFIG_FILE.path),
                )
            ]
        value_encodings = table.value_encodings
        # The diagnostic that keeps the project's Value Encoding Associations
        # from being used is already reported.
        if value_encodings is None:
            return []
        associated_encodings = value_encodings.get(name_content.path.name)
        # Only the value quality's own universe can associate it with an
        # encoding, so without one nothing can ever hold the value.
        if associated_encodings is None:
            return [
                association_resolution_diagnostics.ValueHasNoEncodingDiagnostic(
                    location=definition.typed_name.location,
                    value_quality=definition.typed_name.source_typed_name,
                )
            ]
        if len(associated_encodings) > 1:
            # TODO: Choose between a value quality's encodings when each
            # particle is created, as the spec allows.
            raise NotImplementedError(
                f"{definition.typed_name.source_typed_name} has more than one encoding:"
                + f" {[encoding.full_typed_name for encoding in associated_encodings]}"
            )
        self._value_encodings[definition.typed_name.full_typed_name] = (
            reference_graph.ReferenceEdge(
                enclosing_definition=definition,
                global_name_reference=associated_encodings[0],
            )
        )
        return []

    def add_logical_operation(
        self, definition: ast.LogicalOperationDefinition
    ) -> list[diagnostics.Diagnostic]:
        """Add a logical operation's associations with Encoding Operations, and return a diagnostic for each association that cannot be used."""
        return self._add_abstract_operation(definition)

    def add_value_operation(self, definition: ast.ValueOperationDefinition):
        """Add a Value Operation's associations with Encoding Operations.

        Adding the same Value Operation again changes nothing.
        ``value_operation_diagnostics`` returns the diagnostics about the
        associations. A Value Operation with such a diagnostic has no usable
        associations.
        """
        association_diagnostics = self._add_abstract_operation(definition)
        name = definition.typed_name.full_typed_name
        # An execution of a Value Operation with a wrong association does not
        # fall back to compiling the Value Operation's statements, because the
        # wrong association might have been the one that the execution needed.
        if association_diagnostics:
            self._unusable_abstract_operations.add(name)
        # Each addition finds the same diagnostics, so only the first is kept.
        _ = self._value_operation_diagnostics.setdefault(name, association_diagnostics)

    def value_operation_diagnostics(self) -> list[diagnostics.Diagnostic]:
        """Return the diagnostics about the associations of every added Value Operation, once every definition is resolved."""
        found: list[diagnostics.Diagnostic] = []
        for association_diagnostics in self._value_operation_diagnostics.values():
            found.extend(association_diagnostics)
        return found

    def _add_abstract_operation(
        self, definition: ast.AbstractOperationDefinition
    ) -> list[diagnostics.Diagnostic]:
        """Add an Abstract Operation's associations with Encoding Operations, and return a diagnostic for each association that cannot be used."""
        name_content = definition.typed_name.name_content
        table = self._project_roots.get_association_table(name_content.fqun.canonical)
        # An Abstract Operation in a universe without a project config has no
        # associations. The value qualities of that universe report the
        # missing config.
        if isinstance(table, project_roots.NoProjectConfig):
            self._encoding_operations[definition.typed_name.full_typed_name] = (
                definition,
                {},
            )
            return []
        associated_encoding_operations = table.encoding_operations
        # The diagnostic that keeps the project's Encoding Operation
        # associations from being used is already reported.
        if associated_encoding_operations is None:
            self._unusable_abstract_operations.add(
                definition.typed_name.full_typed_name
            )
            return []
        encoding_operations: dict[
            tuple[str, ...], encoding_operations_config.AssociatedEncodingOperation
        ] = {}
        association_diagnostics: list[diagnostics.Diagnostic] = []
        abstract_operation = (definition.typed_name.name_type, name_content.path.name)
        for encodings, association in associated_encoding_operations.get(
            abstract_operation, {}
        ).items():
            view_diagnostics = _view_name_diagnostics(definition, association)
            if view_diagnostics:
                association_diagnostics.extend(view_diagnostics)
                continue
            encoding_operations[encodings] = association
        self._encoding_operations[definition.typed_name.full_typed_name] = (
            definition,
            encoding_operations,
        )
        return association_diagnostics

    def value_encoding(
        self, value_quality: ast.GlobalTypedNameReference
    ) -> ast.GlobalTypedNameReference | None:
        """Return the value quality's encoding, or None if it is not defined or has none, which is already reported."""
        edge = self._value_encodings.get(value_quality.full_typed_name)
        if edge is None:
            return None
        return edge.global_name_reference

    def has_usable_associations(
        self,
        abstract_operation: ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
    ) -> bool:
        """Whether the Abstract Operation's associations can be used, rather than a diagnostic in its project's config files, which is already reported, keeping them from being used."""
        return (
            abstract_operation.full_typed_name not in self._unusable_abstract_operations
        )

    def choose_encoding_operation(
        self,
        abstract_operation: ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
        encodings: tuple[str, ...],
    ) -> ast.GlobalTypedNameReference | None:
        """Return the Encoding Operation whose association with the Abstract Operation lists the encodings with the full typed names ``encodings``, in their order, if one does, and record that resolution chose it.

        The Abstract Operation's associations must be usable.
        """
        definition, encoding_operations = self._encoding_operations[
            abstract_operation.full_typed_name
        ]
        association = encoding_operations.get(encodings)
        if association is None:
            return None
        key = (abstract_operation.full_typed_name, encodings)
        # Resolution chooses concurrently, but every choice of this association
        # records the same value, so concurrent writes of a key are harmless and
        # need no lock.
        if key not in self._chosen_encoding_operations:
            self._chosen_encoding_operations[key] = ChosenEncodingOperation(
                abstract_operation=definition,
                encoding_operation_association=association,
            )
        return association.reference

    def chosen_encoding_operations(self) -> list[ChosenEncodingOperation]:
        """Return each Encoding Operation that resolution chose, with the association that chose it, once every definition is resolved."""
        return list(self._chosen_encoding_operations.values())

    def chosen_edges(
        self,
    ) -> tuple[list[reference_graph.ReferenceEdge], Collection[diagnostics.Diagnostic]]:
        """Return the edge to each encoding and Encoding Operation that resolution chose, once every definition is resolved, with the diagnostics about the edges.

        An edge to a universe that the project whose config writes the edge
        does not configure is left out. Each such universe is reported once
        for each config file, at the place in the file that names it first.
        """
        candidates = list(self._value_encodings.values())
        for chosen in self._chosen_encoding_operations.values():
            candidates.append(
                reference_graph.ReferenceEdge(
                    enclosing_definition=chosen.abstract_operation,
                    global_name_reference=chosen.encoding_operation_association.reference,
                )
            )
        edges: list[reference_graph.ReferenceEdge] = []
        # The diagnostic for each config file and the universe that it names.
        unconfigured: dict[
            tuple[str | None, str],
            config_diagnostics.ExternalUniverseNotConfiguredDiagnostic,
        ] = {}
        for edge in candidates:
            reference = edge.global_name_reference
            # An association is in the config of the project whose universe
            # its references are written in, which is loaded.
            _, root_config = typing.cast(
                "tuple[define_path.DefinePath, config_loader.Config]",
                self._project_roots.get_loaded_root_config(
                    reference.enclosing_fqun.canonical
                ),
            )
            diagnostic = root_config.check_universe_configured(reference.name_content)
            if diagnostic is None:
                edges.append(edge)
                continue
            location = diagnostic.location
            key = (location.file_path, diagnostic.universe)
            first = unconfigured.get(key)
            # Resolution chooses associations concurrently, so the edges come
            # in no fixed order.
            if first is None or (location.line, location.column) < (
                first.location.line,
                first.location.column,
            ):
                unconfigured[key] = diagnostic
        return edges, unconfigured.values()

    def value_encodings(self) -> Mapping[str, ast.GlobalTypedNameReference]:
        """Return each value quality's encoding, by the value quality's full typed name, once every value quality is added."""
        value_encodings: dict[str, ast.GlobalTypedNameReference] = {}
        for value_quality, edge in self._value_encodings.items():
            value_encodings[value_quality] = edge.global_name_reference
        return value_encodings


def _view_name_diagnostics(
    definition: ast.AbstractOperationDefinition,
    association: encoding_operations_config.AssociatedEncodingOperation,
) -> list[diagnostics.Diagnostic]:
    """Return a diagnostic for each way the views that the association lists differ from the Abstract Operation's, which must match in name and order."""
    encoding_operation_name = association.reference.source_typed_name
    abstract_operation_name = definition.typed_name.source_typed_name
    abstract_operation_views = definition.views
    # Views at the same place cannot be compared meaningfully when the counts
    # differ.
    if len(association.views) != len(abstract_operation_views):
        return [
            association_resolution_diagnostics.AssociationAbstractOperationViewCountDiagnostic(
                location=association.reference.location,
                encoding_operation_name=encoding_operation_name,
                view_count=len(association.views),
                abstract_operation_name=abstract_operation_name,
                abstract_operation_view_count=len(abstract_operation_views),
                definition_location=definition.typed_name.location,
            )
        ]
    view_diagnostics: list[diagnostics.Diagnostic] = []
    # ZIP: This relationship can only be created here because the
    # association and the Abstract Operation are separate definitions, and
    # this checks the rule that the views the association lists are the
    # Abstract Operation's views in the same order, so it compares the two
    # views at each position. A different number of views was reported above.
    for number, (associated_view, abstract_operation_view) in enumerate(
        zip(association.views, abstract_operation_views, strict=True), start=1
    ):
        abstract_operation_view_name = (
            abstract_operation_view.typed_name.name_content.name
        )
        if associated_view.name != abstract_operation_view_name:
            view_diagnostics.append(
                association_resolution_diagnostics.AssociationAbstractOperationViewNameDiagnostic(
                    location=associated_view.name_location,
                    view_number=number,
                    view_name=associated_view.name,
                    encoding_operation_name=encoding_operation_name,
                    abstract_operation_name=abstract_operation_name,
                    abstract_operation_view_name=abstract_operation_view_name,
                    definition_location=abstract_operation_view.typed_name.location,
                )
            )
    return view_diagnostics
