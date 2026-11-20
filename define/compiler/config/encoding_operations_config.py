"""The encoding operations config, .define/encodings/encoding_operations.defcl, which associates the project's Abstract Operations with Encoding Operations."""

from __future__ import annotations

import typing
from pathlib import PurePosixPath

import msgspec

from define.compiler import name_types
from define.compiler.config import config_file, global_names
from define.compiler.data_structures import define_path
from define.compiler.errors import config_diagnostics
from define.config.encodings import encoding_operations_pb2

if typing.TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from crates.source_rendering.python import rendering
    from defcl.python import validator as defcl_validator
    from define.compiler import ast
    from define.compiler.config import config_loader
    from define.compiler.errors import diagnostics

CONFIG_FILE = config_file.ConfigFile(
    path=define_path.DefinePathFromPosix(
        PurePosixPath(".define/encodings/encoding_operations.defcl")
    ),
    message_type=encoding_operations_pb2.EncodingOperationsFile,
)


class AssociatedView(msgspec.Struct, frozen=True):
    """An Interface View that an association lists for its Encoding Operation, with the encoding the association says the view has."""

    # The view's local name, as the association writes it.
    name: str
    # Where the association writes the view's name.
    name_location: rendering.SourceLocation
    encoding: ast.GlobalTypedNameReference


class AssociatedEncodingOperation(msgspec.Struct, frozen=True):
    """The Encoding Operation of an association: a reference to it, located where the association writes it, and its Interface Views in order."""

    reference: ast.GlobalTypedNameReference
    views: tuple[AssociatedView, ...]


# A project's associations of its Abstract Operations with Encoding
# Operations. The Encoding Operations associated with each Abstract Operation
# are keyed by the Abstract Operation's name type and short global name, and
# then by the full typed names of the encodings that each association lists,
# in order.
type EncodingOperationAssociations = Mapping[
    tuple[name_types.NameType, str],
    Mapping[tuple[str, ...], AssociatedEncodingOperation],
]

# The associations of a project that has no Encoding Operation associations.
NO_ASSOCIATIONS: EncodingOperationAssociations = {}


class EncodingOperationsConfigReader(
    config_file.ConfigFileReader[encoding_operations_pb2.EncodingOperationsFile]
):
    """Reads a project root's encoding operations config, which the project config says whether the project has."""

    def __init__(self, root: define_path.DefinePath, source_map: rendering.SourceMap):
        """Initialize with the project root and the source map to register the file with."""
        super().__init__(root, source_map, CONFIG_FILE)

    def load(
        self, config: config_loader.Config
    ) -> tuple[
        EncodingOperationAssociations | None,
        list[diagnostics.FormattableDiagnostic],
    ]:
        """Load and validate the project's Encoding Operation associations with its Abstract Operations.

        Returns the associations, or None if a diagnostic keeps the
        associations from being used, with the associations' diagnostics. The
        associations are empty when the project config does not say that the
        project has Encoding Operation associations.
        """
        # TODO: Once a library can be compiled, report each association whose
        # Abstract Operation the compile never validated. Until then, an
        # association is checked only when the program uses its Abstract
        # Operation, so one that names an unused or undefined Abstract
        # Operation goes unreported.
        if config.has_encoding_operations_location is None:
            return NO_ASSOCIATIONS, []
        # The project config says the file exists, so only then is it checked.
        if not self.exists():
            return None, [
                config_diagnostics.EncodingOperationsConfigNotFoundDiagnostic(
                    location=config.has_encoding_operations_location,
                    encoding_operations_config_path=str(self.path()),
                )
            ]
        result, encoding_operations_diagnostics = self.load_message()
        if result is None:
            return None, encoding_operations_diagnostics
        associations, association_diagnostics = _AssociationsReader(
            result.file, config.fqun
        ).read(result.message.encoding_operations.operation_encodings)
        encoding_operations_diagnostics.extend(association_diagnostics)
        return associations, encoding_operations_diagnostics


class _AbstractOperation(msgspec.Struct, frozen=True, order=True):
    """The Abstract Operation of an association, as the association writes it.

    Associations are sorted by their _AbstractOperation. Each global name has
    only one legal spelling, so the written name identifies the Abstract
    Operation within its name type.
    """

    # The name of the association's field that names the Abstract Operation,
    # which is the Abstract Operation's name type.
    name_type: name_types.NameType
    # The global name, as the association writes it.
    written_name: str

    @property
    def written_typed_name(self) -> str:
        """The typed name of the Abstract Operation, as the association writes it."""
        return f"{self.name_type.value}<{self.written_name}>"


class _ReadAssociation(msgspec.Struct, frozen=True):
    """An association that is not ignored."""

    # The name type of the association's Abstract Operation.
    name_type: name_types.NameType
    # The short global name of the association's Abstract Operation.
    short_name: str
    # The full typed names of the encodings that the association lists, in
    # order.
    encodings: tuple[str, ...]
    encoding_operation: AssociatedEncodingOperation


def _abstract_operation(
    association: encoding_operations_pb2.OperationEncoding,
) -> _AbstractOperation:
    if association.HasField("logical_operation"):
        return _AbstractOperation(
            name_type=name_types.NameType.LOGICAL_OPERATION,
            written_name=association.logical_operation,
        )
    # Validation of the config's schema requires one of the two fields.
    return _AbstractOperation(
        name_type=name_types.NameType.OPERATION, written_name=association.operation
    )


def _encoding_operation(
    file: defcl_validator.ValidatedFile,
    encoding_operation_path: config_diagnostics.FieldPath,
    encoding_operation: encoding_operations_pb2.EncodingOperation,
    fqun: ast.Fqun,
) -> tuple[AssociatedEncodingOperation | None, list[diagnostics.Diagnostic]]:
    """Parse and validate the Encoding Operation at encoding_operation_path, and the encodings of its views.

    Returns it, or None if it cannot be used, with its diagnostics. fqun is
    the project's universe.
    """
    canonical = fqun.canonical
    name, encoding_operation_diagnostics = global_names.config_global_name(
        file,
        (*encoding_operation_path, "name"),
        encoding_operation.name,
        canonical,
    )
    views: list[AssociatedView] = []
    for index, view in enumerate(encoding_operation.views):
        view_path = (*encoding_operation_path, "views", index)
        encoding, encoding_diagnostics = global_names.config_global_name(
            file, (*view_path, "encoding"), view.encoding, canonical
        )
        encoding_operation_diagnostics.extend(encoding_diagnostics)
        if encoding is not None:
            views.append(
                AssociatedView(
                    name=view.view,
                    name_location=file.location_of((*view_path, "view")),
                    encoding=global_names.associated_reference(
                        name_types.NameType.ENCODING, encoding, fqun
                    ),
                )
            )
    if name is None or len(views) != len(encoding_operation.views):
        return None, encoding_operation_diagnostics
    return AssociatedEncodingOperation(
        reference=global_names.associated_reference(
            name_types.NameType.ENCODING_OPERATION, name, fqun
        ),
        views=tuple(views),
    ), encoding_operation_diagnostics


class _AssociationsReader:
    """Reads the associations of one encoding operations config file.

    These associations are ignored:

    - An association that an earlier association already makes.
    - An association that lists the same encodings as an earlier association
      of the same Abstract Operation.
    - An association whose Abstract Operation, Encoding Operation, or listed
      view encoding is not a valid name for it.
    - An association whose Abstract Operation is in another universe.
    """

    def __init__(
        self,
        file: defcl_validator.ValidatedFile,
        fqun: ast.Fqun,
    ):
        """Create a reader for file, whose project's universe is fqun."""
        self._file: defcl_validator.ValidatedFile = file
        self._fqun: ast.Fqun = fqun
        self._diagnostics: list[diagnostics.FormattableDiagnostic] = []
        # The index of the first association of each Abstract Operation and
        # Encoding Operation. Each global name has only one legal spelling, so
        # the written names identify the pair.
        self._first_indexes: dict[tuple[_AbstractOperation, str], int] = {}
        # The first Encoding Operation associated with each Abstract Operation
        # and list of encodings.
        self._first_encoding_operations: dict[
            tuple[_AbstractOperation, tuple[str, ...]], AssociatedEncodingOperation
        ] = {}
        self._previous_abstract_operation: _AbstractOperation | None = None

    def read(
        self, associations: Sequence[encoding_operations_pb2.OperationEncoding]
    ) -> tuple[EncodingOperationAssociations, list[diagnostics.FormattableDiagnostic]]:
        """Return the Encoding Operations of each Abstract Operation from the associations, with the diagnostics about the associations."""
        encoding_operations: dict[
            tuple[name_types.NameType, str],
            dict[tuple[str, ...], AssociatedEncodingOperation],
        ] = {}
        for index, association in enumerate(associations):
            read_association = self._read_association(index, association)
            if read_association is None:
                continue
            abstract_operation = (
                read_association.name_type,
                read_association.short_name,
            )
            encoding_operations.setdefault(abstract_operation, {})[
                read_association.encodings
            ] = read_association.encoding_operation
        return encoding_operations, self._diagnostics

    def _read_association(
        self, index: int, association: encoding_operations_pb2.OperationEncoding
    ) -> _ReadAssociation | None:
        """Check the association at index, and return it, or None if it is ignored."""
        field_path = ("encoding_operations", "operation_encodings", index)
        abstract_operation = _abstract_operation(association)
        abstract_operation_path = (*field_path, abstract_operation.name_type.value)
        short_name = self._check_abstract_operation_name(
            abstract_operation, abstract_operation_path
        )
        encoding_operation, encoding_operation_diagnostics = _encoding_operation(
            self._file,
            (*field_path, "encoding_operation"),
            association.encoding_operation,
            self._fqun,
        )
        self._diagnostics.extend(encoding_operation_diagnostics)
        self._check_sorted(abstract_operation, abstract_operation_path)
        written_encoding_operation = association.encoding_operation.name
        if not self._check_unique_pair(
            index, field_path, abstract_operation, written_encoding_operation
        ):
            return None
        if short_name is None or encoding_operation is None:
            return None
        encodings: list[str] = []
        for view in encoding_operation.views:
            encodings.append(view.encoding.full_typed_name)
        read_association = _ReadAssociation(
            name_type=abstract_operation.name_type,
            short_name=short_name,
            encodings=tuple(encodings),
            encoding_operation=encoding_operation,
        )
        if not self._check_unique_encodings(abstract_operation, read_association):
            return None
        return read_association

    def _check_abstract_operation_name(
        self,
        abstract_operation: _AbstractOperation,
        abstract_operation_path: config_diagnostics.FieldPath,
    ) -> str | None:
        """Return the short global name of abstract_operation, or None if the name is not valid or is in another universe."""
        canonical = self._fqun.canonical
        name, name_diagnostics = global_names.config_global_name(
            self._file,
            abstract_operation_path,
            abstract_operation.written_name,
            canonical,
        )
        self._diagnostics.extend(name_diagnostics)
        if name is None:
            return None
        universe_diagnostic = global_names.check_global_name_in_this_universe(
            abstract_operation.name_type.value, name, canonical
        )
        if universe_diagnostic is not None:
            self._diagnostics.append(universe_diagnostic)
            return None
        return name.path.name

    def _check_sorted(
        self,
        abstract_operation: _AbstractOperation,
        abstract_operation_path: config_diagnostics.FieldPath,
    ):
        """Report abstract_operation if it sorts before the Abstract Operation of the association before it."""
        previous = self._previous_abstract_operation
        self._previous_abstract_operation = abstract_operation
        if previous is None or not abstract_operation < previous:
            return
        self._diagnostics.append(
            config_diagnostics.UnsortedEncodingOperationDiagnostic(
                location=self._file.location_of(abstract_operation_path),
                abstract_operation=abstract_operation.written_typed_name,
                previous_abstract_operation=previous.written_typed_name,
            )
        )

    def _check_unique_pair(
        self,
        index: int,
        field_path: config_diagnostics.FieldPath,
        abstract_operation: _AbstractOperation,
        written_encoding_operation: str,
    ) -> bool:
        """Return whether no earlier association makes the same association as the association at index, and report it if one does."""
        pair = (abstract_operation, written_encoding_operation)
        first_index = self._first_indexes.setdefault(pair, index)
        if first_index == index:
            return True
        self._diagnostics.append(
            config_diagnostics.DuplicateEncodingOperationDiagnostic(
                location=self._file.location_of(field_path),
                abstract_operation=abstract_operation.written_typed_name,
                encoding_operation=written_encoding_operation,
                first_location=self._file.location_of(
                    ("encoding_operations", "operation_encodings", first_index)
                ),
            )
        )
        return False

    def _check_unique_encodings(
        self,
        abstract_operation: _AbstractOperation,
        read_association: _ReadAssociation,
    ) -> bool:
        """Return whether no earlier association of abstract_operation lists the encodings of read_association, and report read_association if one does."""
        encoding_operation = read_association.encoding_operation
        first = self._first_encoding_operations.setdefault(
            (abstract_operation, read_association.encodings), encoding_operation
        )
        if first is encoding_operation:
            return True
        self._diagnostics.append(
            config_diagnostics.DuplicateAssociationEncodingsDiagnostic(
                location=encoding_operation.reference.location,
                abstract_operation=abstract_operation.written_typed_name,
                encoding_operation=encoding_operation.reference.name_content.source_name,
                first_encoding_operation=first.reference.name_content.source_name,
                first_location=first.reference.location,
            )
        )
        return False
