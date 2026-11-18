// Rejected: clippy::integer_division, clippy::integer_division_remainder_used
// Rejected in mutation runs: nothing
//! An operator replaced with `/`, which the repository writes otherwise.

#[must_use]
pub const fn scaled(value: u32, factor: u32) -> u32 {
    value / factor
}
