// Rejected: clippy::manual_let_else
// Rejected in mutation runs: nothing
//! A match arm deleted, which leaves a match that `let ... else` could write.

#[must_use]
pub fn first_digit(text: &str) -> Option<u32> {
    let character = match text.chars().next() {
        Some(character) => character,
        _ => return None,
    };
    character.to_digit(10)
}
