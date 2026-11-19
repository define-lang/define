"""A rule that runs a generator, which fails when it runs longer than a time limit."""

def _run_generator_impl(ctx):
    arguments = ctx.actions.args()
    arguments.add(str(ctx.attr.timeout_seconds))
    arguments.add(ctx.executable.generator)
    arguments.add(ctx.outputs.out)
    arguments.add_all([
        ctx.expand_location(argument, targets = ctx.attr.tools)
        for argument in ctx.attr.arguments
    ])
    ctx.actions.run(
        executable = ctx.executable._run_with_timeout,
        arguments = [arguments],
        outputs = [ctx.outputs.out],
        tools = [ctx.attr.generator[DefaultInfo].files_to_run] + [
            tool[DefaultInfo].files_to_run
            for tool in ctx.attr.tools
        ],
        mnemonic = "RunGenerator",
        progress_message = "Generating %{output}",
    )
    return [DefaultInfo(files = depset([ctx.outputs.out]))]

run_generator = rule(
    implementation = _run_generator_impl,
    doc = "Runs `generator` with the path of `out` and then `arguments`, with no " +
          "shell. Bazel gives a build action no time limit, unlike a test, " +
          "so the generator is killed, together with every process it " +
          "started, and fails after `timeout_seconds`.",
    attrs = {
        "arguments": attr.string_list(
            doc = "Arguments after the output's path. `$(execpath)` can " +
                  "name the targets in `tools`.",
        ),
        "generator": attr.label(
            mandatory = True,
            executable = True,
            cfg = "exec",
        ),
        "out": attr.output(mandatory = True),
        "timeout_seconds": attr.int(default = 60),
        "tools": attr.label_list(
            cfg = "exec",
            doc = "Other programs that the generator runs.",
        ),
        "_run_with_timeout": attr.label(
            default = "//tools/run_with_timeout",
            executable = True,
            cfg = "exec",
        ),
    },
)
