// Rejected: arithmetic_overflow
// Rejected in mutation runs: nothing
//! An operator changed so that constant arithmetic overflows, which is the bug
//! itself.

#[must_use]
pub const fn hex_letter_value(letter: u8) -> u8 {
    letter.wrapping_sub(b'a').wrapping_add(200 * 10)
}
