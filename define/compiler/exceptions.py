"""Exceptions raised by the Define compiler."""

from pathlib import Path, PurePosixPath

from defcl.python import exceptions as dcl_exceptions
from define.compiler import constants
from define.compiler.data_structures import define_path


class DefineError(Exception):
    """Base class for errors raised by the Define compiler."""


class ConfigError(DefineError):
    """Base class for errors raise by anything to do with configuration."""


class NotProjectRootError(ConfigError):
    """A directory is not a Define project root."""

    config_path: Path
    root: str

    def __init__(self, config_path: Path, root: define_path.DefinePath):
        """Initialize with the config path that was not found."""
        self.config_path = config_path
        self.root = str(root)
        if root == constants.PROJECT_ROOT:
            header = "The Define compiler must be run from a project root directory."
        else:
            header = (
                f"The referenced subroot ({self.root}) is not a valid project root:"
                + f" {config_path} not found."
            )
        super().__init__(
            f"{header}\n"
            + f"A project root is any directory containing {config_path}.\n"
            + f"For more information, see {constants.DOCS_ROOT}/project-root.md"
        )


class DuplicateFqunError(ConfigError):
    """Two different sub-roots have the same fully-qualified universe name."""

    fqun: str
    existing_config: PurePosixPath
    new_config: PurePosixPath

    def __init__(
        self,
        fqun: str,
        existing_root: PurePosixPath,
        new_root: PurePosixPath,
        config_subpath: PurePosixPath,
    ):
        """Initialize with the duplicate FQUN and both root paths."""
        self.fqun = fqun
        existing_config = existing_root / config_subpath
        new_config = new_root / config_subpath
        self.existing_config = existing_config
        self.new_config = new_config
        super().__init__(
            f"Universe '{fqun}' is already defined in '{existing_config}'"
            + f" and cannot be redefined in '{new_config}'"
        )


class SubRootFqunMismatchError(ConfigError):
    """A sub-root's project config declares a different universe than expected."""

    expected_fqun: str
    actual_fqun: str
    sub_root_path: str

    def __init__(self, expected_fqun: str, actual_fqun: str, sub_root_path: str):
        """Initialize with the expected and actual FQUNs."""
        self.expected_fqun = expected_fqun
        self.actual_fqun = actual_fqun
        self.sub_root_path = sub_root_path
        super().__init__(
            f"Sub-root at '{sub_root_path}' is configured as a dependency"
            + f" with universe '{expected_fqun}' but the actual project root"
            + f" in that path says it has the universe name '{actual_fqun}'"
        )


class SourceFileNotFoundError(DefineError):
    """A Define source file could not be found on disk."""

    filesystem_path: Path

    def __init__(self, filesystem_path: Path):
        """Initialize with the filesystem path that was not found."""
        self.filesystem_path = filesystem_path
        super().__init__(f"Source file not found: {filesystem_path}")


class ConfigSyntaxError(ConfigError):
    """Configuration file has DCL syntax errors."""

    # TODO: I don't like having exceptions.py depend on defcl. We should
    # perhaps move the config exceptions into config.py or their own module.
    syntax_error: dcl_exceptions.DclSyntaxError

    def __init__(self, syntax_error: dcl_exceptions.DclSyntaxError):
        """Initialize with the underlying syntax error."""
        self.syntax_error = syntax_error
        super().__init__(str(syntax_error))


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
