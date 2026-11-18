//! A crate whose test fails without any mutant.

#[must_use]
pub const fn is_larger(left: u32, right: u32) -> bool {
    left > right
}

#[cfg(test)]
mod tests {
    use super::*;
    use googletest::prelude::*;

    #[gtest]
    fn wrong() -> Result<()> {
        verify_that!(is_larger(2, 1), eq(false))
    }
}
