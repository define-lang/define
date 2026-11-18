//! A let chain, whose `&&` cargo-mutants replaces with `||`, which does not
//! parse.

#[must_use]
pub const fn nonzero_first(values: &[u32]) -> Option<u32> {
    if let Some(&first) = values.first()
        && first != 0
    {
        return Some(first);
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;
    use googletest::prelude::*;

    #[gtest]
    fn nonzero() -> Result<()> {
        verify_that!(nonzero_first(&[2, 0]), some(eq(2)))
    }

    #[gtest]
    fn zero() -> Result<()> {
        verify_that!(nonzero_first(&[0, 2]), none())
    }
}
