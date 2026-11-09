//! The errors that parsing can end in.

use pyo3::prelude::*;

pub enum ParseError {
    /// A syntax error in the source, as an instance of a class from
    /// `define.compiler.errors.syntax_errors`.
    Syntax(Py<PyAny>),
    /// An exception that Python raised while the parser built the AST.
    Python(PyErr),
}

impl From<PyErr> for ParseError {
    fn from(error: PyErr) -> Self {
        Self::Python(error)
    }
}

pub type ParseResult<T> = Result<T, ParseError>;
