from __future__ import annotations

import json

import pytest

from tools.bazel_mutation_testing.rust import crates


def _rule(name: str, rule_class: str, **attributes: str | list[str]) -> str:
    attribute_list: list[dict[str, object]] = [
        {"name": "crate", "type": "LABEL"},
        {"name": "crate_name", "type": "STRING", "stringValue": ""},
        {"name": "crate_root", "type": "LABEL"},
        {"name": "srcs", "type": "LABEL_LIST"},
        {"name": "tags", "type": "STRING_LIST"},
    ]
    for attribute in attribute_list:
        value = attributes.get(str(attribute["name"]))
        if isinstance(value, list):
            attribute["stringListValue"] = value
        elif value is not None:
            attribute["stringValue"] = value
    return json.dumps(
        {
            "type": "RULE",
            "rule": {
                "name": name,
                "ruleClass": rule_class,
                "attribute": attribute_list,
            },
        }
    )


def _crates(*rules: str) -> list[crates.Crate]:
    return crates.from_query("".join(rule + "\n" for rule in rules))


def test_library_with_crate_root_and_crate_name():
    found = _crates(
        _rule(
            "//defcl/rust/parser:parser",
            "rust_library",
            crate_name="defcl_parser",
            crate_root="//defcl/rust/parser:lib.rs",
            srcs=["//defcl/rust/parser:lib.rs", "//defcl/rust/parser:parser.rs"],
        )
    )
    assert found == [
        crates.Crate(
            label="//defcl/rust/parser:parser",
            name="defcl_parser",
            root="defcl/rust/parser/lib.rs",
            tests=(),
        )
    ]


def test_tests_that_compile_a_crate_and_run():
    found = _crates(
        _rule(
            "//crates/scanning:scanning",
            "rust_library",
            srcs=["//crates/scanning:lib.rs"],
        ),
        _rule(
            "//crates/scanning:scanning_test",
            "rust_test",
            crate="//crates/scanning:scanning",
        ),
        _rule(
            "//crates/scanning:manual_test",
            "rust_test",
            crate="//crates/scanning:scanning",
            tags=["manual"],
        ),
        _rule(
            "//crates/scanning:no_coverage_test",
            "rust_test",
            crate="//crates/scanning:scanning",
            tags=["no-coverage"],
        ),
        _rule(
            "//crates/scanning:integration_test",
            "rust_test",
            srcs=["//crates/scanning:integration_test.rs"],
        ),
    )
    assert found == [
        crates.Crate(
            label="//crates/scanning:scanning",
            name="scanning",
            root="crates/scanning/lib.rs",
            tests=("//crates/scanning:scanning_test",),
        )
    ]


def test_default_crate_names_and_roots():
    found = _crates(
        _rule(
            "//tools/generate:generate-errors",
            "rust_binary",
            srcs=["//tools/generate:errors.rs", "//tools/generate:main.rs"],
        ),
        _rule(
            "//crates/extension:extension_shared",
            "rust_cdylib_library",
            srcs=["//crates/extension:lib.rs", "//crates/extension:module.rs"],
        ),
        _rule("//:root_crate", "rust_library", srcs=["//:root.rs"]),
    )
    assert [(crate.name, crate.root) for crate in found] == [
        ("generate_errors", "tools/generate/main.rs"),
        ("extension_shared", "crates/extension/lib.rs"),
        ("root_crate", "root.rs"),
    ]


def test_crate_without_root():
    with pytest.raises(ValueError, match="//crates/example:example has no crate root"):
        _ = _crates(
            _rule(
                "//crates/example:example",
                "rust_library",
                srcs=["//crates/example:first.rs", "//crates/example:second.rs"],
            )
        )
