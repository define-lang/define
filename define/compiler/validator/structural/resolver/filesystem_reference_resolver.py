"""Resolution of the references in a program whose files are all on the filesystem."""

from __future__ import annotations

import typing

from define.compiler import constants
from define.compiler.data_structures import define_path, typed_name_dict
from define.compiler.validator.structural import (
    file_validation_context,
    file_validator,
)
from define.compiler.validator.structural.resolver import reference_resolver

if typing.TYPE_CHECKING:
    import pathlib

    from source_rendering.python import rendering


@typing.final
class FilesystemReferenceResolver(reference_resolver.ReferenceResolver):
    """Finds the files and definitions that the references of a program on the filesystem lead to."""

    _file_validator: file_validator.FileStructuralValidator

    def __init__(self, source_map: rendering.SourceMap):
        """Initialize with the source map to register the program's files with, and no files loaded."""
        super().__init__(source_map)
        self._file_validator = file_validator.FileStructuralValidator(source_map)

    def load_entry_file(
        self, path: pathlib.PurePosixPath
    ) -> file_validator.LoadedFile | None:
        """Load the program's entry file.

        If the entry file's project config fails to load, records the entry
        file with no definitions, and returns None after recording the
        config's diagnostics.
        """
        root_prefix = constants.PROJECT_ROOT
        file_path = define_path.DefinePathFromPosix(path)
        full_path = root_prefix / file_path
        root_config = self._load_root_config(root_prefix)
        if root_config is None:
            self._path_tracker.set_result(
                full_path, _make_unloaded_file(file_path, root_prefix)
            )
            return None
        entry_file = self._file_validator.load_file(
            file_validation_context.FileValidationContext(
                file_path=file_path,
                root_prefix=root_prefix,
                root_config=root_config,
            )
        )
        self._path_tracker.mark_in_progress(full_path)
        self._path_tracker.set_result(full_path, entry_file)
        return entry_file


def _make_unloaded_file(
    file_path: define_path.DefinePath,
    root_prefix: define_path.DefinePath,
) -> file_validator.LoadedFile:
    """Create a LoadedFile with no definitions for a file whose project config failed to load."""
    return file_validator.LoadedFile(
        context=file_validation_context.FileValidationContext(
            file_path=file_path, root_prefix=root_prefix
        ),
        exception=None,
        file_diagnostics=[],
        definitions=typed_name_dict.TypedNameDict(),
    )
