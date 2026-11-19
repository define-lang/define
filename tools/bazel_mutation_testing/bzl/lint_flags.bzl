"""A rule that writes Rust lint flags, and the lints and rules mutation runs turn off, to a file."""

# rules_rust exports LintsInfo only from its private providers, which rules_rs
# loads too.
# buildifier: disable=bzl-visibility
load("@rules_rust//rust/private:providers.bzl", "LintsInfo")
load("//tools/bzl:rust_lints.bzl", "with_allowed_lints")
load(":lint_settings.bzl", "AST_GREP_RULES", "PYRIGHT_RULES", "RUFF_RULES", "RUST_LINTS")

def _lint_flags_impl(ctx):
    lints = ctx.attr.lint_config[LintsInfo]
    mutation_run = with_allowed_lints(lints, RUST_LINTS)
    output = ctx.actions.declare_file(ctx.label.name + ".json")
    ctx.actions.write(output, json.encode({
        "mutation_run": {"clippy": mutation_run.clippy, "rustc": mutation_run.rustc},
        "repository": {"clippy": lints.clippy_lint_flags, "rustc": lints.rustc_lint_flags},
        "turned_off": {
            "ast_grep": AST_GREP_RULES,
            "pyright": PYRIGHT_RULES,
            "ruff": RUFF_RULES,
            "rust": RUST_LINTS,
        },
    }))
    return [DefaultInfo(files = depset([output]))]

lint_flags = rule(
    implementation = _lint_flags_impl,
    doc = "Writes a lint config's rustc and clippy flags, in the repository " +
          "and in mutation runs, and the turned-off lints, to `<name>.json`.",
    attrs = {"lint_config": attr.label(mandatory = True, providers = [LintsInfo])},
)
