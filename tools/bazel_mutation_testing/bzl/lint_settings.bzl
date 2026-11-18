"""The lints that mutation runs turn off.

A mutation run turns off the lints that reject a mutant for how the mutation is
written rather than for the bug it stands for. For example, replacing a
function's body with a constant leaves its parameters unused, though the bug,
returning a wrong value, could be written with every parameter used. The worker
passes TURNED_OFF as //tools/bzl:allowed_rust_lints.

Every lint that has rejected a mutant so far fails that test, so mutation runs
turn off every reviewed lint. Compile errors and unparseable mutants are still
kills. Each lint here has an example in //tools/bazel_mutation_testing:lint_examples,
which lint_examples_test checks.
"""

TURNED_OFF = [
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
