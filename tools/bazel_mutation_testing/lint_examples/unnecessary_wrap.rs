// Rejected: unused_variables, clippy::missing_const_for_fn, clippy::unnecessary_wraps
// Rejected in mutation runs: nothing
//! A helper whose body became `Some` of a constant, which always returns
//! `Some`.

#[must_use]
pub fn first_word_length(text: &str) -> usize {
    first_word(text).map_or(0, str::len)
}

fn first_word(text: &str) -> Option<&str> {
    Some("")
}
