"""Pyright type-checking aspect for Python targets."""

load("@rules_python//python:defs.bzl", "PyInfo")

_SUPPRESSION_TAG = "no-pyright"

def resolve_extra_paths(roots, imports):
    """Resolve PyInfo imports against tree roots into pyright extra search paths.

    Args:
        roots: List of root path strings (e.g., [".", "bazel-out/k8-fastbuild/bin"]).
        imports: List of import path strings from PyInfo.imports.

    Returns:
        A deduplicated list of extra path strings, always including ".".
    """
    seen = {}
    extra_paths = []
    for root in roots:
        for imp in imports:
            if imp == "_main":
                p = root if root != "." else "."
            elif imp.startswith("_main/"):
                suffix = imp[len("_main/"):]
                p = root + "/" + suffix if root != "." else suffix
            else:
                p = root + "/external/" + imp if root != "." else "external/" + imp
            if p not in seen:
                seen[p] = True
                extra_paths.append(p)

    if "." not in seen:
        extra_paths.insert(0, ".")

    return extra_paths

def _pyright_aspect_impl(target, ctx):
    if PyInfo not in target:
        return []

    if _SUPPRESSION_TAG in ctx.rule.attr.tags:
        return []

    srcs = [f for f in target[DefaultInfo].files.to_list() if f.extension == "py"]
    if not srcs:
        return []

    trans_srcs = target[PyInfo].transitive_sources

    # Build extra search paths from PyInfo.imports resolved against every
    # tree-root that appears in transitive_sources.
    roots = {}
    for f in trans_srcs.to_list():
        root = f.root.path if f.root.path else "."
        roots[root] = True

    imports = target[PyInfo].imports.to_list()
    extra_paths = resolve_extra_paths(roots.keys(), imports)

    report = ctx.actions.declare_file(target.label.name + ".pyright")

    args = ctx.actions.args()
    args.add(report)
    args.add_all(srcs)

    ctx.actions.run(
        executable = ctx.executable._pyright_tool,
        arguments = [args],
        inputs = depset(srcs + ctx.files._config, transitive = [trans_srcs]),
        outputs = [report],
        mnemonic = "Pyright",
        progress_message = "Type-checking %s" % target.label,
        env = {
            "PYRIGHT_EXTRA_PATHS": ":".join(extra_paths),
        },
    )

    return [OutputGroupInfo(pyright = depset([report]))]

pyright_aspect = aspect(
    implementation = _pyright_aspect_impl,
    attr_aspects = ["deps"],
    attrs = {
        "_pyright_tool": attr.label(
            default = "//tools/lint:pyright_tool",
            executable = True,
            cfg = "exec",
        ),
        "_config": attr.label(
            default = "//:pyproject.toml",
            allow_single_file = True,
        ),
    },
)
