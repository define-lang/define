//! A function that only a test tagged `no-coverage` checks.

#[must_use]
pub const fn is_larger(left: u32, right: u32) -> bool {
    left > right
}

#[cfg(test)]
mod tests {
    use super::*;
    use googletest::prelude::*;

    #[gtest]
    fn larger() -> Result<()> {
        verify_that!(is_larger(2, 1), eq(true))
    }

    #[gtest]
    fn equal() -> Result<()> {
        verify_that!(is_larger(1, 1), eq(false))
    }

    #[gtest]
    fn smaller() -> Result<()> {
        verify_that!(is_larger(1, 2), eq(false))
    }
}
