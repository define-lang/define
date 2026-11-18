// Rejected: unused_variables, clippy::missing_const_for_fn
// Rejected in mutation runs: nothing
//! A function whose body became a constant, which leaves its parameters unused
//! and lets it be `const`.

#[must_use]
pub fn is_larger(left: u32, right: u32) -> bool {
    true
}
