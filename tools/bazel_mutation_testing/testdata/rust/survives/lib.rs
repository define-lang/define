//! A function whose tests miss one of its mutants.

#[must_use]
pub const fn is_larger(left: u32, right: u32) -> bool {
    left > right
}

#[cfg(test)]
mod tests {
    use super::*;
    use googletest::prelude::*;

    // No test compares equal values, so `>=` survives.
    #[gtest]
    fn larger() -> Result<()> {
        verify_that!(is_larger(2, 1), eq(true))
    }

    #[gtest]
    fn smaller() -> Result<()> {
        verify_that!(is_larger(1, 2), eq(false))
    }
}
