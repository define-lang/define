"""Basedpyright type-checking test macro."""

load("@aspect_rules_py//py:defs.bzl", "py_test")
load("@rules_python//python:py_info.bzl", "PyInfo")

# py_proto_library generates .pyi stubs but only puts them in
# PyInfo.transitive_pyi_files, not in DefaultInfo.default_runfiles.
# aspect_rules_py's py_library/py_test don't propagate that field,
# so an aspect is needed to walk the dep graph and collect them.

_PyiCollectorInfo = provider(
    "Collects .pyi type stub files from transitive dependencies.",
    fields = {"pyi_files": "depset of .pyi files"},
)

def _pyi_collector_aspect_impl(target, ctx):
    pyi = []
    if PyInfo in target:
        pyi.append(target[PyInfo].transitive_pyi_files)
    for dep in getattr(ctx.rule.attr, "deps", []):
        if _PyiCollectorInfo in dep:
            pyi.append(dep[_PyiCollectorInfo].pyi_files)
    return [_PyiCollectorInfo(pyi_files = depset(transitive = pyi))]

_pyi_collector_aspect = aspect(
    implementation = _pyi_collector_aspect_impl,
    attr_aspects = ["deps"],
)

def _pyi_files_impl(ctx):
    """Collects .pyi type stub files by walking the transitive dep graph."""
    pyi_files = depset(
        transitive = [
            dep[_PyiCollectorInfo].pyi_files
            for dep in ctx.attr.deps
            if _PyiCollectorInfo in dep
        ],
    )
    return [DefaultInfo(
        files = pyi_files,
        runfiles = ctx.runfiles(transitive_files = pyi_files),
    )]

_pyi_files = rule(
    implementation = _pyi_files_impl,
    attrs = {
        "deps": attr.label_list(aspects = [_pyi_collector_aspect]),
    },
)

def pyright_test(name, pyproject = None, deps = [], srcs = [], **kwargs):
    """Type-check Python sources in this package with basedpyright.

    Args:
        name: Test target name.
        pyproject: Label of the package-specific pyproject.toml.
            If None, only the root pyproject.toml is used.
        deps: All Python targets in this package (py_library, py_test,
            py_binary). Their sources are type-checked and their
            transitive deps provide import resolution.
        srcs: Additional Python source files not covered by any target.
        **kwargs: Additional py_test attributes (tags, size, etc.).
    """
    _pyi_files(
        name = name + "_pyi",
        testonly = True,
        deps = deps,
    )

    pyproject_data = [pyproject] if pyproject else []

    py_test(
        name = name,
        srcs = ["//tools/lint:pyright_test_runner.py"] + srcs,
        main = "//tools/lint:pyright_test_runner.py",
        args = [native.package_name()],
        data = pyproject_data + [
            "//:pyproject.toml",
            ":" + name + "_pyi",
        ],
        deps = deps + [
            "@pypi//basedpyright",
        ],
        tags = ["pyright"],
        **kwargs
    )
