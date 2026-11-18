//! A function with a mutant that only clippy rejects.

#[must_use]
pub const fn tripled(value: u32) -> u32 {
    value * 3
}

#[cfg(test)]
mod tests {
    use super::*;
    use googletest::prelude::*;

    // Tripling zero gives zero, so `/` passes this test, and only clippy's
    // integer_division rejects it.
    #[gtest]
    fn zero() -> Result<()> {
        verify_that!(tripled(0), eq(0))
    }
}
