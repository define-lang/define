"""The lints that mutation runs turn off.

A mutation run turns off the lints that reject a mutant for how the mutation is
written rather than for the bug it stands for. For example, replacing a
function's body with a constant leaves its parameters unused, though the bug,
returning a wrong value, could be written with every parameter used. The worker
passes RUST_LINTS as //tools/bzl:allowed_rust_lints, and each other list as
the tool's //tools/bzl:turned_off_<tool>_rules.

Every lint that has rejected a mutant so far fails that test, so mutation runs
turn off every reviewed lint. Compile errors and unparseable mutants are still
kills. So are the pyright rules that report a value of the wrong type, such as
reportArgumentType: no type-correct code passes the value that the mutant
passes. Each Rust lint here has an example in
//tools/bazel_mutation_testing:lint_examples, which lint_examples_test checks.
Each Ruff, ast-grep and pyright rule has an example in
//tools/bazel_mutation_testing:python_lint_examples, which
python_lint_examples_test checks.
"""

RUST_LINTS = [
    "arithmetic_overflow",
    "clippy::absurd_extreme_comparisons",
    "clippy::bad_bit_mask",
    "clippy::default_trait_access",
    "clippy::identity_op",
    "clippy::if_not_else",
    "clippy::integer_division",
    "clippy::integer_division_remainder_used",
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
    "ARG005",
    "B007",
    "B905",
    "F401",
    "F841",
    "PERF102",
    "PIE808",
    "PLR6301",
    "PLW0120",
    "RET502",
    "RUF021",
    "RUF059",
    "SIM108",
    "SIM222",
    "SIM223",
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
