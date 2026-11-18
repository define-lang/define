// Rejected: clippy::match_same_arms
// Rejected in mutation runs: nothing
//! A match arm changed to give what another arm gives.

#[must_use]
pub const fn sign(value: i32) -> i32 {
    match value {
        0 => 0,
        1.. => 1,
        _ => 1,
    }
}
