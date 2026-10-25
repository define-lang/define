"""API for declaring a Ruff lint aspect.

Typical usage, in `linters.bzl`:

```starlark
load("//tools/bzl:ruff.bzl", "lint_ruff_aspect")

ruff = lint_ruff_aspect(
    binary = Label("@multitool//tools/ruff"),
    config = Label("//:pyproject.toml"),
    rule_kinds = ["py_library", "py_test"],
)
```

Filegroups tagged `lint-with-ruff` are also linted, and targets tagged
`no-lint` are not.
"""

load("//tools/bzl:lint_batches.bzl", "lint_batches")

def _should_lint(rule, rule_kinds):
    if "no-lint" in rule.attr.tags:
        return False
    if rule.kind == "filegroup":
        return "lint-with-ruff" in rule.attr.tags
    return rule.kind in rule_kinds

def _ruff_aspect_impl(target, ctx):
    if not _should_lint(ctx.rule, ctx.attr._rule_kinds):
        return []
    srcs = [src for src in ctx.rule.files.srcs if src.is_source and src.owner.workspace_name == ""]
    if not srcs:
        return []
    outputs = []
    for index, batch in enumerate(lint_batches(srcs)):
        output = ctx.actions.declare_file("{}.{}.ruff".format(target.label.name, index))
        args = ctx.actions.args()
        args.add_all(batch)
        ctx.actions.run_shell(
            inputs = batch + [ctx.file._config],
            outputs = [output],
            tools = [ctx.executable._ruff],
            # --force-exclude applies the configuration's exclusions even to
            # paths named on the command line.
            command = "{ruff} check --force-exclude --quiet --output-format=concise \"$@\" && touch {output}".format(
                ruff = ctx.executable._ruff.path,
                output = output.path,
            ),
            arguments = [args],
            mnemonic = "Ruff",
            progress_message = "Linting %{label} with Ruff",
        )
        outputs.append(output)
    return [OutputGroupInfo(_validation = depset(outputs))]

def lint_ruff_aspect(binary, config, rule_kinds):
    """Create an aspect that fails the build when `ruff check` reports a violation in a target's sources.

    Args:
        binary: the Ruff executable
        config: the `pyproject.toml` that configures Ruff. Ruff finds it in
            the execution root, the nearest parent directory of every source.
        rule_kinds: the kinds of rules whose sources are linted
    """
    return aspect(
        implementation = _ruff_aspect_impl,
        attrs = {
            "_ruff": attr.label(
                default = binary,
                executable = True,
                cfg = "exec",
            ),
            "_config": attr.label(
                default = config,
                allow_single_file = True,
            ),
            "_rule_kinds": attr.string_list(
                default = rule_kinds,
            ),
        },
    )
