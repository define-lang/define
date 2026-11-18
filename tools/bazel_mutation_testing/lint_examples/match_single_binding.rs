// Rejected: clippy::match_single_binding
// Rejected in mutation runs: nothing
//! Match arms deleted, which leaves a match with one arm that binds.

#[must_use]
pub const fn kind_index(kind: u8) -> u8 {
    match kind {
        other => other,
    }
}
