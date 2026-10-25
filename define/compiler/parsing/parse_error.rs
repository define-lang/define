//! The errors that parsing can end in.

use pyo3::prelude::*;

pub enum ParseError {
    /// A syntax error in the source, as an exception from
    /// `define.compiler.errors.parser_exceptions`.
    Syntax(PyErr),
    /// An exception that Python raised while the parser built the AST.
    Python(PyErr),
}

impl From<PyErr> for ParseError {
    fn from(error: PyErr) -> Self {
        Self::Python(error)
    }
}

pub type ParseResult<T> = Result<T, ParseError>;
