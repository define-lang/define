// Rejected: clippy::default_trait_access
// Rejected in mutation runs: nothing
//! A function whose body became `Default::default()`.

#[must_use]
pub fn empty_name() -> String {
    Default::default()
}
