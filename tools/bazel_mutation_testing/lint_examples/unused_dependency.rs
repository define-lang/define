// Rejected: unused_variables, unused_crate_dependencies, clippy::missing_const_for_fn
// Rejected in mutation runs: nothing
// Flags: --extern=dependency
//! A function whose body became a constant, which leaves a dependency that only
//! the body used.

#[must_use]
pub fn token_count(text: &str) -> usize {
    0
}
