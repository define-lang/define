// Rejected: unused_imports, unused_variables, clippy::missing_const_for_fn
// Rejected in mutation runs: nothing
//! A function whose body became a constant, which leaves an import that only
//! the body used.

use std::collections::BTreeSet;

#[must_use]
pub fn distinct_count(values: &[u32]) -> usize {
    0
}
