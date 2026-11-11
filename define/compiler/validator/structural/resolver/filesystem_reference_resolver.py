"""Resolution of the references in a program whose files are all on the filesystem."""

from __future__ import annotations

import pathlib
import typing

from define.compiler import constants
from define.compiler.data_structures import define_path
from define.compiler.errors import diagnostics
from define.compiler.validator.structural import (
    file_validation_context,
    file_validator,
)
from define.compiler.validator.structural.resolver import reference_resolver

if typing.TYPE_CHECKING:
    from crates.source_rendering.python import rendering


@typing.final
class FilesystemReferenceResolver(reference_resolver.ReferenceResolver):
    """Finds the files and definitions that the references of a program on the filesystem lead to."""

    _file_validator: file_validator.FileStructuralValidator

    def __init__(self, source_map: rendering.SourceMap):
        """Initialize with the source map to register the program's files with, and no files loaded."""
        super().__init__(source_map)
        self._file_validator = file_validator.FileStructuralValidator(source_map)

    def load_entry_file(
        self, path: pathlib.PurePath
    ) -> file_validator.LoadedFile | None:
        """Load the program's entry file, at path relative to the current directory, which is the project root.

        Returns None, after recording the diagnostics for why, if the path is
        not under the project root or the project config fails to load.
        """
        path_in_project = _path_in_project(pathlib.Path(path))
        if isinstance(path_in_project, diagnostics.PathOutsideProjectRootDiagnostic):
            self._program_diagnostics.append(path_in_project)
            return None
        root_prefix = constants.PROJECT_ROOT
        root_config = self._load_root_config(root_prefix)
        if root_config is None:
            return None
        file_path = define_path.DefinePathFromPosix(path_in_project)
        full_path = root_prefix / file_path
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


def _path_in_project(
    path: pathlib.Path,
) -> pathlib.PurePosixPath | diagnostics.PathOutsideProjectRootDiagnostic:
    """Return path relative to the project root, which is the current directory, or the diagnostic for why it is not under the project root."""
    if ".." in path.parts:
        # A ".." can leave the project root and come back (or the
        # reverse), which a lexical prefix comparison cannot see.
        project_root = pathlib.Path.cwd().resolve()
        resolved = (project_root / path).resolve()
    else:
        project_root = pathlib.Path.cwd()
        resolved = project_root / path
    try:
        relative = resolved.relative_to(project_root)
    except ValueError:
        diagnostic_class = (
            diagnostics.AbsolutePathOutsideProjectRootDiagnostic
            if path.is_absolute()
            else diagnostics.RelativePathOutsideProjectRootDiagnostic
        )
        return diagnostic_class(
            input_path=path.as_posix(),
            resolved_path=resolved.as_posix(),
            project_root=project_root.as_posix(),
        )
    return pathlib.PurePosixPath(relative.as_posix())
