"""Exceptions raised by the Define compiler."""

from pathlib import Path

from define.compiler import constants


class DefineError(Exception):
    """Base class for errors raised by the Define compiler."""


class ConfigError(DefineError):
    """Base class for errors raise by anything to do with configuration."""


# TODO: This will need to specify what directory is missing the config, for sub-roots.
class NotProjectRootError(ConfigError):
    """The current directory is not a Define project root."""

    config_path: Path

    def __init__(self, config_path: Path):
        """Initialize with the config path that was not found."""
        self.config_path = config_path
        super().__init__(
            f"Not a Define project root: {config_path} not found.\n"
            + "The Define compiler must be run from a project root directory.\n"
            + f"A project root is any directory containing {config_path}.\n"
            + f"For more information, see {constants.DOCS_ROOT}/project-root.md"
        )


class SourceFileNotFoundError(DefineError):
    """A Define source file could not be found on disk."""

    filesystem_path: Path

    def __init__(self, filesystem_path: Path):
        """Initialize with the filesystem path that was not found."""
        self.filesystem_path = filesystem_path
        super().__init__(f"Source file not found: {filesystem_path}")


class ConfigValidationError(ConfigError):
    """Project configuration failed validation."""

    config_path: Path
    violation_messages: list[str]

    def __init__(self, config_path: Path, violation_messages: list[str]):
        """Initialize with the config path and list of violation messages."""
        self.config_path = config_path
        self.violation_messages = violation_messages
        violations_text = "\n".join(f"  - {msg}" for msg in violation_messages)
        super().__init__(
            f'File "{config_path}"\nInvalid configuration:\n{violations_text}'
        )


class PathError(DefineError):
    """A file path that does not fall under the project root."""

    label: str = "Path is outside the project root"
    input_path: Path
    resolved_path: Path
    project_root: Path

    def __init__(self, input_path: Path, resolved_path: Path, project_root: Path):
        """Initialize with the input path, resolved path, and project root."""
        self.input_path = input_path
        self.resolved_path = resolved_path
        self.project_root = project_root
        super().__init__(
            f"{self.label}: {input_path}\n"
            + f"  Resolved to: {resolved_path}\n"
            + f"  Project root: {project_root}\n"
            + f"For more information, see {constants.DOCS_ROOT}/project-root.md"
        )


class AbsolutePathError(PathError):
    """An absolute path does not fall under the project root."""

    label: str = "Absolute path is outside the project root"


class RelativePathError(PathError):
    """A relative path resolves to a location outside the project root."""

    label: str = "Relative path resolves to outside the project root"
