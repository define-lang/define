"""Basedpyright type-checking test macro."""

load("@aspect_rules_py//py:defs.bzl", _py_test = "py_test")
load("@rules_python//python:py_info.bzl", "PyInfo")

# aspect_rules_py doesn't propagate transitive_pyi_files through py_test
# and py_binary targets, so an aspect is needed to walk the dep graph and
# collect .pyi stubs directly from each target.

_PyiCollectorInfo = provider(
    "Collects .pyi type stub files from transitive dependencies.",
    fields = {"transitive_pyi_files": "depset of .pyi files"},
)

def _pyi_collector_aspect_impl(target, ctx):
    pyi = []
    if PyInfo in target:
        pyi.append(target[PyInfo].transitive_pyi_files)
    for dep in getattr(ctx.rule.attr, "deps", []):
        if _PyiCollectorInfo in dep:
            pyi.append(dep[_PyiCollectorInfo].transitive_pyi_files)
    return [_PyiCollectorInfo(
        transitive_pyi_files = depset(transitive = pyi),
    )]

_pyi_collector_aspect = aspect(
    implementation = _pyi_collector_aspect_impl,
    attr_aspects = ["deps"],
)

# The other PyInfo fields (transitive_sources, imports,
# direct_original_sources) propagate fine through py_test/py_binary, so
# we read them directly from deps. This rule also avoids the performance
# cost of each dep creating its own runfiles tree.
def _pyright_deps_impl(ctx):
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
        transitive = [
            dep[_PyiCollectorInfo].transitive_pyi_files
            for dep in ctx.attr.deps
        ],
    )
    source_and_stub_files = depset(transitive = [transitive_sources, transitive_pyi_files])
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
        "deps": attr.label_list(
            providers = [PyInfo],
            aspects = [_pyi_collector_aspect],
        ),
    },
)

def pyright_test(name, deps = [], srcs = [], **kwargs):
    """Type-check Python sources in this package with basedpyright.

    Tag a target "include-subpackages" when deps also lists Python targets
    from packages below this one. tools/check_python_deps.py reads that tag
    to decide which pyright_test is expected to cover each Python target.

    Args:
        name: Test target name.
        deps: All Python targets in this package (py_library, py_test,
            py_binary). Their sources are type-checked and their
            transitive deps provide import resolution.
        srcs: Additional Python source files not covered by any target.
        **kwargs: Additional py_test attributes (tags, size, etc.).
    """
    _pyright_deps(
        name = name + "_deps",
        testonly = True,
        deps = deps,
    )

    env = dict(kwargs.pop("env", {}))
    env["FORCE_COLOR"] = "1"

    tags = ["no-lint", "pyright"] + kwargs.pop("tags", [])

    _py_test(
        name = name,
        srcs = ["//tools/bzl:pyright_test_runner.py"] + srcs,
        main = "//tools/bzl:pyright_test_runner.py",
        args = [
            "$(location //:basedpyright)",
            native.package_name(),
        ],
        data = [
            "//:basedpyright",
            "//:pyproject.toml",
            "//typestubs:typestubs",
        ],
        deps = [":" + name + "_deps"] + [
            "@pypi//types_protobuf",
            "@pypi//types_pyyaml",
        ],
        env = env,
        tags = tags,
        **kwargs
    )
