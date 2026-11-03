"""The inputs for validating one file."""

from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING

import msgspec

from define.compiler import constants
from define.compiler.data_structures import define_path

if TYPE_CHECKING:
    from define.compiler import config


class FileValidationContext(msgspec.Struct, frozen=True, dict=True):
    """Immutable input for validating a single file."""

    file_path: define_path.DefinePath
    root_prefix: define_path.DefinePath
    root_config: config.ProjectRootConfig | None = None
    is_filesystem_context: bool = True

    @cached_property
    def full_path(self) -> define_path.DefinePath:
        """The full filesystem path for this validation context."""
        return self.root_prefix / self.file_path

    @cached_property
    def expected_definition_path(self) -> define_path.DefinePath | None:
        """The expected definition path for filesystem-backed validation."""
        return self.file_path.without_suffix(constants.DEFINE_FILE_SUFFIX)


class EmptyFileValidationContext(FileValidationContext, frozen=True, dict=True):
    """Validation context for non-filesystem source validation."""

    file_path: define_path.DefinePath = constants.NON_FILESYSTEM_PATH
    root_prefix: define_path.DefinePath = define_path.EMPTY
    root_config: config.ProjectRootConfig | None = None
    is_filesystem_context: bool = False

    @cached_property
    def expected_definition_path(self) -> define_path.DefinePath | None:
        """The expected definition path, absent for source-only validation."""
        return None
