// Rejected: unused_variables, unfulfilled_lint_expectations
// Rejected in mutation runs: nothing
//! A function whose body became a constant, which no longer does what an
//! `#[expect]` expected.

#[must_use]
#[expect(clippy::cast_possible_truncation, reason = "values fit in a u8")]
pub const fn low_byte(value: u32) -> u8 {
    0
}
