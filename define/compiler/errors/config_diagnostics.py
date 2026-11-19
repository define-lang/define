"""Diagnostics that loading a project's config files reports."""

from __future__ import annotations

import typing
from typing import ClassVar

from define.compiler import constants
from define.compiler.errors import diagnostics

if typing.TYPE_CHECKING:
    from crates.source_rendering.python import rendering


class ConfigDiagnostic(diagnostics.BaseDiagnostic):
    """Base class for diagnostics about a project's config file, the one at config_path."""

    config_path: str

    @typing.override
    def format(self, sources: rendering.SourceMap, /) -> str:
        """Format the diagnostic with the config file that it is about."""
        return f'File "{self.config_path}"\n{self.render_message(sources)}'


# A path to a field of a config file: field names, and the indices of repeated
# fields' elements.
type FieldPath = tuple[str | int, ...]


def _project_root_help(config_path: str) -> str:
    return (
        f"A project root is any directory containing {config_path}.\n"
        + f"For more information, see {constants.DOCS_ROOT}/project-root.md"
    )


class AssociationNameInAnotherUniverseDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for a name in an association config file whose field requires a definition in the same universe as the project, when the name is in another universe.

    Its location is the name.
    """

    # The association's field that holds the name.
    field_name: str
    name: str
    # The project's universe.
    fqun: str

    @typing.override
    def render_message(self, _sources: rendering.SourceMap, /) -> str:
        return (
            f"'{self.field_name}' must be in this project's universe,"
            + f" '{self.fqun}', but '{self.name}' is not."
        )


class ConfigViolationDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for the field of a config file at field_path, whose value breaks a rule of its schema."""

    field_path: FieldPath
    violation_message: str

    @typing.override
    def render_message(self, _sources: rendering.SourceMap, /) -> str:
        # The field path as it is written in messages, such as
        # `deps.local[0].path`.
        field_path_text = ""
        for element in self.field_path:
            if isinstance(element, int):
                field_path_text += f"[{element}]"
            elif field_path_text:
                field_path_text += f".{element}"
            else:
                field_path_text = element
        return f"{field_path_text}: {self.violation_message}"


class DuplicateEncodingOperationDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for an Encoding Operation association that an earlier association already makes.

    Its location is the later association.
    """

    logical_operation: str
    encoding_operation: str
    # The earlier association.
    first_location: rendering.SourceLocation

    @typing.override
    def render_message(self, sources: rendering.SourceMap, /) -> str:
        return (
            f"Logical operation '{self.logical_operation}' is already associated"
            + f" with Encoding Operation '{self.encoding_operation}' here:\n"
            + sources.render_location(self.first_location)
        )


class DuplicateFqunDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for two project roots that declare the same fully-qualified universe name.

    Its location is the universe_name of the later project's config.
    """

    fqun: str
    # The universe_name of the earlier project's config, which declares the
    # universe first.
    existing_location: rendering.SourceLocation

    @typing.override
    def render_message(self, sources: rendering.SourceMap, /) -> str:
        return (
            f"Universe '{self.fqun}' cannot be defined again here, since it is"
            f" already defined here:\n{sources.render_location(self.existing_location)}"
        )


class DuplicateLocalDependencyDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for a local dependency whose universe name an earlier local dependency already declares.

    The first declaration of a universe wins, and the later one is not used.
    Its location is the later local dependency's universe_name.
    """

    universe_name: str
    # The universe_name of the earlier local dependency.
    first_location: rendering.SourceLocation

    @typing.override
    def render_message(self, sources: rendering.SourceMap, /) -> str:
        return (
            f"Universe '{self.universe_name}' is already declared by an earlier"
            " local dependency, so only that one is used. It is here:\n"
            f"{sources.render_location(self.first_location)}"
        )


class DuplicateValueEncodingDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for an encoding association that an earlier association already makes.

    Its location is the later association.
    """

    value: str
    encoding: str
    # The earlier association.
    first_location: rendering.SourceLocation

    @typing.override
    def render_message(self, sources: rendering.SourceMap, /) -> str:
        return (
            f"Value quality '{self.value}' is already associated with encoding"
            + f" '{self.encoding}' here:\n"
            + sources.render_location(self.first_location)
        )


class EncodingOperationsConfigNotFoundDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for a project config that says the project has Encoding Operation associations, when encoding_operations_config_path does not exist.

    Its location is the project config's has_encoding_operations.
    """

    encoding_operations_config_path: str

    @typing.override
    def render_message(self, _sources: rendering.SourceMap, /) -> str:
        return (
            "The project says it has Encoding Operation associations, but"
            + f" {self.encoding_operations_config_path} was not found."
        )


class EncodingsConfigNotFoundDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for a project config that says the project has encoding associations, when encodings_config_path does not exist.

    Its location is the project config's has_encodings.
    """

    encodings_config_path: str

    @typing.override
    def render_message(self, _sources: rendering.SourceMap, /) -> str:
        return (
            "The project says it has encoding associations, but"
            + f" {self.encodings_config_path} was not found."
        )


class ExternalUniverseNotConfiguredDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for when a cross-universe reference targets an unconfigured universe."""

    universe: str
    current_universe_name: str
    message_format: ClassVar[str] = (
        "universe '{self.universe}' is not configured as a dependency "
        "of this universe ({self.current_universe_name}); "
        "add it to .define/deps/local.defcl"
    )


class LocalDependencyOnOwnUniverseDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for a local dependency that names the universe of the project that declares it.

    That universe is already at the project root, so the entry is not used.
    Its location is the local dependency's universe_name.
    """

    universe: str
    message_format: ClassVar[str] = (
        "Universe '{self.universe}' is the project's own universe, so it cannot"
        + " be a dependency of that project."
    )


class NotRunFromProjectRootDiagnostic(ConfigDiagnostic):
    """Diagnostic for a compiler run from a directory that is not a project root, so has no project config at config_path."""

    message_format: ClassVar[str] = (
        "The Define compiler must be run from a project root directory."
    )

    @typing.override
    def format(self, sources: rendering.SourceMap, /) -> str:
        # The config file does not exist, so showing it as the file that the
        # diagnostic is about would mislead.
        return self.render_message(sources)

    @typing.override
    def render_message(self, sources: rendering.SourceMap, /) -> str:
        return f"{super().render_message(sources)}\n" + _project_root_help(
            self.config_path
        )


class SubRootFqunMismatchDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for a sub-root whose project config declares a different universe than the local dependency that names it.

    Its location is the universe_name of the sub-root's project config.
    """

    expected_fqun: str
    actual_fqun: str
    sub_root_path: str
    message_format: ClassVar[str] = (
        "Sub-root at '{self.sub_root_path}' is configured as a dependency"
        + " with universe '{self.expected_fqun}' but the actual project root"
        + " in that path says it has the universe name '{self.actual_fqun}'"
    )


class SubRootNotProjectRootDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for a sub-root that a local dependency names but that is not a project root.

    Its location is the local dependency's path.
    """

    sub_root_path: str
    # The project config that the sub-root does not have.
    sub_root_config_path: str

    @typing.override
    def render_message(self, _sources: rendering.SourceMap, /) -> str:
        return (
            f"The referenced subroot ({self.sub_root_path}) is not a valid project"
            + f" root: {self.sub_root_config_path} not found.\n"
            + _project_root_help(self.sub_root_config_path)
        )


class SubRootPathAlreadyDeclaredDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for a local dependency that declares a sub-root at a path that another local dependency already declared.

    The first declaration of a path wins, and the later one is not used. Its
    location is the later local dependency's path.
    """

    sub_root_path: str
    # The path of the first local dependency that declares the sub-root.
    first_location: rendering.SourceLocation

    @typing.override
    def render_message(self, sources: rendering.SourceMap, /) -> str:
        first_entry = sources.render_location(self.first_location)
        return (
            f"This local dependency declares the sub-root '{self.sub_root_path}',"
            " but an earlier one already declares it, so only that one is used."
            f" It is here:\n{first_entry}"
        )


class UnsortedEncodingOperationDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for an Encoding Operation association whose logical operation sorts before the association before it.

    Its location is the association's logical operation.
    """

    logical_operation: str
    previous_logical_operation: str

    @typing.override
    def render_message(self, _sources: rendering.SourceMap, /) -> str:
        return (
            "Encoding Operation associations must be sorted by logical operation,"
            + f" but '{self.logical_operation}' comes after"
            + f" '{self.previous_logical_operation}'."
        )


class UnsortedValueEncodingDiagnostic(diagnostics.Diagnostic):
    """Diagnostic for an encoding association whose value quality sorts before the association before it.

    Its location is the association's value.
    """

    value: str
    previous_value: str

    @typing.override
    def render_message(self, _sources: rendering.SourceMap, /) -> str:
        return (
            "Encoding associations must be sorted by value quality, but"
            + f" '{self.value}' comes after '{self.previous_value}'."
        )
