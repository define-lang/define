from __future__ import annotations

from typing import TYPE_CHECKING

from tools import runfiles
from tools.bazel_mutation_testing.rust import crates, generator

if TYPE_CHECKING:
    import pathlib

_SOURCE = """\
#[must_use]
pub const fn is_larger(left: u32, right: u32) -> bool {
    left > right
}
"""
_CRATE = crates.Crate(
    label="//crates/example:example",
    name="example",
    root="crates/example/lib.rs",
    tests=("//crates/example:example_test",),
)


def _list_mutants(workspace: pathlib.Path, tracked_paths: frozenset[str]):
    return generator.list_mutants(
        _CRATE,
        workspace=workspace,
        tracked_paths=tracked_paths,
        cargo_mutants=runfiles.resolve_from_env("CARGO_MUTANTS"),
        cargo=runfiles.resolve_from_env("CARGO"),
    )


def _workspace(tmp_path: pathlib.Path) -> pathlib.Path:
    workspace = tmp_path / "workspace"
    source = workspace / _CRATE.root
    source.parent.mkdir(parents=True)
    _ = source.write_text(_SOURCE, encoding="utf-8", newline="\n")
    return workspace


def test_mutants_of_tracked_file(tmp_path: pathlib.Path):
    mutants = _list_mutants(_workspace(tmp_path), frozenset({_CRATE.root}))
    assert [listed.name for listed in mutants] == [
        "crates/example/lib.rs:3:5: replace is_larger -> bool with true",
        "crates/example/lib.rs:3:5: replace is_larger -> bool with false",
        "crates/example/lib.rs:3:10: replace > with == in is_larger",
        "crates/example/lib.rs:3:10: replace > with < in is_larger",
        "crates/example/lib.rs:3:10: replace > with >= in is_larger",
    ]


def test_patches_apply_at_the_workspace_top(tmp_path: pathlib.Path):
    workspace = _workspace(tmp_path)
    mutants = _list_mutants(workspace, frozenset({_CRATE.root}))
    mutants[2].apply(workspace)
    assert "left == /* ~ changed by cargo-mutants ~ */ right" in (
        workspace / _CRATE.root
    ).read_text(encoding="utf-8")


def test_untracked_files_have_no_mutants(tmp_path: pathlib.Path):
    assert _list_mutants(_workspace(tmp_path), frozenset()) == []


def test_binary_beside_the_crate_root_is_not_mutated(tmp_path: pathlib.Path):
    workspace = _workspace(tmp_path)
    binary = workspace / "crates/example/main.rs"
    _ = binary.write_text(
        'fn main() {\n    println!("{}", 1 + 2);\n}\n', encoding="utf-8", newline="\n"
    )
    mutants = _list_mutants(
        workspace, frozenset({_CRATE.root, "crates/example/main.rs"})
    )
    assert {listed.path for listed in mutants} == {_CRATE.root}
