//! Tests a crate in another package, which mutation runs leave out of the area.

#[cfg(test)]
mod tests {
    use googletest::prelude::*;
    use outside_area::is_larger;

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
