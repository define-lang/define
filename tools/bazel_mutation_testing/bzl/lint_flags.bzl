"""A rule that writes Rust lint flags, and the lints mutation runs turn off, to a file."""

# rules_rust exports LintsInfo only from its private providers, which rules_rs
# loads too.
# buildifier: disable=bzl-visibility
load("@rules_rust//rust/private:providers.bzl", "LintsInfo")
load("//tools/bzl:rust_lints.bzl", "with_allowed_lints")
load(":lint_settings.bzl", "TURNED_OFF")

def _lint_flags_impl(ctx):
    lints = ctx.attr.lint_config[LintsInfo]
    mutation_run = with_allowed_lints(lints, TURNED_OFF)
    output = ctx.actions.declare_file(ctx.label.name + ".json")
    ctx.actions.write(output, json.encode({
        "mutation_run": {"clippy": mutation_run.clippy, "rustc": mutation_run.rustc},
        "repository": {"clippy": lints.clippy_lint_flags, "rustc": lints.rustc_lint_flags},
        "turned_off": TURNED_OFF,
    }))
    return [DefaultInfo(files = depset([output]))]

lint_flags = rule(
    implementation = _lint_flags_impl,
    doc = "Writes a lint config's rustc and clippy flags, in the repository " +
          "and in mutation runs, and the turned-off lints, to `<name>.json`.",
    attrs = {"lint_config": attr.label(mandatory = True, providers = [LintsInfo])},
)
