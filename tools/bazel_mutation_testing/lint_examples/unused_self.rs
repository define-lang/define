// Rejected: dead_code, clippy::unused_self
// Rejected in mutation runs: nothing
//! A method whose body became a constant, which leaves `self` unused.

#[derive(Debug)]
pub struct Counter {
    count: u32,
}

impl Counter {
    #[must_use]
    pub const fn new(count: u32) -> Self {
        Self { count }
    }

    #[must_use]
    pub const fn doubled(&self) -> u32 {
        self.current().wrapping_mul(2)
    }

    const fn current(&self) -> u32 {
        0
    }
}
