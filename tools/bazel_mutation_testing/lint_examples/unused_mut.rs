// Rejected: unused_mut, unused_variables
// Rejected in mutation runs: nothing
//! A function whose body became a constant, which no longer changes a
//! parameter that it declares `mut`.

#[must_use]
pub fn with_entry(mut entries: Vec<u32>, entry: u32) -> Vec<u32> {
    Vec::new()
}
