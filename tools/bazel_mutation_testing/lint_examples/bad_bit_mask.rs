// Rejected: clippy::bad_bit_mask
// Rejected in mutation runs: nothing
//! A bit mask changed so that the comparison never holds, which is the bug
//! itself.

#[must_use]
pub const fn is_even(value: u32) -> bool {
    value | 1 == 0
}
