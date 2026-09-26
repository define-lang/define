"""API for declaring an ast-grep lint aspect.

Typical usage, in `linters.bzl`:

```starlark
load("//tools/bzl:ast_grep.bzl", "lint_ast_grep_aspect")

ast_grep = lint_ast_grep_aspect(
    binary = Label("@multitool//tools/ast-grep"),
    config = Label("//:sgconfig.yml"),
    rules = Label("//checks:rules"),
    rule_kinds = ["py_library", "py_test"],
)
```
"""

def _ast_grep_aspect_impl(target, ctx):
    if ctx.rule.kind not in ctx.attr._rule_kinds:
        return []
    srcs = [src for src in ctx.rule.files.srcs if src.is_source and src.owner.workspace_name == ""]
    if not srcs:
        return []

    output = ctx.actions.declare_file(target.label.name + ".ast_grep")
    args = ctx.actions.args()
    args.add_all(srcs)
    ctx.actions.run_shell(
        inputs = srcs + [ctx.file._config, ctx.file._rules],
        outputs = [output],
        tools = [ctx.executable._ast_grep],
        command = "{ast_grep} scan --config={config} --report-style=short \"$@\" && touch {output}".format(
            ast_grep = ctx.executable._ast_grep.path,
            config = ctx.file._config.path,
            output = output.path,
        ),
        arguments = [args],
        mnemonic = "AstGrep",
        progress_message = "Linting %{label} with ast-grep",
    )
    return [OutputGroupInfo(_validation = depset([output]))]

def lint_ast_grep_aspect(binary, config, rules, rule_kinds):
    """Create an aspect that fails the build when `ast-grep scan` reports an error in a target's sources.

    Args:
        binary: the ast-grep executable
        config: the `sgconfig.yml` project configuration
        rules: the source directory that the configuration's `ruleDirs` names.
            It must be the directory itself rather than its files, because
            ast-grep does not load symlinked rule files and Bazel provides a
            source directory as a symlink to a directory of real files.
        rule_kinds: the kinds of rules whose sources are scanned
    """
    return aspect(
        implementation = _ast_grep_aspect_impl,
        attrs = {
            "_ast_grep": attr.label(
                default = binary,
                executable = True,
                cfg = "exec",
            ),
            "_config": attr.label(
                default = config,
                allow_single_file = True,
            ),
            "_rules": attr.label(
                default = rules,
                allow_single_file = True,
            ),
            "_rule_kinds": attr.string_list(
                default = rule_kinds,
            ),
        },
    )
