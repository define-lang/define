"""Settings that every Rust target in the repository shares."""

def lint_config():
    """Return the lint config that applies the workspace's lints from Cargo.toml.

    Every Rust target passes it as its `lint_config`, which is what the clippy
    aspect reads. `lint_config` from `@crates//:defs.bzl` returns None for
    every package except the Cargo package `define`, so it applies no lints.
    """
    return Label("@crates//:workspace_cargo_lints")

def binary_rustc_flags():
    """Return the `rustc_flags` that every rust_binary sets."""

    # Cargo.toml allows this lint, since a rust_test compiles its library's
    # sources as a test binary, where public items that only other crates use
    # look unused. rules_rust passes a target's rustc_flags to rustc after its
    # lint config's flags, and rustc applies the last flag for a lint.
    return ["--deny=dead_code_pub_in_binary"]
