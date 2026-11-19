"""The result of validating a whole Define program, which every validation stage adds its diagnostics to."""

from __future__ import annotations

import itertools
import typing

import msgspec

from define.compiler.errors import diagnostics

if typing.TYPE_CHECKING:
    from collections.abc import Sequence

    from crates.source_rendering.python import rendering
    from define.compiler import ast
    from define.compiler.graphs import reference_graph_order
    from define.compiler.validator.structural import structural_result


class ProgramValidationResult(msgspec.Struct):
    """Full result of validating a Define program."""

    file_results: list[structural_result.FileValidationResult]
    entry_action: ast.ActionDefinition | None
    definition_order: reference_graph_order.ReferenceGraphOrder
    # Each validated definition, by its full typed name.
    definitions: dict[str, ast.GlobalDefinition]
    # The result of each validated definition, by its full typed name, which
    # reference graph validation reads for each action and Value Operation
    # that it validates.
    structural_results: dict[str, structural_result.StructuralDefinitionResult]
    # Each validated Encoding Operation, which association resolution
    # validates once the ones it chooses are loaded.
    encoding_operations: list[ast.EncodingOperationDefinition]
    # The lists that the stages add their diagnostics to, held by reference,
    # so that the result includes diagnostics that a stage finds after the
    # result is built. Each stage only ever adds to its list. Read them only
    # once every stage is done.
    diagnostic_lists: list[Sequence[diagnostics.FormattableDiagnostic]]
    source_map: rendering.SourceMap

    def sorted_diagnostics(self) -> list[diagnostics.FormattableDiagnostic]:
        """Every diagnostic, sorted by file and location, after those that have no location in the order they were found."""
        return sorted(
            itertools.chain.from_iterable(self.diagnostic_lists), key=_diagnostic_order
        )

    def error_strings(self) -> list[str]:
        """Format every diagnostic for the command-line caller."""
        return [
            diagnostic.format(self.source_map)
            for diagnostic in self.sorted_diagnostics()
        ]

    def has_errors(self) -> bool:
        """Whether the program has any diagnostics."""
        # Every diagnostic is an error, which keeps code generation from ever
        # running on a file whose comments have characters the spec does not
        # allow, such as the bidi controls of a Trojan Source attack.
        return any(self.diagnostic_lists)


def _diagnostic_order(
    diagnostic: diagnostics.FormattableDiagnostic,
) -> tuple[str, int, int]:
    """Return a diagnostic's file and its line and column in that file, by which diagnostics are sorted."""
    if isinstance(diagnostic, diagnostics.Diagnostic):
        location = diagnostic.location
        return (location.file_path or "", location.line, location.column)
    # A diagnostic about a whole config file comes before the diagnostics at
    # places in it.
    if isinstance(diagnostic, diagnostics.ConfigDiagnostic):
        return (diagnostic.config_path, 0, 0)
    # The rest have no location, such as the entry path's diagnostics and a
    # file that cannot be read, and come first, in the order they were found.
    return ("", 0, 0)
