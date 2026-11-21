"""The program's Encoding Operation Associations, looked up by Abstract Operation."""

from __future__ import annotations

import functools
import typing

import msgspec

from define.compiler import ast
from define.compiler.config import project_roots
from define.compiler.data_structures import computed_once
from define.compiler.errors import association_resolution_diagnostics
from define.compiler.graphs import reference_graph

if typing.TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from define.compiler.config import encoding_operations_config
    from define.compiler.errors import diagnostics


# An Abstract Operation, and its associations, by the full typed names of the
# encodings that they list, in order.
type _AbstractOperationEncodingOperations = tuple[
    ast.AbstractOperationDefinition,
    dict[tuple[str, ...], encoding_operations_config.AssociatedEncodingOperation],
]


class ChosenEncodingOperation(msgspec.Struct, frozen=True):
    """An Encoding Operation that association resolution chose for an execution of an Abstract Operation."""

    abstract_operation: ast.AbstractOperationDefinition
    # The association of the Abstract Operation that names the Encoding
    # Operation.
    encoding_operation_association: (
        encoding_operations_config.AssociatedEncodingOperation
    )


@typing.final
class AbstractOperationAssociations:
    """Each Abstract Operation's Encoding Operations, and which of them association resolution chose.

    This answers which Encoding Operation an Abstract Operation's associations
    name for the encodings at an execution. Deciding what an execution of a
    Value Operation runs is ``ValueOperationResolver``'s job.

    A Value Operation's associations are in its own universe. A logical
    operation's associations are in its own universe and in the universe of
    each encoding at an execution.

    It is thread-safe. Each logical operation must be added once, with
    ``add_abstract_operation``, before ``choose_encoding_operation`` is called
    for it.
    """

    def __init__(self, roots: project_roots.ProjectRoots):
        """Initialize with the program's project roots, whose configs have the associations, and nothing added."""
        self._project_roots = roots
        # Each Abstract Operation, and its associations, by the full typed
        # names of the encodings that they list, in order, by the Abstract
        # Operation's full typed name. None means that a diagnostic in the
        # project's config files keeps the associations from being used.
        self._encoding_operations: dict[
            str, _AbstractOperationEncodingOperations | None
        ] = {}
        # The diagnostics about the associations that resolution looks up
        # when an execution first needs them: each added Value Operation's,
        # and each logical operation's in each other universe.
        self._lookup_diagnostics: list[diagnostics.Diagnostic] = []
        # The usable associations of each logical operation in each universe
        # other than its own, by the full typed name of the logical operation
        # and the universe, once an execution needs them. None means that the
        # universe's associations cannot be used, which is already reported.
        self._other_universe_associations: computed_once.ComputedOnce[
            tuple[str, str],
            Mapping[
                tuple[str, ...], encoding_operations_config.AssociatedEncodingOperation
            ]
            | None,
        ] = computed_once.ComputedOnce()
        # Each Encoding Operation that resolution chose, by the full typed
        # names of its Abstract Operation and of the encodings that its
        # association lists, which identify the association, so that each
        # association is checked once however many executions choose it.
        self._chosen_encoding_operations: dict[
            tuple[str, tuple[str, ...]], ChosenEncodingOperation
        ] = {}

    def add_value_operation(self, definition: ast.ValueOperationDefinition):
        """Add a Value Operation's associations with Encoding Operations.

        Each Value Operation must be added at most once.
        ``lookup_diagnostics`` returns the diagnostics about the
        associations. A Value Operation with such a diagnostic has no usable
        associations.
        """
        association_diagnostics = self.add_abstract_operation(definition)
        # An execution of a Value Operation with a wrong association does not
        # fall back to compiling the Value Operation's statements, because the
        # wrong association might have been the one that the execution needed.
        if association_diagnostics:
            self._encoding_operations[definition.typed_name.full_typed_name] = None
        self._lookup_diagnostics.extend(association_diagnostics)

    def lookup_diagnostics(self) -> list[diagnostics.Diagnostic]:
        """Return the diagnostics about the associations that resolution looked up when an execution first needed them, once every definition is resolved."""
        return self._lookup_diagnostics

    def add_abstract_operation(
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
            self._encoding_operations[definition.typed_name.full_typed_name] = None
            return []
        encoding_operations, association_diagnostics = _usable_associations(
            definition,
            associated_encoding_operations.get(
                definition.typed_name.full_typed_name, {}
            ),
        )
        self._encoding_operations[definition.typed_name.full_typed_name] = (
            definition,
            encoding_operations,
        )
        return association_diagnostics

    def has_usable_associations(
        self,
        abstract_operation: ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
        encodings: Sequence[ast.GlobalTypedNameReference],
    ) -> bool:
        """Whether the associations that an execution of the Abstract Operation with ``encodings`` could use can be used, rather than an already reported diagnostic keeping some of them from being used.

        Those are the Abstract Operation's associations in its own universe,
        and a logical operation's associations in the universe of each
        encoding.
        """
        own = self._encoding_operations[abstract_operation.full_typed_name]
        if own is None:
            return False
        definition, _ = own
        if not isinstance(definition, ast.LogicalOperationDefinition):
            return True
        for associations in self._associations_in_other_universes(
            definition, encodings
        ):
            if associations is None:
                return False
        return True

    def choose_encoding_operation(
        self,
        abstract_operation: ast.GlobalTypedName[ast.GlobalNameContent[ast.Fqun | None]],
        encodings: Sequence[ast.GlobalTypedNameReference],
    ) -> ast.GlobalTypedNameReference | None:
        """Return the Encoding Operation whose association with the Abstract Operation lists ``encodings``, in their order, if one does, and record that resolution chose it.

        The associations of a logical operation are in its own universe or in
        the universe of one of the encodings. ``has_usable_associations``
        must be true for the Abstract Operation and ``encodings``.
        """
        definition, encoding_operations = typing.cast(
            "_AbstractOperationEncodingOperations",
            self._encoding_operations[abstract_operation.full_typed_name],
        )
        key_encodings = tuple(encoding.full_typed_name for encoding in encodings)
        association = encoding_operations.get(key_encodings)
        if association is None and isinstance(
            definition, ast.LogicalOperationDefinition
        ):
            association = self._other_universe_association(
                definition, encodings, key_encodings
            )
        if association is None:
            return None
        key = (abstract_operation.full_typed_name, key_encodings)
        # Resolution chooses concurrently, but every choice of this association
        # records the same value, so concurrent writes of a key are harmless and
        # need no lock.
        if key not in self._chosen_encoding_operations:
            self._chosen_encoding_operations[key] = ChosenEncodingOperation(
                abstract_operation=definition,
                encoding_operation_association=association,
            )
        return association.reference

    def _other_universe_association(
        self,
        definition: ast.LogicalOperationDefinition,
        encodings: Sequence[ast.GlobalTypedNameReference],
        key_encodings: tuple[str, ...],
    ) -> encoding_operations_config.AssociatedEncodingOperation | None:
        """Return the association of the logical operation that lists the encodings, from the universe of one of the encodings other than the logical operation's, if one makes it."""
        # At most one universe can make a matching association. A
        # universe that makes one must see the logical operation and every
        # listed encoding, and must define one of them, so two such universes
        # would each depend on the other. Project dependencies cannot form a
        # cycle, so the first match is the only one.
        for associations in self._associations_in_other_universes(
            definition, encodings
        ):
            # The caller checked that every universe's associations are
            # usable.
            association = typing.cast(
                "Mapping[tuple[str, ...], encoding_operations_config.AssociatedEncodingOperation]",
                associations,
            ).get(key_encodings)
            if association is not None:
                return association
        return None

    def _associations_in_other_universes(
        self,
        definition: ast.LogicalOperationDefinition,
        encodings: Sequence[ast.GlobalTypedNameReference],
    ) -> list[
        Mapping[tuple[str, ...], encoding_operations_config.AssociatedEncodingOperation]
        | None
    ]:
        """Return the logical operation's usable associations in the universe of each encoding that is not in the logical operation's own universe."""
        own_universe = definition.typed_name.name_content.fqun.canonical
        found: list[
            Mapping[
                tuple[str, ...], encoding_operations_config.AssociatedEncodingOperation
            ]
            | None
        ] = []
        for encoding in encodings:
            universe = encoding.effective_fqun.canonical
            # The associations in the logical operation's own universe were
            # read when it was added.
            if universe == own_universe:
                continue
            key = (definition.typed_name.full_typed_name, universe)
            look_up = functools.partial(
                self._look_up_associations_in_universe, definition, encoding
            )
            found.append(self._other_universe_associations.get(key, look_up))
        return found

    def _look_up_associations_in_universe(
        self,
        definition: ast.LogicalOperationDefinition,
        encoding: ast.GlobalTypedNameReference,
    ) -> (
        Mapping[tuple[str, ...], encoding_operations_config.AssociatedEncodingOperation]
        | None
    ):
        """Look up the usable associations of the logical operation in the universe of the encoding, or None if they cannot be used, and record their diagnostics."""
        table = self._project_roots.get_referenced_association_table(encoding)
        # A universe that cannot be loaded, or whose Encoding Operation
        # associations cannot be used, is already reported.
        if (
            table is None
            or isinstance(table, project_roots.NoProjectConfig)
            or table.encoding_operations is None
        ):
            return None
        associations, association_diagnostics = _usable_associations(
            definition,
            table.encoding_operations.get(definition.typed_name.full_typed_name, {}),
        )
        self._lookup_diagnostics.extend(association_diagnostics)
        return associations

    def chosen_encoding_operations(self) -> list[ChosenEncodingOperation]:
        """Return each Encoding Operation that resolution chose, with the association that chose it, once every definition is resolved."""
        return list(self._chosen_encoding_operations.values())

    def chosen_edges(self) -> list[reference_graph.ReferenceEdge]:
        """Return the edge to each Encoding Operation that resolution chose, once every definition is resolved."""
        edges: list[reference_graph.ReferenceEdge] = []
        for chosen in self._chosen_encoding_operations.values():
            edges.append(
                reference_graph.ReferenceEdge(
                    enclosing_definition=chosen.abstract_operation,
                    global_name_reference=chosen.encoding_operation_association.reference,
                )
            )
        return edges


def _usable_associations(
    definition: ast.AbstractOperationDefinition,
    associations: Mapping[
        tuple[str, ...], encoding_operations_config.AssociatedEncodingOperation
    ],
) -> tuple[
    dict[tuple[str, ...], encoding_operations_config.AssociatedEncodingOperation],
    list[diagnostics.Diagnostic],
]:
    """Return the associations of the Abstract Operation whose views match its views, and a diagnostic for each way the others do not."""
    usable: dict[
        tuple[str, ...], encoding_operations_config.AssociatedEncodingOperation
    ] = {}
    association_diagnostics: list[diagnostics.Diagnostic] = []
    for encodings, association in associations.items():
        view_diagnostics = _view_name_diagnostics(definition, association)
        if view_diagnostics:
            association_diagnostics.extend(view_diagnostics)
            continue
        usable[encodings] = association
    return usable, association_diagnostics


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
