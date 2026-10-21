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

# ast-grep can't read its paths from a file, and Windows limits a command line
# to 32,767 characters, so a target with many sources is scanned in batches
# whose paths fit well within that limit.
_MAX_BATCH_PATH_CHARS = 20000

def _batches(srcs):
    batches = [[]]
    batch_chars = 0
    for src in srcs:
        path_chars = len(src.path) + 1
        if batches[-1] and batch_chars + path_chars > _MAX_BATCH_PATH_CHARS:
            batches.append([])
            batch_chars = 0
        batches[-1].append(src)
        batch_chars += path_chars
    return batches

def _ast_grep_aspect_impl(target, ctx):
    if ctx.rule.kind not in ctx.attr._rule_kinds:
        return []
    srcs = [src for src in ctx.rule.files.srcs if src.is_source and src.owner.workspace_name == ""]
    if not srcs:
        return []

    outputs = []
    for index, batch in enumerate(_batches(srcs)):
        output = ctx.actions.declare_file("{}.{}.ast_grep".format(target.label.name, index))
        args = ctx.actions.args()
        args.add_all(batch)
        ctx.actions.run_shell(
            inputs = batch + [ctx.file._config, ctx.file._rules],
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
        outputs.append(output)
    return [OutputGroupInfo(_validation = depset(outputs))]

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
