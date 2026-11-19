"""What structural validation finds about each definition and file, which later stages read."""

from __future__ import annotations

import typing

import msgspec

if typing.TYPE_CHECKING:
    from define.compiler import ast
    from define.compiler.data_structures import define_path
    from define.compiler.graphs import reference_graph


class ParticleStatementValidity(msgspec.Struct, frozen=True):
    """Name validation results for a Particle Statement."""

    target_ok: bool
    source_ok: bool = True
    from_is_prefix_of_to: bool = False


class StructuralDefinitionResult(msgspec.Struct):
    """What structural validation found about one definition in a file."""

    definition: ast.GlobalDefinition
    # Whether structural validation found no problem with the definition.
    # Reference graph validation reads it for each Value Operation.
    structurally_valid: bool

    reference_edges: list[reference_graph.ReferenceEdge] = msgspec.field(
        default_factory=list
    )
    particle_statement_validity: list[ParticleStatementValidity] = msgspec.field(
        default_factory=list
    )
    # Whether each position looked at by an Operation Argument Statement in an
    # action is valid, in source order.
    looked_at_position_validity: list[bool] = msgspec.field(default_factory=list)


class FileValidationResult(msgspec.Struct):
    """Validation output for one source file."""

    file_path: define_path.DefinePath  # Full path: root_prefix / relative file path.
    root_prefix: define_path.DefinePath
    # The file's validated definitions, in source order.
    definition_results: list[StructuralDefinitionResult]
