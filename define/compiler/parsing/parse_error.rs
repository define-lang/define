//! The errors that parsing can end in.

use crate::scanner::Position;
use pyo3::exceptions::PyNotImplementedError;
use pyo3::prelude::*;

pub enum ParseError {
    /// Source that the parser does not handle yet.
    NotYetSupported {
        position: Position,
        description: &'static str,
    },
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

impl From<ParseError> for PyErr {
    fn from(error: ParseError) -> Self {
        match error {
            ParseError::NotYetSupported {
                position: Position { line, column },
                description,
            } => PyNotImplementedError::new_err(format!(
                "line {line}, column {column}: the parser does not support {description} yet"
            )),
            ParseError::Syntax(error) | ParseError::Python(error) => error,
        }
    }
}

pub type ParseResult<T> = Result<T, ParseError>;
