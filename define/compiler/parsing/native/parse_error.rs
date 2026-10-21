//! The errors that parsing can end in.

use crate::scanner::Position;
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

impl ParseError {
    pub const fn not_yet_supported(position: Position, description: &'static str) -> Self {
        Self::NotYetSupported {
            position,
            description,
        }
    }
}

impl From<PyErr> for ParseError {
    fn from(error: PyErr) -> Self {
        Self::Python(error)
    }
}

pub type ParseResult<T> = Result<T, ParseError>;
