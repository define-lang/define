//! A Python module whose function only a Python test calls:
//! `tools.bazel_mutation_testing.testdata.rust.killed_by_py_test.extension`.

#[pyo3::pymodule(gil_used = false)]
mod extension {
    use pyo3::prelude::*;

    #[pyfunction]
    const fn is_larger(left: u32, right: u32) -> bool {
        left > right
    }
}
