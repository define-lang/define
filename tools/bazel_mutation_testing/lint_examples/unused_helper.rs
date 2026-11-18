// Rejected: dead_code, unused_variables, clippy::missing_const_for_fn
// Rejected in mutation runs: nothing
//! A function whose body became a constant, which leaves a helper that only it
//! called.

#[must_use]
pub fn doubled_first(values: &[u32]) -> u32 {
    0
}

const fn doubled(value: u32) -> u32 {
    value.wrapping_mul(2)
}
