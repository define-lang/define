"""Macro for code generator integration tests."""

load("//tools/bzl:py_test.bzl", "py_test")

def generator_integration_tests(
        name,
        test_module,
        testdata_packages,
        deps,
        visibility = None):
    """Creates one generator integration test for each codegen testdata package."""
    tests = []
    for testdata_package in testdata_packages:
        category = testdata_package
        test_name = "%s_%s" % (name, category)
        py_test(
            name = test_name,
            size = "small",
            args = [test_module],
            data = ["//define/testdata/codegen/%s:codegen_testdata" % category],
            env = {
                "DEFINE_CODEGEN_TESTDATA_CATEGORY": category,
            },
            deps = deps,
        )
        tests.append(":" + test_name)

    native.test_suite(
        name = name,
        tests = tests,
        visibility = visibility,
    )
