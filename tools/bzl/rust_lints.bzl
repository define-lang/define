"""Every Rust target's lint config, which can allow more lints from the command line.

`--//tools/bzl:allowed_rust_lints=<lint>,...` allows each lint it names in every
Rust target, after the lint config from Cargo.toml.
"""

load("@bazel_skylib//rules:common_settings.bzl", "BuildSettingInfo")

# rules_rust exports LintsInfo only from its private providers, which rules_rs
# loads too.
# buildifier: disable=bzl-visibility
load("@rules_rust//rust/private:providers.bzl", "LintsInfo")

def with_allowed_lints(lints, allowed):
    """Return a lint config's rustc and clippy flags with more lints allowed.

    Args:
        lints: the LintsInfo of a lint config
        allowed: the rustc and clippy lints to allow, such as `unused_variables`
            or `clippy::unused_self`

    Returns:
        A struct of the rustc flags `rustc` and the clippy flags `clippy`.
    """

    # The clippy action passes the rustc flags and then the clippy flags, and
    # rustc applies the last flag for a lint.
    return struct(
        rustc = lints.rustc_lint_flags + ["--allow=" + lint for lint in allowed if "::" not in lint],
        clippy = lints.clippy_lint_flags + ["--allow=" + lint for lint in allowed if "::" in lint],
    )

def _rust_lint_config_impl(ctx):
    lints = ctx.attr.lint_config[LintsInfo]
    allowed = ctx.attr._allowed_lints[BuildSettingInfo].value
    if not allowed:
        return [lints]
    flags = with_allowed_lints(lints, allowed)
    return [LintsInfo(
        rustc_lint_flags = flags.rustc,
        rustc_lint_files = lints.rustc_lint_files,
        clippy_lint_flags = flags.clippy,
        clippy_lint_files = lints.clippy_lint_files,
        rustdoc_lint_flags = lints.rustdoc_lint_flags,
        rustdoc_lint_files = lints.rustdoc_lint_files,
    )]

rust_lint_config = rule(
    implementation = _rust_lint_config_impl,
    doc = "A lint config that also allows the lints that `allowed_rust_lints` names.",
    attrs = {
        "lint_config": attr.label(mandatory = True, providers = [LintsInfo]),
        "_allowed_lints": attr.label(default = Label("//tools/bzl:allowed_rust_lints")),
    },
)
