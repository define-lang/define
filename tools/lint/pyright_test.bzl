"""Unit tests for pyright aspect path resolution logic."""

load("@bazel_skylib//lib:unittest.bzl", "asserts", "unittest")
load("//tools/lint:pyright.bzl", "resolve_extra_paths")

def _exec_root_main_test(ctx):
    env = unittest.begin(ctx)
    result = resolve_extra_paths(["."], ["_main"])
    asserts.equals(env, ["."], result)
    return unittest.end(env)

exec_root_main_test = unittest.make(_exec_root_main_test)

def _exec_root_main_subpath_test(ctx):
    env = unittest.begin(ctx)
    result = resolve_extra_paths(["."], ["_main/compiler"])
    asserts.equals(env, [".", "compiler"], result)
    return unittest.end(env)

exec_root_main_subpath_test = unittest.make(_exec_root_main_subpath_test)

def _exec_root_external_test(ctx):
    env = unittest.begin(ctx)
    result = resolve_extra_paths(["."], ["some_repo/site-packages"])
    asserts.equals(env, [".", "external/some_repo/site-packages"], result)
    return unittest.end(env)

exec_root_external_test = unittest.make(_exec_root_external_test)

def _bin_root_main_test(ctx):
    env = unittest.begin(ctx)
    result = resolve_extra_paths(["bazel-out/k8-fastbuild/bin"], ["_main"])
    asserts.equals(env, [".", "bazel-out/k8-fastbuild/bin"], result)
    return unittest.end(env)

bin_root_main_test = unittest.make(_bin_root_main_test)

def _bin_root_main_subpath_test(ctx):
    env = unittest.begin(ctx)
    result = resolve_extra_paths(["bazel-out/k8-fastbuild/bin"], ["_main/compiler"])
    asserts.equals(env, [".", "bazel-out/k8-fastbuild/bin/compiler"], result)
    return unittest.end(env)

bin_root_main_subpath_test = unittest.make(_bin_root_main_subpath_test)

def _bin_root_external_test(ctx):
    env = unittest.begin(ctx)
    result = resolve_extra_paths(
        ["bazel-out/k8-fastbuild/bin"],
        ["pypi_lark/install/lib/python3.12/site-packages"],
    )
    asserts.equals(env, [
        ".",
        "bazel-out/k8-fastbuild/bin/external/pypi_lark/install/lib/python3.12/site-packages",
    ], result)
    return unittest.end(env)

bin_root_external_test = unittest.make(_bin_root_external_test)

def _multiple_roots_and_imports_test(ctx):
    env = unittest.begin(ctx)
    result = resolve_extra_paths(
        [".", "bazel-out/k8-fastbuild/bin"],
        ["_main", "_main/compiler", "pypi_lark"],
    )
    asserts.equals(env, [
        ".",
        "compiler",
        "external/pypi_lark",
        "bazel-out/k8-fastbuild/bin",
        "bazel-out/k8-fastbuild/bin/compiler",
        "bazel-out/k8-fastbuild/bin/external/pypi_lark",
    ], result)
    return unittest.end(env)

multiple_roots_and_imports_test = unittest.make(_multiple_roots_and_imports_test)

def _deduplication_test(ctx):
    env = unittest.begin(ctx)
    result = resolve_extra_paths([".", "."], ["_main"])
    asserts.equals(env, ["."], result)
    return unittest.end(env)

deduplication_test = unittest.make(_deduplication_test)

def _empty_imports_test(ctx):
    env = unittest.begin(ctx)
    result = resolve_extra_paths(["."], [])
    asserts.equals(env, ["."], result)
    return unittest.end(env)

empty_imports_test = unittest.make(_empty_imports_test)

def _dot_always_present_test(ctx):
    env = unittest.begin(ctx)
    result = resolve_extra_paths(["bazel-out/k8-fastbuild/bin"], ["_main/x"])
    asserts.true(env, "." in result)
    return unittest.end(env)

dot_always_present_test = unittest.make(_dot_always_present_test)

def pyright_test_suite(name):
    unittest.suite(
        name,
        exec_root_main_test,
        exec_root_main_subpath_test,
        exec_root_external_test,
        bin_root_main_test,
        bin_root_main_subpath_test,
        bin_root_external_test,
        multiple_roots_and_imports_test,
        deduplication_test,
        empty_imports_test,
        dot_always_present_test,
    )
