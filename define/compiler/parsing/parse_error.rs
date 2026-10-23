//! The errors that parsing can end in.

use pyo3::prelude::*;

pub enum ParseError {
    // TODO: Decide which syntax errors should stop the parse and which should
    // become diagnostics, so that the parser can keep going and report more
    // problems in one run. Checks that the validator makes today only because
    // they would otherwise stop the parse, such as an operation argument that
    // looks at a view in an action or at a position in an operation, could
    // then move into the parser.
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
