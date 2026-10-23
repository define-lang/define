//! The parser's Python module.

mod ast_builder;
mod characters;
mod parse_error;
mod parser;
mod scanner;
// rustfmt runs on the source tree, which has ast.rs only after
// setup_local_dev copies it there.
#[rustfmt::skip]
mod ast;
// Generated like ast.rs, so rustfmt skips them for the same reason.
#[rustfmt::skip]
mod parser_diagnostics;
#[rustfmt::skip]
mod syntax_errors;

use ast_builder::{FilePath, Node};
use parse_error::ParseError;
use parser::Parser;
use pyo3::prelude::*;
use pyo3::types::PyList;

/// The result of parsing Define source code.
#[pyclass(
    frozen,
    get_all,
    name = "ParseResult",
    module = "define.compiler.parsing.native_parser"
)]
struct PythonParseResult {
    /// The `ast.Program`, unless the parse ended in `exception`.
    program: Option<Py<PyAny>>,
    /// The diagnostics that the parse found, in source order.
    diagnostics: Py<PyList>,
    /// The `parser_exceptions.DefineSyntaxError` that ended the parse, if any.
    exception: Option<Py<PyAny>>,
}

/// Parses UTF-8 Define source code into an `ast.Program`.
#[pyfunction]
fn parse<'py>(
    py: Python<'py>,
    source: &[u8],
    file_path: Option<Bound<'py, PyAny>>,
) -> PyResult<PythonParseResult> {
    let file_path = file_path.map(FilePath::new);
    let mut parser = Parser::new(py, source, file_path)?;
    let (program, exception) = match parser.parse_program() {
        Ok(program) => (Some(program.into_object().unbind()), None),
        Err(ParseError::Syntax(error)) => (None, Some(error.into_value(py).into_any())),
        Err(ParseError::Python(error)) => return Err(error),
    };
    Ok(PythonParseResult {
        program,
        diagnostics: parser.into_diagnostics()?.unbind(),
        exception,
    })
}

#[pymodule(gil_used = false)]
fn native_parser(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<PythonParseResult>()?;
    module.add_function(wrap_pyfunction!(parse, module)?)
}
