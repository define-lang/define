"""The lints that mutation runs turn off.

A mutation run turns off a lint when a developer could write the same wrong
behavior in a form the lint accepts, such as a parameter left unused after a
function's body became a constant. The worker passes RUST_LINTS as
//tools/bzl:allowed_rust_lints, and each other list as the tool's
//tools/bzl:turned_off_<tool>_rules.

Each lint here, and each lint whose kills were reviewed and kept, has an example
in //tools/bazel_mutation_testing:lint_examples or :python_lint_examples, which
their tests check.
"""

RUST_LINTS = [
    "arithmetic_overflow",
    "clippy::absurd_extreme_comparisons",
    "clippy::bad_bit_mask",
    "clippy::default_trait_access",
    "clippy::identity_op",
    "clippy::if_not_else",
    "clippy::int_plus_one",
    "clippy::integer_division",
    "clippy::integer_division_remainder_used",
    "clippy::manual_let_else",
    "clippy::match_same_arms",
    "clippy::match_single_binding",
    "clippy::missing_const_for_fn",
    "clippy::needless_pass_by_ref_mut",
    "clippy::needless_pass_by_value",
    "clippy::ptr_arg",
    "clippy::semicolon_if_nothing_returned",
    "clippy::single_match_else",
    "clippy::unit_arg",
    "clippy::unnecessary_literal_bound",
    "clippy::unnecessary_wraps",
    "clippy::unused_self",
    "clippy::unused_unit",
    "dead_code",
    "unfulfilled_lint_expectations",
    "unused_comparisons",
    "unused_crate_dependencies",
    "unused_imports",
    "unused_mut",
    "unused_variables",
]

RUFF_RULES = [
    "ARG001",
    "ARG002",
    "ARG004",
    "ARG005",
    "B007",
    "B905",
    "F401",
    "F841",
    "FURB148",
    "PERF102",
    "PIE808",
    "PLR6301",
    "PLW0120",
    "PLW1510",
    "RET502",
    "RUF021",
    "RUF059",
    "RUF100",
    "SIM108",
    "SIM222",
    "SIM223",
    "SIM910",
    "TC001",
    "TC003",
    "TC006",
]

AST_GREP_RULES = [
    "concrete-sequence-parameter-only-read",
]

PYRIGHT_RULES = [
    "reportMatchNotExhaustive",
    "reportUnnecessaryComparison",
    "reportUnnecessaryContains",
    "reportUnnecessaryIsInstance",
    "reportUnreachable",
    "reportUnusedFunction",
    "reportUnusedImport",
    "reportUnusedParameter",
    "reportUnusedVariable",
]
