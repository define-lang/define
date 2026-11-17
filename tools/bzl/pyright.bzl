"""Basedpyright type-checking test macro."""

load("@rules_py//py:defs.bzl", "PyInfo", _py_test = "py_test")
load("@rules_python//python:py_info.bzl", LegacyPyInfo = "PyInfo")

# Native extensions must be present so stub imports can resolve to their
# implementation. They are not included in PyInfo's transitive sources or stubs.

_NativeExtensionsInfo = provider(
    "Collects native extensions from dependencies.",
    fields = {"transitive_native_extensions": "depset of native extension files"},
)

def _native_extensions_collector_aspect_impl(target, ctx):
    transitive_native_extensions = []
    native_extensions = []
    if LegacyPyInfo in target and DefaultInfo in target:
        for file in target[DefaultInfo].files.to_list():
            if file.extension in ["so", "pyd"]:
                native_extensions.append(file)
    transitive_native_extensions.append(depset(native_extensions))
    for dep in getattr(ctx.rule.attr, "deps", []):
        if _NativeExtensionsInfo in dep:
            transitive_native_extensions.append(dep[_NativeExtensionsInfo].transitive_native_extensions)

    # rules_py puts py_binary and py_test dependencies on a hidden sibling venv
    # target, so following only deps would miss protobuf libraries below them.
    # The venv attribute has a transition, which makes it a list.
    for venv in getattr(ctx.rule.attr, "venv", []):
        if _NativeExtensionsInfo in venv:
            transitive_native_extensions.append(venv[_NativeExtensionsInfo].transitive_native_extensions)
    return [_NativeExtensionsInfo(
        transitive_native_extensions = depset(transitive = transitive_native_extensions),
    )]

_native_extensions_collector_aspect = aspect(
    implementation = _native_extensions_collector_aspect_impl,
    attr_aspects = ["deps", "venv"],
)

def _pyright_sources_impl(ctx):
    # A pyright_test checks its own package, and the packages below it whose
    # targets it lists. The rest of the transitive sources, including targets
    # it lists from other packages, only resolve imports, and each of their
    # packages has its own pyright_test. A source's owner, rather than its
    # directory, gives its package, since a package can have files in
    # subdirectories, and a rule can generate stubs, such as a PyO3
    # extension's, that no target lists in srcs.
    packages = {ctx.label.package: None}
    for dep in ctx.attr.deps:
        if dep.label.package.startswith(ctx.label.package + "/"):
            packages[dep.label.package] = None
    files = depset(
        ctx.files.srcs,
        transitive = [dep[PyInfo].transitive_sources for dep in ctx.attr.deps] +
                     [dep[PyInfo].transitive_pyi_files for dep in ctx.attr.deps],
    )
    paths = []
    for file in files.to_list():
        if file.owner.package in packages and file.extension in ["py", "pyi"]:
            paths.append(file.short_path)
    sources_file = ctx.actions.declare_file(ctx.label.name + ".txt")
    ctx.actions.write(sources_file, "".join([path + "\n" for path in sorted(paths)]))
    return [DefaultInfo(files = depset([sources_file]))]

_pyright_sources = rule(
    implementation = _pyright_sources_impl,
    attrs = {
        "deps": attr.label_list(providers = [PyInfo]),
        "srcs": attr.label_list(allow_files = [".py", ".pyi"]),
    },
)

# RulesPyInfo fields propagate through Python targets, so this rule reads them
# directly from deps and avoids the cost of each dep creating its own runfiles
# tree.
def _pyright_deps_impl(ctx):
    transitive_sources = depset(
        transitive = [dep[PyInfo].transitive_sources for dep in ctx.attr.deps],
    )
    transitive_pyi_files = depset(
        transitive = [dep[PyInfo].transitive_pyi_files for dep in ctx.attr.deps],
    )
    imports = depset(
        transitive = [dep[PyInfo].imports for dep in ctx.attr.deps],
    )
    virtual_dependencies = depset(
        transitive = [dep[PyInfo].virtual_dependencies for dep in ctx.attr.deps],
    )
    virtual_resolutions = depset(
        transitive = [dep[PyInfo].virtual_resolutions for dep in ctx.attr.deps],
    )
    transitive_native_extensions = depset(
        transitive = [
            dep[_NativeExtensionsInfo].transitive_native_extensions
            for dep in ctx.attr.deps
        ],
    )
    source_and_stub_files = depset(transitive = [transitive_sources, transitive_pyi_files, transitive_native_extensions])
    return [
        DefaultInfo(
            files = source_and_stub_files,
            runfiles = ctx.runfiles(transitive_files = source_and_stub_files),
        ),
        PyInfo(
            transitive_sources = transitive_sources,
            transitive_pyi_files = transitive_pyi_files,
            imports = imports,
            virtual_dependencies = virtual_dependencies,
            virtual_resolutions = virtual_resolutions,
        ),
    ]

_pyright_deps = rule(
    implementation = _pyright_deps_impl,
    attrs = {
        "deps": attr.label_list(
            providers = [PyInfo],
            aspects = [_native_extensions_collector_aspect],
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

    _pyright_sources(
        name = name + "_sources",
        testonly = True,
        deps = deps,
        srcs = srcs,
    )

    env = dict(kwargs.pop("env", {}))
    env["FORCE_COLOR"] = "1"

    tags = ["no-lint", "pyright"] + kwargs.pop("tags", [])

    _py_test(
        name = name,
        srcs = ["//tools/bzl:pyright_test_runner.py"] + srcs,
        main = "//tools/bzl:pyright_test_runner.py",
        args = [
            "$(rlocationpath //:basedpyright)",
            "$(rlocationpath //:pyproject.toml)",
            "$(rlocationpath :" + name + "_sources)",
        ],
        data = [
            ":" + name + "_sources",
            "//:basedpyright",
            "//:pyproject.toml",
            "//typestubs:typestubs",
        ],
        deps = [":" + name + "_deps"] + [
            "//tools:runfiles",
            "@pypi//types_protobuf",
            "@pypi//types_pyyaml",
        ],
        env = env,
        tags = tags,
        **kwargs
    )
