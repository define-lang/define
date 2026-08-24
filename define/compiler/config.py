"""Project configuration loading and validation."""

from __future__ import annotations

import types
import typing
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path, PurePosixPath

import protovalidate
from google.protobuf import message

from defcl.python import exceptions as dcl_exceptions
from defcl.python import parser as defcl_parser
from define.compiler import constants, exceptions
from define.compiler.data_structures import define_path
from define.config.deps import local_pb2
from define.config.project import config_pb2

if typing.TYPE_CHECKING:
    from collections.abc import Mapping


class ConfigError(exceptions.DefineError):
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
    existing_config: define_path.DefinePath
    new_config: define_path.DefinePath

    def __init__(
        self,
        fqun: str,
        existing_root: define_path.DefinePath,
        new_root: define_path.DefinePath,
        config_subpath: define_path.DefinePath,
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


class ConfigSyntaxError(ConfigError):
    """Configuration file has DCL syntax errors."""

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


CONFIG_PATH = define_path.DefinePathFromPosix(
    PurePosixPath(".define/project/config.defcl")
)
LOCAL_DEPS_PATH = define_path.DefinePathFromPosix(
    PurePosixPath(".define/deps/local.defcl")
)

_EMPTY_DEPS: types.MappingProxyType[str, define_path.DefinePathFromPosix] = (
    types.MappingProxyType({})
)


@dataclass(slots=True)
class ProjectRootConfig:
    """Resolved project configuration for a project root."""

    fqun: str
    sub_roots: Mapping[str, define_path.DefinePath]


class ConfigLoader:
    """Loads and validates Define project configuration files."""

    _root: define_path.DefinePath

    def __init__(self, root: define_path.DefinePath):
        """Initialize with the project root path."""
        self._root = root

    @cached_property
    def _parser(self) -> defcl_parser.Parser:
        return defcl_parser.Parser()

    def _load_config[M: message.Message](
        self, subpath: define_path.DefinePath, message_type: type[M]
    ) -> M:
        """Load and validate a defcl config file."""
        path = Path((self._root / subpath).as_posix_path())
        try:
            result = self._parser.parse_file(path, message_type)
        except dcl_exceptions.DclSyntaxError as e:
            raise ConfigSyntaxError(e) from e
        try:
            # TODO: Remove this cast when Protovalidate's annotation is fixed:
            # https://github.com/bufbuild/protovalidate-py/issues/522
            typing.cast(
                "typing.Callable[[message.Message], None]", protovalidate.validate
            )(result)
        except protovalidate.ValidationError as e:
            messages: list[str] = []
            for violation in e.violations:
                field = violation.proto.field
                if field:
                    field_path = ".".join(elem.field_name for elem in field.elements)
                    messages.append(f"{field_path}: {violation.proto.message}")
                else:
                    # TODO: Add a real test for this once the config schema
                    # can produce a root-level/message-level protovalidate violation.
                    messages.append(violation.proto.message)
            raise ConfigValidationError(path, messages) from e
        return result

    def assert_is_project_root(self) -> None:
        """Raise NotProjectRootError if the root is not a project root."""
        config_path = Path((self._root / CONFIG_PATH).as_posix_path())
        if not config_path.exists():
            raise NotProjectRootError(config_path, self._root)

    def project_config(self) -> config_pb2.ProjectConfigFile:
        """Load and validate the project configuration."""
        return self._load_config(CONFIG_PATH, config_pb2.ProjectConfigFile)

    def local_deps_config(
        self,
    ) -> types.MappingProxyType[str, define_path.DefinePathFromPosix]:
        """Load and validate the local dependency overrides.

        Returns an immutable mapping from universe name to relative path.
        """
        deps_path = Path((self._root / LOCAL_DEPS_PATH).as_posix_path())
        if not deps_path.exists():
            return _EMPTY_DEPS
        result = self._load_config(LOCAL_DEPS_PATH, local_pb2.LocalDepsFile)
        deps: dict[str, define_path.DefinePathFromPosix] = {}
        for dep in result.deps.local:
            if dep.universe_name in deps:
                raise ConfigValidationError(
                    deps_path,
                    [f'deps.local: duplicate universe_name "{dep.universe_name}"'],
                )
            deps[dep.universe_name] = define_path.DefinePathFromPosix(
                PurePosixPath(dep.path)
            )
        return types.MappingProxyType(deps)

    def load_project_root_config(
        self, expected_fqun: str | None = None
    ) -> ProjectRootConfig:
        """Load and resolve this root's own configuration.

        Raises:
            SubRootFqunMismatchError: If expected_fqun is given and does not
                match the universe name declared by this root's own config.
        """
        self.assert_is_project_root()
        fqun = self.project_config().project.universe_name or ""
        if expected_fqun and fqun != expected_fqun:
            raise SubRootFqunMismatchError(
                expected_fqun=expected_fqun,
                actual_fqun=fqun,
                sub_root_path=str(self._root),
            )
        return ProjectRootConfig(fqun=fqun, sub_roots=self.local_deps_config())
