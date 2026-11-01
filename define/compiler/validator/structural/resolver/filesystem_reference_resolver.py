"""Resolution of the references in a program whose files are all on the filesystem."""

from __future__ import annotations

import typing

from define.compiler import config, constants
from define.compiler.data_structures import define_path, typed_name_dict
from define.compiler.validator.structural import file_validator
from define.compiler.validator.structural.resolver import reference_resolver

if typing.TYPE_CHECKING:
    import pathlib


@typing.final
class FilesystemReferenceResolver(reference_resolver.ReferenceResolver):
    """Finds the files and definitions that the references of a program on the filesystem lead to."""

    def load_entry_file(
        self, path: pathlib.PurePosixPath
    ) -> file_validator.LoadedFile | None:
        """Load the program's entry file.

        If the entry file's project config fails to load, records the failure
        as the entry file's result and returns None.
        """
        root_prefix = constants.PROJECT_ROOT
        file_path = define_path.DefinePathFromPosix(path)
        full_path = root_prefix / file_path
        try:
            root_config = self._load_root_config(root_prefix)
        except config.ConfigError as e:
            self._path_tracker.set_result(
                full_path, _make_config_error_file(file_path, root_prefix, e)
            )
            return None
        entry_file = file_validator.FileStructuralValidator().load_file(
            file_validator.FileValidationContext(
                file_path=file_path,
                root_prefix=root_prefix,
                root_config=root_config,
            )
        )
        self._path_tracker.mark_in_progress(full_path)
        self._path_tracker.set_result(full_path, entry_file)
        return entry_file


def _make_config_error_file(
    file_path: define_path.DefinePath,
    root_prefix: define_path.DefinePath,
    error: config.ConfigError,
) -> file_validator.LoadedFile:
    """Create a LoadedFile for a file whose project config failed to load."""
    return file_validator.LoadedFile(
        context=file_validator.FileValidationContext(
            file_path=file_path, root_prefix=root_prefix
        ),
        exception=error,
        source_digest=None,
        file_diagnostics=[],
        definitions=typed_name_dict.TypedNameDict(),
    )
