from __future__ import annotations

import json

from tools.bazel_mutation_testing.python import sources

_PYTEST_MAIN = "@rules_py//py/private:pytest_main.py"


def _rule(
    name: str, rule_class: str, srcs: list[str], **attributes: str | bool | list[str]
) -> str:
    testonly = attributes.get("testonly", False)
    return json.dumps(
        {
            "type": "RULE",
            "rule": {
                "name": name,
                "ruleClass": rule_class,
                "attribute": [
                    {
                        "name": "main",
                        "type": "LABEL",
                        "stringValue": attributes.get("main", ""),
                    },
                    {"name": "srcs", "type": "LABEL_LIST", "stringListValue": srcs},
                    {
                        "name": "tags",
                        "type": "STRING_LIST",
                        "stringListValue": attributes.get("tags", []),
                    },
                    {"name": "testonly", "type": "BOOLEAN", "booleanValue": testonly},
                ],
            },
        }
    )


def _sources(*rules: str) -> sources.Sources:
    return sources.from_query("".join(rule + "\n" for rule in rules))


def test_sources_of_libraries_and_binaries():
    found = _sources(
        _rule(
            "//define/compiler:ast",
            "py_library",
            srcs=["//define/compiler:ast.py", "//define/compiler:ast.pyi"],
        ),
        _rule("//tools:tool", "py_venv_exec", srcs=["//tools:tool.py"]),
        _rule(
            "//define/compiler:fixtures",
            "py_library",
            srcs=["//define/compiler:fixtures.py"],
            testonly=True,
        ),
        _rule("//:generated", "py_library", srcs=["@pypi//external:module.py"]),
        _rule(
            "//define/generators:generate",
            "py_venv_exec",
            srcs=["//define/generators:generate.py"],
            tags=["no-mutation"],
        ),
    )
    assert found == sources.Sources(
        paths=["define/compiler/ast.py", "tools/tool.py"], tests=[]
    )


def test_pytest_tests_that_a_run_tests_with():
    found = _sources(
        _rule(
            "//define/compiler:ast_test",
            "py_venv_exec_test",
            srcs=["//define/compiler:ast_test.py", "//define/compiler:helpers.py"],
            main=_PYTEST_MAIN,
            testonly=True,
        ),
        _rule(
            "//define/compiler:slow_test",
            "py_venv_exec_test",
            srcs=["//define/compiler:slow_test.py"],
            main=_PYTEST_MAIN,
            testonly=True,
            tags=["no-coverage"],
        ),
        _rule(
            "//define/compiler:manual_test",
            "py_venv_exec_test",
            srcs=["//define/compiler:manual_test.py"],
            main=_PYTEST_MAIN,
            testonly=True,
            tags=["manual"],
        ),
        _rule(
            "//define/testdata/codegen:generator_integration_tests_values",
            "py_venv_exec_test",
            srcs=[],
            main=_PYTEST_MAIN,
            testonly=True,
        ),
        _rule(
            "//define/compiler:pyright_test",
            "py_venv_exec_test",
            srcs=["//tools/bzl:pyright_test_runner.py"],
            main="//tools/bzl:pyright_test_runner.py",
            testonly=True,
            tags=["pyright"],
        ),
    )
    assert found == sources.Sources(
        paths=[],
        tests=[
            sources.PytestTest(
                label="//define/compiler:ast_test",
                source="define/compiler/ast_test.py",
            )
        ],
    )
