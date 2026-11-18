// Rejected: dead_code, clippy::missing_const_for_fn, clippy::unnecessary_literal_bound
// Rejected in mutation runs: nothing
//! A method whose body became `""`, which could return `&'static str`.

#[derive(Debug)]
pub struct Text {
    value: String,
}

impl Text {
    #[must_use]
    pub fn as_str(&self) -> &str {
        ""
    }
}
