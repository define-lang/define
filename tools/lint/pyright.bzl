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

# This exists for performance reasons. When we put py_test and py_binary
# rules into pyright_test deps, they all create their own runfiles tree,
# making the test setup take forever. We only need the actual .py and .pyi
# files from all the deps.
def _pyright_deps_impl(ctx):
    """Re-export only type-checking inputs from transitive Python dependencies."""
    transitive_sources = depset(
        transitive = [dep[PyInfo].transitive_sources for dep in ctx.attr.deps],
    )
    imports = depset(
        transitive = [dep[PyInfo].imports for dep in ctx.attr.deps],
    )
    direct_original_sources = depset(
        transitive = [dep[PyInfo].direct_original_sources for dep in ctx.attr.deps],
    )
    transitive_pyi_files = depset(
        transitive = [dep[PyInfo].transitive_pyi_files for dep in ctx.attr.deps],
    )
    source_and_stub_files = depset(
        transitive = [transitive_sources, transitive_pyi_files],
    )
    return [
        DefaultInfo(
            files = source_and_stub_files,
            runfiles = ctx.runfiles(transitive_files = source_and_stub_files),
        ),
        PyInfo(
            transitive_sources = transitive_sources,
            imports = imports,
            direct_original_sources = direct_original_sources,
            transitive_pyi_files = transitive_pyi_files,
        ),
    ]

_pyright_deps = rule(
    implementation = _pyright_deps_impl,
    attrs = {
        "deps": attr.label_list(providers = [PyInfo]),
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
    _pyright_deps(
        name = name + "_deps",
        testonly = True,
        deps = deps,
    )

    pyproject_data = [pyproject] if pyproject else []
    env = dict(kwargs.pop("env", {}))
    env["FORCE_COLOR"] = "1"

    py_test(
        name = name,
        srcs = ["//tools/lint:pyright_test_runner.py"] + srcs,
        main = "//tools/lint:pyright_test_runner.py",
        args = [
            "$(location //:basedpyright)",
            native.package_name(),
        ],
        data = pyproject_data + [
            "//:basedpyright",
            "//:pyproject.toml",
            ":" + name + "_pyi",
            "//typestubs:typestubs",
        ],
        deps = [":" + name + "_deps"] + [
            "@pypi//types_protobuf",
            "@pypi//types_pyyaml",
        ],
        env = env,
        tags = ["pyright"],
        **kwargs
    )
