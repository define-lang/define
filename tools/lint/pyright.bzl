"""Pyright type-checking test macro."""

load("@aspect_rules_py//py:defs.bzl", "py_test")

def pyright_test(name, pyproject, deps = [], srcs = [], data = [], **kwargs):
    """Type-check Python sources in this package with pyright.

    Args:
        name: Test target name.
        pyproject: Label of the package-specific pyproject.toml.
        deps: All Python targets in this package (py_library, py_test,
            py_binary). Their sources are type-checked and their
            transitive deps provide import resolution.
        srcs: Additional Python source files not covered by any target.
        data: Additional data files for the test.
        **kwargs: Additional py_test attributes (tags, size, etc.).
    """
    py_test(
        name = name,
        srcs = ["//tools/lint:pyright_test_runner.py"] + srcs,
        main = "//tools/lint:pyright_test_runner.py",
        args = [native.package_name()],
        data = data + [
            pyproject,
            "//:pyproject.toml",
        ],
        deps = deps + [
            "@pypi//nodejs_wheel_binaries",
            "@pypi//pyright",
        ],
        **kwargs,
    )
