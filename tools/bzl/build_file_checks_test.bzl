"""Unit tests for build_file_checks.bzl."""

load("@bazel_skylib//lib:partial.bzl", "partial")
load("@bazel_skylib//lib:unittest.bzl", "asserts", "unittest")
load(":build_file_checks.bzl", "build_file_violations")

def _macro_rules(function, name, kind, attributes, helpers = []):
    rules = [
        (helper, {"generator_function": function, "generator_name": name, "kind": "filegroup"})
        for helper in helpers
    ]
    main = {"generator_function": function, "generator_name": name, "kind": kind}
    main.update(attributes)
    rules.append((name, main))
    return rules

def _py_test(name, size = "small", tags = [], source = None):
    return _macro_rules(
        "py_test",
        name,
        "py_venv_exec_test",
        {"size": size, "srcs": (":%s.py" % (source or name),), "tags": tags},
        helpers = [name + ".pytest_paths", "_%s.venv" % name],
    )

def _py_library(name, source):
    return [(name, {"kind": "py_library", "srcs": (":" + source,)})]

def _format_test():
    return _macro_rules(
        "format_test",
        "format_test",
        "test_suite",
        {},
        helpers = ["format_test_srcs", "format_test_Python_with_ruff"],
    )

def _pyright_test(deps):
    return [
        ("pyright_test_deps", {
            "deps": tuple(deps),
            "generator_function": "pyright_test",
            "generator_name": "pyright_test",
            "kind": "_pyright_deps",
        }),
        ("pyright_test", {
            "generator_function": "pyright_test",
            "generator_name": "pyright_test",
            "kind": "py_venv_exec_test",
            "size": "medium",
        }),
    ]

def _test_targets_must_be_small_impl(ctx):
    env = unittest.begin(ctx)
    rules = (
        _py_test("large_test", size = "large") +
        _py_test("manual_test", size = "medium", tags = ["manual"]) +
        [("missing_test", {"kind": "sh_test", "srcs": (":missing_test.sh",)})] +
        _py_test("small_test") +
        _format_test()
    )
    asserts.equals(env, [
        'test target "large_test" must set size = "small"',
        'test target "missing_test" must set size = "small"',
    ], build_file_violations("tools", rules))
    return unittest.end(env)

_test_targets_must_be_small_test = unittest.make(_test_targets_must_be_small_impl)

def _python_targets_are_named_after_their_source_impl(ctx):
    env = unittest.begin(ctx)
    rules = (
        _py_library("generated", "generated.py") +
        _py_library("parser", "parser.py") +
        _py_test("parser_tests", source = "parser_test") +
        _py_library("stubs", "stubs.pyi") +
        _py_library("tools", "__init__.py")
    )
    asserts.equals(env, [
        'py_test "parser_tests" must be named "parser_test"',
    ], build_file_violations("tools", rules))
    return unittest.end(env)

_python_targets_are_named_after_their_source_test = unittest.make(
    _python_targets_are_named_after_their_source_impl,
)

def _package_init_target_is_named_after_its_directory_impl(ctx):
    env = unittest.begin(ctx)
    asserts.equals(env, [
        'py_library "schema_package" must be named "schema"',
    ], build_file_violations("schema", _py_library("schema_package", "__init__.py")))
    return unittest.end(env)

_package_init_target_is_named_after_its_directory_test = unittest.make(
    _package_init_target_is_named_after_its_directory_impl,
)

def _package_init_target_takes_py_suffix_when_directory_name_is_taken_impl(ctx):
    env = unittest.begin(ctx)
    rules = [("core", {"embed": (":boolean_go_proto",), "kind": "go_library"})] + _py_library("core_py", "__init__.py")
    asserts.equals(env, [], build_file_violations("core", rules))
    return unittest.end(env)

_package_init_target_takes_py_suffix_when_directory_name_is_taken_test = unittest.make(
    _package_init_target_takes_py_suffix_when_directory_name_is_taken_impl,
)

def _proto_targets_are_named_after_their_source_impl(ctx):
    env = unittest.begin(ctx)
    rules = [
        ("integers", {"kind": "proto_library", "srcs": (":integers.proto",)}),
        ("integers_py", {"deps": (":integers",), "kind": "py_proto_library"}),
        ("strings_proto", {"kind": "proto_library", "srcs": (":strings.proto",)}),
        ("strings_proto_py", {"deps": (":strings_proto",), "kind": "py_proto_library"}),
    ]
    asserts.equals(env, [
        'proto_library "integers" must be named "integers_proto"',
    ], build_file_violations("schemas", rules))
    return unittest.end(env)

_proto_targets_are_named_after_their_source_test = unittest.make(
    _proto_targets_are_named_after_their_source_impl,
)

def _go_targets_are_named_after_their_directory_impl(ctx):
    env = unittest.begin(ctx)
    rules = (
        _macro_rules("go_binary_macro", "buf", "go_binary", {"embed": (":main",)}) +
        [
            ("main", {"kind": "go_library", "srcs": (":main.go",)}),
            ("main_test", {"kind": "go_test", "size": "small", "srcs": (":main_test.go",)}),
        ]
    )
    asserts.equals(env, [
        'go_library "main" must be named "buf_lib"',
        'go_test "main_test" must be named "buf_test"',
    ], build_file_violations("buf", rules))
    return unittest.end(env)

_go_targets_are_named_after_their_directory_test = unittest.make(
    _go_targets_are_named_after_their_directory_impl,
)

def _targets_must_be_in_alphabetical_order_impl(ctx):
    env = unittest.begin(ctx)
    rules = (
        _py_library("parser", "parser.py") +
        _py_library("ast", "ast.py") +
        _py_test("parser_test")
    )
    asserts.equals(env, [
        '"ast" must come before "parser"',
    ], build_file_violations("tools", rules))
    return unittest.end(env)

_targets_must_be_in_alphabetical_order_test = unittest.make(
    _targets_must_be_in_alphabetical_order_impl,
)

def _order_ignores_meta_targets_impl(ctx):
    env = unittest.begin(ctx)
    rules = (
        _macro_rules("format_multirun", "format", "multirun", {}) +
        _py_library("ast", "ast.py") +
        _py_library("parser", "parser.py") +
        _format_test() +
        _pyright_test([":ast", "//tools:parser"])
    )
    asserts.equals(env, [], build_file_violations("tools", rules))
    return unittest.end(env)

_order_ignores_meta_targets_test = unittest.make(_order_ignores_meta_targets_impl)

def _language_proto_targets_follow_their_proto_library_impl(ctx):
    env = unittest.begin(ctx)
    rules = [
        ("boolean_proto", {"kind": "proto_library", "srcs": (":boolean.proto",)}),
        ("boolean_go_proto", {"kind": "go_proto_library", "proto": ":boolean_proto"}),
        ("integers_proto", {"kind": "proto_library", "srcs": (":integers.proto",)}),
        ("integers_proto_py", {"deps": (":integers_proto",), "kind": "py_proto_library"}),
        ("integers_value_proto", {"kind": "proto_library", "srcs": (":integers_value.proto",)}),
    ]
    asserts.equals(env, [], build_file_violations("schemas", rules))
    return unittest.end(env)

_language_proto_targets_follow_their_proto_library_test = unittest.make(
    _language_proto_targets_follow_their_proto_library_impl,
)

def _python_targets_must_be_in_pyright_test_impl(ctx):
    env = unittest.begin(ctx)
    rules = (
        _py_library("ast", "ast.py") +
        _py_library("parser", "parser.py") +
        _pyright_test([":ast"])
    )
    asserts.equals(env, [
        'Python target "parser" must be in the deps of pyright_test "pyright_test"',
    ], build_file_violations("tools", rules))
    return unittest.end(env)

_python_targets_must_be_in_pyright_test_test = unittest.make(
    _python_targets_must_be_in_pyright_test_impl,
)

def _package_without_pyright_test_is_not_checked_for_coverage_impl(ctx):
    env = unittest.begin(ctx)
    asserts.equals(env, [], build_file_violations("child", _py_library("child", "__init__.py")))
    return unittest.end(env)

_package_without_pyright_test_is_not_checked_for_coverage_test = unittest.make(
    _package_without_pyright_test_is_not_checked_for_coverage_impl,
)

def _codegen_testdata(name):
    return [(name, {"kind": "filegroup"})]

def _codegen_testdata_requires_pyright_test_impl(ctx):
    env = unittest.begin(ctx)
    asserts.equals(env, [
        "codegen testdata packages must declare a pyright_test for their generated Python",
    ], build_file_violations("move_particle", _codegen_testdata("codegen_testdata")))
    asserts.equals(env, [
        "codegen testdata packages must declare a pyright_test for their generated Python",
    ], build_file_violations("generator", _codegen_testdata("tracing_testdata")))
    asserts.equals(env, [], build_file_violations(
        "move_particle",
        _codegen_testdata("codegen_testdata") + _pyright_test([]),
    ))
    return unittest.end(env)

_codegen_testdata_requires_pyright_test_test = unittest.make(
    _codegen_testdata_requires_pyright_test_impl,
)

def build_file_checks_test_suite(name):
    """Creates the unit tests for build_file_checks.bzl.

    Args:
        name: Name of the test suite.
    """
    unittest.suite(
        name,
        *[
            partial.make(test, size = "small")
            for test in [
                _test_targets_must_be_small_test,
                _python_targets_are_named_after_their_source_test,
                _package_init_target_is_named_after_its_directory_test,
                _package_init_target_takes_py_suffix_when_directory_name_is_taken_test,
                _proto_targets_are_named_after_their_source_test,
                _go_targets_are_named_after_their_directory_test,
                _targets_must_be_in_alphabetical_order_test,
                _order_ignores_meta_targets_test,
                _language_proto_targets_follow_their_proto_library_test,
                _python_targets_must_be_in_pyright_test_test,
                _package_without_pyright_test_is_not_checked_for_coverage_test,
                _codegen_testdata_requires_pyright_test_test,
            ]
        ]
    )
