"""The program's Value Encoding Associations, looked up by value quality."""

from __future__ import annotations

import typing

from define.compiler import ast
from define.compiler.config import project_config, project_roots
from define.compiler.data_structures import computed_once
from define.compiler.errors import association_resolution_diagnostics
from define.compiler.graphs import reference_graph

if typing.TYPE_CHECKING:
    from collections.abc import Mapping

    from define.compiler.errors import diagnostics


@typing.final
class ValueQualityAssociations:
    """Each value quality's encoding, which association resolution looks up the first time something needs it.

    Looking up an encoding is thread-safe.
    """

    def __init__(
        self,
        definitions: Mapping[str, ast.GlobalDefinition],
        roots: project_roots.ProjectRoots,
    ):
        """Initialize with the program's definitions by full typed name, the program's project roots, whose configs have the associations, and nothing looked up."""
        self._definitions = definitions
        self._project_roots = roots
        # The edge to each value quality's one encoding, or None if it has
        # none or is not defined, by the value quality's full typed name, once
        # something needs the encoding.
        self._value_encodings: computed_once.ComputedOnce[
            str, reference_graph.ReferenceEdge | None
        ] = computed_once.ComputedOnce()
        # The diagnostics about the encoding of each value quality that
        # something needed. Each value quality is looked up once, so each
        # lookup adds its diagnostics once.
        self._diagnostics: list[diagnostics.Diagnostic] = []

    def value_encoding(
        self, value_quality: ast.GlobalTypedNameReference
    ) -> ast.GlobalTypedNameReference | None:
        """Return the value quality's encoding, looking it up the first time something needs it, or None if it is not defined or has none.

        ``diagnostics`` returns why a value quality has no encoding.
        """
        name = value_quality.full_typed_name
        edge = self._value_encodings.get(
            name, lambda: self._look_up_value_encoding(name)
        )
        if edge is None:
            return None
        return edge.global_name_reference

    def diagnostics(self) -> list[diagnostics.Diagnostic]:
        """Return the diagnostics about the encoding of each value quality that something needed, once every definition is resolved."""
        return self._diagnostics

    def encoding_edges(self) -> list[reference_graph.ReferenceEdge]:
        """Return the edge to the encoding of each value quality that something needed and that has one, once every definition is resolved."""
        edges: list[reference_graph.ReferenceEdge] = []
        for edge in self._value_encodings.values():
            if edge is not None:
                edges.append(edge)
        return edges

    def value_encodings(self) -> Mapping[str, ast.GlobalTypedNameReference]:
        """Return the encoding of each value quality that something needed and that has one, by the value quality's full typed name, once every definition is resolved."""
        value_encodings: dict[str, ast.GlobalTypedNameReference] = {}
        for value_quality, edge in self._value_encodings.items():
            if edge is not None:
                value_encodings[value_quality] = edge.global_name_reference
        return value_encodings

    def _look_up_value_encoding(
        self, name: str
    ) -> reference_graph.ReferenceEdge | None:
        """Look up the encoding of the value quality whose full typed name is name, and record its diagnostics."""
        definition = self._definitions.get(name)
        # Structural validation reports a value quality that is not defined,
        # or a definition of another type.
        if not isinstance(definition, ast.ValueDefinition):
            return None
        edge, found = self._value_encoding_edge(definition)
        self._diagnostics.extend(found)
        return edge

    def _value_encoding_edge(
        self, definition: ast.ValueDefinition
    ) -> tuple[reference_graph.ReferenceEdge | None, list[diagnostics.Diagnostic]]:
        """Return the edge to the one encoding associated with a value quality, or None with a diagnostic if it has none."""
        name_content = definition.typed_name.name_content
        table = self._project_roots.get_association_table(name_content.fqun.canonical)
        if isinstance(table, project_roots.NoProjectConfig):
            return None, [
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
            return None, []
        associated_encodings = value_encodings.get(name_content.path.name)
        # Only the value quality's own universe can associate it with an
        # encoding, so without one nothing can ever hold the value.
        if associated_encodings is None:
            return None, [
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
        return reference_graph.ReferenceEdge(
            enclosing_definition=definition,
            global_name_reference=associated_encodings[0],
        ), []
