//! The errors that parsing can end in.

use pyo3::prelude::*;

pub enum ParseError {
    /// A load failure, such as a syntax error in the source, as an instance of
    /// a class from `define.compiler.errors.syntax_errors`.
    LoadFailure(Py<PyAny>),
    /// An exception that Python raised while the parser built the AST.
    Python(PyErr),
}

impl ParseError {
    /// The load failure, or the exception that Python raised while the parser
    /// built the AST.
    pub fn into_load_failure(self) -> PyResult<Py<PyAny>> {
        match self {
            Self::LoadFailure(failure) => Ok(failure),
            Self::Python(error) => Err(error),
        }
    }
}

impl From<PyErr> for ParseError {
    fn from(error: PyErr) -> Self {
        Self::Python(error)
    }
}

pub type ParseResult<T> = Result<T, ParseError>;
