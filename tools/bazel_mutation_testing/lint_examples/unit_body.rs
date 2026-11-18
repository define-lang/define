// Rejected: unused_variables, clippy::missing_const_for_fn, clippy::ptr_arg, clippy::semicolon_if_nothing_returned, clippy::unused_unit
// Rejected in mutation runs: nothing
//! A function whose body became `()`.

pub fn record(values: &mut Vec<u32>, value: u32) {
    ()
}
