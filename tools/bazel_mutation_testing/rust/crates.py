"""Find the Rust crates in an area."""

from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec

from tools.bazel_mutation_testing import bazel

if TYPE_CHECKING:
    import pathlib
    from collections.abc import Iterable

# The rules that compile a crate from its own sources. A rust_test with a
# `crate` compiles that crate's sources again, with its tests.
_CRATE_RULES = frozenset({"rust_binary", "rust_cdylib_library", "rust_library"})
# `bazel test` skips manual tests that a pattern matches, and a run skips the
# no-coverage tests.
_SKIPPED_TEST_TAGS = frozenset({"manual", "no-coverage"})


class Crate(msgspec.Struct, frozen=True):
    """A Rust crate whose sources the tester mutates."""

    label: str
    name: str
    root: str
    """The workspace-relative path of the crate root."""
    tests: tuple[str, ...]
    """The rust_test targets that compile the crate's sources and that a run
    tests with."""


class _Attribute(msgspec.Struct, frozen=True, rename="camel"):
    name: str
    string_value: str = ""
    string_list_value: list[str] = msgspec.field(default_factory=list)


class _Rule(msgspec.Struct, frozen=True, rename="camel"):
    name: str
    rule_class: str
    attribute: list[_Attribute]

    def value(self, name: str) -> _Attribute:
        for attribute in self.attribute:
            if attribute.name == name:
                return attribute
        raise KeyError(name)


class _Target(msgspec.Struct, frozen=True):
    rule: _Rule


def _source_path(label: str) -> str:
    package, name = label.removeprefix("//").split(":", 1)
    return f"{package}/{name}" if package else name


def _crate_root(rule: _Rule) -> str:
    root_label = rule.value("crate_root").string_value
    if root_label:
        return _source_path(root_label)
    sources = rule.value("srcs").string_list_value
    if len(sources) == 1:
        return _source_path(sources[0])
    # rules_rust's default crate root for a crate with several sources.
    default_name = "main.rs" if rule.rule_class == "rust_binary" else "lib.rs"
    for source in sources:
        if source.endswith(f":{default_name}"):
            return _source_path(source)
    raise ValueError(f"{rule.name} has no crate root")


def find(workspace: pathlib.Path, patterns: list[str]) -> list[Crate]:
    """Return the crates that the target patterns `patterns` match.

    Unlike `bazel test`, this includes targets tagged `manual`, since Bazel
    builds each PyO3 extension's crate only through a manual target.
    """
    return from_query(
        bazel.run_checked(
            workspace,
            [
                "query",
                "--output=streamed_jsonproto",
                'kind("^rust_(binary|cdylib_library|library|test) rule$", '
                + f"{query_expression(patterns)})",
            ],
        )
    )


def query_expression(patterns: Iterable[str]) -> str:
    """Return the query expression for target patterns.

    As in `bazel test`, a pattern that starts with `-` removes its targets.
    """
    expression = ""
    for pattern in patterns:
        if pattern.startswith("-"):
            expression += f" - {pattern.removeprefix('-')}"
        elif expression:
            expression += f" + {pattern}"
        else:
            expression = pattern
    return expression


def from_query(output: str) -> list[Crate]:
    """Return the crates in a query's `streamed_jsonproto` output.

    The query names crates and the rust_test targets that compile them.
    """
    decoder = msgspec.json.Decoder(_Target)
    crate_rules: list[_Rule] = []
    test_labels: dict[str, list[str]] = {}
    for line in output.splitlines():
        rule = decoder.decode(line).rule
        if rule.rule_class in _CRATE_RULES:
            crate_rules.append(rule)
            continue
        crate_label = rule.value("crate").string_value
        if crate_label and _SKIPPED_TEST_TAGS.isdisjoint(
            rule.value("tags").string_list_value
        ):
            test_labels.setdefault(crate_label, []).append(rule.name)

    crates: list[Crate] = []
    for rule in crate_rules:
        name = rule.value("crate_name").string_value or rule.name.split(":", 1)[
            1
        ].replace("-", "_")
        crates.append(
            Crate(
                label=rule.name,
                name=name,
                root=_crate_root(rule),
                tests=tuple(test_labels.get(rule.name, [])),
            )
        )
    return crates
