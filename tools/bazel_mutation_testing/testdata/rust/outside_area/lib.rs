//! A function that only a test outside the area checks.

#[must_use]
pub const fn is_larger(left: u32, right: u32) -> bool {
    left > right
}
