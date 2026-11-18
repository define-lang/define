//! A function whose only mutant does not compile.

#[derive(Debug, PartialEq, Eq)]
pub struct Token(u8);

#[must_use]
pub const fn first_token() -> Token {
    Token(1)
}

#[cfg(test)]
mod tests {
    use super::*;
    use googletest::prelude::*;

    #[gtest]
    fn first() -> Result<()> {
        verify_that!(first_token(), eq(&Token(1)))
    }
}
