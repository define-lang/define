"""Bazel rule for linting and compiling Jinja2 templates."""

_IGNORE_RULES = ["S3", "S6"]

def _jinja_templates_impl(ctx):
    srcs = ctx.files.srcs

    # Action 1: Run j2lint on all templates.
    lint_stamp = ctx.actions.declare_file(ctx.label.name + ".j2lint")
    ignore_args = "--ignore " + " ".join(_IGNORE_RULES)
    src_paths = " ".join([f.path for f in srcs])

    ctx.actions.run_shell(
        inputs = srcs,
        outputs = [lint_stamp],
        tools = [ctx.executable._j2lint_tool],
        command = "{tool} {ignore_args} -- {srcs} && touch {stamp}".format(
            tool = ctx.executable._j2lint_tool.path,
            ignore_args = ignore_args,
            srcs = src_paths,
            stamp = lint_stamp.path,
        ),
        mnemonic = "J2Lint",
        progress_message = "Linting Jinja2 templates",
    )

    # Action 2: Compile all templates to Python modules.
    compiled_dir = ctx.actions.declare_directory(ctx.label.name + ".compiled")
    compile_args = ctx.actions.args()
    compile_args.add(srcs[0].dirname)
    compile_args.add(compiled_dir.path)

    ctx.actions.run(
        inputs = [lint_stamp] + srcs,
        outputs = [compiled_dir],
        executable = ctx.executable._compile_tool,
        arguments = [compile_args],
        mnemonic = "Jinja2Compile",
        progress_message = "Compiling Jinja2 templates",
    )

    return [DefaultInfo(
        files = depset([compiled_dir]),
        runfiles = ctx.runfiles(files = srcs),
    )]

jinja_templates = rule(
    implementation = _jinja_templates_impl,
    attrs = {
        "srcs": attr.label_list(allow_files = [".j2"], mandatory = True),
        "_j2lint_tool": attr.label(
            default = "//tools:j2lint_runner",
            executable = True,
            cfg = "exec",
        ),
        "_compile_tool": attr.label(
            default = "//tools:compile_jinja_templates",
            executable = True,
            cfg = "exec",
        ),
    },
)
