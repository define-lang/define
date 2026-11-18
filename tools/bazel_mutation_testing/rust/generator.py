"""List Rust mutants with cargo-mutants."""

from __future__ import annotations

import pathlib
import subprocess
import tempfile
from typing import TYPE_CHECKING

import msgspec

from tools.bazel_mutation_testing import bazel, mutant

if TYPE_CHECKING:
    from tools.bazel_mutation_testing.rust import crates

# cargo-mutants reads a package's sources from the directory of its manifest,
# so each crate gets a manifest whose `src` links to the crate root's
# directory. Listing mutants reads syntax alone, so the manifest names no
# dependencies. Cargo would otherwise also take a `main.rs` or `bin`
# directory beside the crate root as another crate's sources.
_MANIFEST = """\
[package]
name = "{name}"
version = "0.0.0"
edition = "2024"
publish = false
autobins = false
autoexamples = false
autotests = false
autobenches = false

[lib]
path = "src/{root}"

[workspace]
"""


class ListingError(Exception):
    """cargo-mutants failed to list a crate's mutants."""


class _Mutant(msgspec.Struct, frozen=True):
    name: str
    file: str
    diff: str


def _repository_patch(diff: str, path: str) -> str:
    _, _, body = diff.split("\n", 2)
    return f"--- a/{path}\n+++ b/{path}\n{body}"


def list_mutants(
    crate: crates.Crate,
    *,
    workspace: pathlib.Path,
    tracked_paths: frozenset[str],
    cargo_mutants: pathlib.Path,
    cargo: pathlib.Path,
) -> list[mutant.Mutant]:
    """Return the mutants of `crate`'s sources that are in `tracked_paths`.

    Raises:
        ListingError: cargo-mutants failed.
    """
    crate_directory, root_name = (
        crate.root.rsplit("/", 1) if "/" in crate.root else ("", crate.root)
    )
    with tempfile.TemporaryDirectory() as scratch:
        scratch_path = pathlib.Path(scratch)
        _ = scratch_path.joinpath("Cargo.toml").write_text(
            _MANIFEST.format(name=crate.name, root=root_name),
            encoding="utf-8",
            newline="\n",
        )
        scratch_path.joinpath("src").symlink_to(workspace / crate_directory)
        completed = subprocess.run(
            [cargo_mutants, "mutants", "--list", "--json", "--diff"],
            cwd=scratch_path,
            env=bazel.child_environment(CARGO=str(cargo)),
            capture_output=True,
            check=False,
        )
    if completed.returncode != 0:
        raise ListingError(
            f"cargo-mutants failed to list the mutants of {crate.label}:\n"
            + completed.stderr.decode(errors="replace")
        )
    mutants: list[mutant.Mutant] = []
    for listed in msgspec.json.decode(completed.stdout, type=list[_Mutant]):
        relative_path = listed.file.removeprefix("src/")
        path = (
            f"{crate_directory}/{relative_path}" if crate_directory else relative_path
        )
        if path not in tracked_paths:
            continue
        mutants.append(
            mutant.Mutant(
                name=path + listed.name.removeprefix(listed.file),
                path=path,
                patch=_repository_patch(listed.diff, path),
            )
        )
    return mutants
