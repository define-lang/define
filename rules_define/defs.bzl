"""Rules that compile Define programs."""

load("@bazel_skylib//lib:paths.bzl", "paths")

# The compiler requires its current working directory to be the project root,
# but Bazel runs every action from the execution root. The command therefore
# changes into the project root and reaches the compiler and the declared
# output by their paths from the execution root. Bazel may give an action a
# stdin that the compiler would read as piped source text, so the compiler
# reads its stdin from /dev/null instead.
_COMPILE_COMMAND = """\
set -e
execution_root="$PWD"
cd "$1"
exec "$execution_root/$2" compile --out "$execution_root/$4" "$3" </dev/null
"""

def _define_binary_impl(ctx):
    generated = ctx.actions.declare_directory(ctx.label.name)
    project_root = paths.join(ctx.label.workspace_root, ctx.label.package)
    compiler = ctx.attr._compiler[DefaultInfo].files_to_run
    ctx.actions.run_shell(
        mnemonic = "DefineCompile",
        progress_message = "Compiling Define program %{label}",
        command = _COMPILE_COMMAND,
        arguments = [
            project_root,
            compiler.executable.path,
            paths.relativize(ctx.file.entry_point.path, project_root),
            generated.path,
        ],
        inputs = ctx.files.srcs + [ctx.file.entry_point],
        outputs = [generated],
        tools = [compiler],
    )
    return [DefaultInfo(files = depset([generated]))]

# TODO: Add a define_library rule that validates a single .dfn file with
# `define validate`, once `define validate` can check a file that is not the
# entry point of a program. It currently applies the Entry Points Restrictions
# to every file it validates, so it rejects any file whose action defines
# interface positions.
define_binary = rule(
    implementation = _define_binary_impl,
    attrs = {
        "entry_point": attr.label(
            allow_single_file = [".dfn"],
            mandatory = True,
            doc = "The file that defines the entry point action of the program.",
        ),
        "srcs": attr.label_list(
            allow_files = [".dfn", ".defcl"],
            doc = (
                "Every Define source and configuration file of the project. " +
                "The package of the target is the project root."
            ),
        ),
        "_compiler": attr.label(
            default = "//define/compiler:main",
            executable = True,
            cfg = "exec",
        ),
    },
    doc = (
        "Compiles a Define program with `define compile` into a directory " +
        "of generated code."
    ),
)
