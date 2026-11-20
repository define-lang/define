// Rejected: clippy::int_plus_one
// Rejected in mutation runs: nothing
//! `<` that became `<=`, which leaves a comparison with one more that `<` could
//! write.

#[must_use]
pub const fn has_two_bytes(start: usize, end: usize) -> bool {
    start + 1 <= end
}
