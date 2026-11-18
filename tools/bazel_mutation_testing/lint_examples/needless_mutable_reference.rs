// Rejected: unused_variables, clippy::missing_const_for_fn, clippy::needless_pass_by_ref_mut, clippy::ptr_arg
// Rejected in mutation runs: nothing
//! A helper whose body became a constant, which no longer changes what its
//! mutable reference points to.

#[must_use]
pub fn escaped(text: &str) -> String {
    let mut output = String::new();
    push_escaped(&mut output, text);
    output
}

fn push_escaped(output: &mut String, text: &str) -> usize {
    0
}
