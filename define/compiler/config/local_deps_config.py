"""The local dependencies config, .define/deps/local.defcl, which declares the project's sub-roots."""

from __future__ import annotations

import types
import typing
from pathlib import PurePosixPath

import msgspec

from define.compiler.config import config_file
from define.compiler.data_structures import define_path
from define.compiler.errors import diagnostics
from define.config.deps import local_pb2

if typing.TYPE_CHECKING:
    from crates.source_rendering.python import rendering

CONFIG_FILE = config_file.ConfigFile(
    path=define_path.DefinePathFromPosix(PurePosixPath(".define/deps/local.defcl")),
    message_type=local_pb2.LocalDepsFile,
)


class LocalDependencyEntry(msgspec.Struct, frozen=True):
    """One entry in a project's local dependencies config."""

    universe: str
    # The sub-root's path, relative to the project that declares it.
    path: define_path.DefinePathFromPosix
    # The locations of the entry's universe_name and path values in
    # local_deps.defcl, for diagnostics about the entry that are found after the
    # config is loaded.
    universe_location: rendering.SourceLocation
    path_location: rendering.SourceLocation


_EMPTY_DEPS: types.MappingProxyType[str, LocalDependencyEntry] = types.MappingProxyType(
    {}
)


# TODO: Read every config file lazily, when something first needs its values,
# instead of reading all of a project's config files when the project is
# loaded. That reading will have to be thread-safe.
class LocalDepsConfigReader(config_file.ConfigFileReader[local_pb2.LocalDepsFile]):
    """Reads a project root's local dependencies config, which a project need not have."""

    def __init__(self, root: define_path.DefinePath, source_map: rendering.SourceMap):
        """Initialize with the project root and the source map to register the file with."""
        super().__init__(root, source_map, CONFIG_FILE)

    def load(
        self,
    ) -> tuple[
        types.MappingProxyType[str, LocalDependencyEntry] | None,
        list[diagnostics.FormattableDiagnostic],
    ]:
        """Load and validate the sub-roots that the project declares.

        Returns an immutable mapping from universe name to its entry, or None
        if a diagnostic keeps the sub-roots from being used, with the file's
        diagnostics. When two entries declare the same universe, the first is
        used.
        """
        if not self.exists():
            return _EMPTY_DEPS, []
        result, deps_diagnostics = self.load_message()
        if result is None:
            return None, deps_diagnostics
        deps: dict[str, LocalDependencyEntry] = {}
        for index, dep in enumerate(result.message.deps.local):
            universe_location = result.file.location_of(
                ("deps", "local", index, "universe_name")
            )
            first_entry = deps.get(dep.universe_name)
            if first_entry is not None:
                deps_diagnostics.append(
                    diagnostics.DuplicateLocalDependencyDiagnostic(
                        location=universe_location,
                        universe_name=dep.universe_name,
                        first_location=first_entry.universe_location,
                    )
                )
                continue
            deps[dep.universe_name] = LocalDependencyEntry(
                universe=dep.universe_name,
                # Parses the config's path string once, and keeps the parsed
                # path for joining onto the project later.
                path=define_path.DefinePathFromPosix(PurePosixPath(dep.path)),
                universe_location=universe_location,
                path_location=result.file.location_of(("deps", "local", index, "path")),
            )
        return types.MappingProxyType(deps), deps_diagnostics
