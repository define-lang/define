// Rejected: clippy::if_not_else
// Rejected in mutation runs: nothing
//! A comparison in an `if` with an `else` changed from `==` to `!=`.

#[must_use]
pub const fn advance(position: usize, byte: u8) -> usize {
    if byte != b'\n' {
        0
    } else {
        position.wrapping_add(1)
    }
}
