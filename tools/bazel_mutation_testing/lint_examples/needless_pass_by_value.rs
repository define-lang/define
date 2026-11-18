// Rejected: unused_variables, clippy::needless_pass_by_value
// Rejected in mutation runs: nothing
//! A helper whose body became a constant, which no longer consumes a parameter
//! it takes by value.

#[must_use]
pub fn rendered(errors: Vec<String>) -> usize {
    render(errors).len()
}

fn render(errors: Vec<String>) -> String {
    String::new()
}
