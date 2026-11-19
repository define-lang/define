"""Resolution of the references in a program whose files are all on the filesystem."""

from __future__ import annotations

import pathlib
import typing

from define.compiler import constants
from define.compiler.data_structures import define_path
from define.compiler.errors import structural_diagnostics
from define.compiler.validator.structural import (
    file_loader,
    file_validation_context,
)
from define.compiler.validator.structural.resolver import reference_resolver

if typing.TYPE_CHECKING:
    from crates.source_rendering.python import rendering
    from define.compiler.config import project_roots
    from define.compiler.errors import diagnostics


@typing.final
class FilesystemReferenceResolver(reference_resolver.ReferenceResolver):
    """Finds the files and definitions that the references of a program on the filesystem lead to."""

    _source_map: rendering.SourceMap

    def __init__(
        self, source_map: rendering.SourceMap, roots: project_roots.ProjectRoots
    ):
        """Initialize with the source map to register the program's files with, the program's project roots, and no files loaded."""
        super().__init__(roots)
        self._source_map = source_map

    def load_entry_file(
        self, path: pathlib.PurePath
    ) -> tuple[file_loader.LoadedFile | None, list[diagnostics.FormattableDiagnostic]]:
        """Load the program's entry file, at path relative to the current directory, which is the project root, and return it and its diagnostics.

        The file is None if the path is not under the project root or the
        project config fails to load. The diagnostics include why the entry
        file could not be read, since no reference leads into it.
        """
        path_in_project = _path_in_project(pathlib.Path(path))
        if isinstance(
            path_in_project, structural_diagnostics.PathOutsideProjectRootDiagnostic
        ):
            return None, [path_in_project]
        root_config = self._project_roots.load_entry_file_project_config()
        if root_config is None:
            return None, []
        root_prefix = constants.PROJECT_ROOT
        file_path = define_path.DefinePathFromPosix(path_in_project)
        full_path = root_prefix / file_path
        entry_file, file_diagnostics = file_loader.load_file(
            file_validation_context.FileValidationContext(
                file_path=file_path,
                root_prefix=root_prefix,
                root_config=root_config,
            ),
            self._source_map,
        )
        self._path_tracker.mark_in_progress(full_path)
        self._path_tracker.set_result(full_path, entry_file)
        if entry_file.read_failure is None:
            return entry_file, list(file_diagnostics)
        return entry_file, [entry_file.read_failure, *file_diagnostics]


def _path_in_project(
    path: pathlib.Path,
) -> pathlib.PurePosixPath | structural_diagnostics.PathOutsideProjectRootDiagnostic:
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
            structural_diagnostics.AbsolutePathOutsideProjectRootDiagnostic
            if path.is_absolute()
            else structural_diagnostics.RelativePathOutsideProjectRootDiagnostic
        )
        return diagnostic_class(
            input_path=path.as_posix(),
            resolved_path=resolved.as_posix(),
            project_root=project_root.as_posix(),
        )
    return pathlib.PurePosixPath(relative.as_posix())
