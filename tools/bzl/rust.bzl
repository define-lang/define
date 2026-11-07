"""Settings that every Rust target in the repository shares."""

def lint_config():
    """Return the lint config that applies the workspace's lints from Cargo.toml.

    Every Rust target passes it as its `lint_config`, which is what the clippy
    aspect reads. `lint_config` from `@crates//:defs.bzl` returns None for
    every package except the Cargo package `define`, so it applies no lints.
    """
    return Label("@crates//:workspace_cargo_lints")
