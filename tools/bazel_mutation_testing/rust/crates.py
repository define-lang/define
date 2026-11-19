"""Find the Rust crates in an area."""

from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec

from tools.bazel_mutation_testing import bazel

if TYPE_CHECKING:
    import pathlib

# The rules that compile a crate from its own sources. A rust_test with a
# `crate` compiles that crate's sources again, with its tests.
_CRATE_RULES = frozenset({"rust_binary", "rust_cdylib_library", "rust_library"})
# A mutation run never runs tests with these tags. `bazel test` leaves out
# manual tests when a wildcard pattern matches them, and each run passes
# --test_tag_filters=-no-coverage.
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


def _crate_root(rule: bazel.Rule) -> str:
    root_label = rule.value("crate_root").string_value
    if root_label:
        return bazel.source_path(root_label)
    sources = rule.value("srcs").string_list_value
    if len(sources) == 1:
        return bazel.source_path(sources[0])
    # rules_rust's default crate root for a crate with several sources.
    default_name = "main.rs" if rule.rule_class == "rust_binary" else "lib.rs"
    for source in sources:
        if source.endswith(f":{default_name}"):
            return bazel.source_path(source)
    raise ValueError(f"{rule.name} has no crate root")


def find(workspace: pathlib.Path, patterns: list[str]) -> list[Crate]:
    """Return the crates that the target patterns `patterns` match.

    Unlike `bazel test`, this includes targets tagged `manual`, since Bazel
    builds each PyO3 extension's crate only through a manual target. As in
    `bazel test`, the tests include the tests of the test suites that the
    patterns match.
    """
    expression = bazel.query_expression(patterns)
    return from_query(
        bazel.run_checked(
            workspace,
            [
                "query",
                "--output=streamed_jsonproto",
                f'kind("^rust_(binary|cdylib_library|library) rule$", {expression}) + '
                + f'kind("^rust_test rule$", tests({expression}))',
            ],
        )
    )


def from_query(output: str) -> list[Crate]:
    """Return the crates in a query's `streamed_jsonproto` output.

    The query names crates and the rust_test targets that compile them.
    """
    crate_rules: list[bazel.Rule] = []
    test_labels: dict[str, list[str]] = {}
    for rule in bazel.rules(output):
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
