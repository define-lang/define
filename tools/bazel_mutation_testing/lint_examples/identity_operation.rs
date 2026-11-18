// Rejected: clippy::identity_op
// Rejected in mutation runs: nothing
//! An operator replaced so that it does nothing, such as `- 1` becoming `* 1`.

#[must_use]
pub const fn last_index(length: usize) -> usize {
    length * 1
}
