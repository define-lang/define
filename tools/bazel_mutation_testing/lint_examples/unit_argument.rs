// Rejected: unused_variables, clippy::unit_arg
// Rejected in mutation runs: nothing
//! A function whose body became `Ok(Default::default())`, which passes `()`.

use std::fmt;

#[derive(Debug)]
pub struct Name;

impl fmt::Display for Name {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        Ok(Default::default())
    }
}
