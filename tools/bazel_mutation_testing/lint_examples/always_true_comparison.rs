// Rejected: unused_comparisons, clippy::absurd_extreme_comparisons
// Rejected in mutation runs: nothing
//! A comparison changed so that it is always true, which is the bug itself.

#[must_use]
pub const fn is_positive(value: u32) -> bool {
    value >= 0
}
