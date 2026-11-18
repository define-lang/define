//! A function with a mutant that never returns.

#[must_use]
pub const fn first_multiple_from(step: u32, limit: u32) -> u32 {
    let mut value = 0;
    // Replacing `+=` with `*=` leaves `value` at zero forever.
    while value < limit {
        value += step;
    }
    value
}

#[cfg(test)]
mod tests {
    use super::*;
    use googletest::prelude::*;

    #[gtest]
    fn reaches_limit() -> Result<()> {
        verify_that!(first_multiple_from(3, 9), eq(9))
    }
}
