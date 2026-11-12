//! The parser's Python module.

mod ast_builder;
mod characters;
mod element_stack;
mod node_construction;
mod parse_error;
mod parser;
mod scanner;
// rustfmt runs on the source tree, which has ast.rs only after
// setup_local_dev copies it there.
#[rustfmt::skip]
mod ast;
// Generated like ast.rs, so rustfmt skips them for the same reason.
#[rustfmt::skip]
mod ast_constructors;
#[rustfmt::skip]
mod parser_diagnostics;
#[rustfmt::skip]
mod syntax_errors;

use node_construction::Node as _;
use parse_error::ParseError;
use parser::Parser;
use pyo3::prelude::*;
use pyo3::types::{PyList, PyString};
use source_rendering::Position;

/// The result of parsing Define source code.
#[pyclass(
    frozen,
    get_all,
    name = "ParseResult",
    module = "define.compiler.parsing.parser"
)]
struct PythonParseResult {
    /// The `ast.Program`, unless the parse ended in `syntax_error`.
    program: Option<Py<PyAny>>,
    /// The diagnostics that the parse found, in the order it found them.
    diagnostics: Py<PyList>,
    /// The `syntax_errors.DefineSyntaxError` that ended the parse, if any.
    syntax_error: Option<Py<PyAny>>,
}

/// Parses UTF-8 Define source code into an `ast.Program`. A line with the
/// wrong indentation gets a diagnostic only if `check_indentation`.
#[pyfunction]
#[pyo3(signature = (source, file_path, *, check_indentation = true))]
fn parse<'py>(
    py: Python<'py>,
    source: &[u8],
    file_path: Option<Bound<'py, PyString>>,
    check_indentation: bool,
) -> PyResult<PythonParseResult> {
    let mut parser = Parser::new(py, source, Position::START, file_path, check_indentation)?;
    let (program, syntax_error) = match parser.parse_program() {
        Ok(program) => (Some(program.into_object().unbind()), None),
        Err(ParseError::Syntax(error)) => (None, Some(error)),
        Err(ParseError::Python(error)) => return Err(error),
    };
    Ok(PythonParseResult {
        program,
        diagnostics: parser.into_diagnostics()?.unbind(),
        syntax_error,
    })
}

/// Parses `name`, a global name that is not in Define source, such as one
/// that configuration writes, into an `ast.ReferenceGlobalNameContent`. Its
/// first character is at `line` and `column` in the file at `file_path`, so
/// that the nodes' locations point there. Returns the
/// `syntax_errors.DefineSyntaxError` instead if `name` is not a global name.
#[pyfunction]
fn parse_global_name<'py>(
    py: Python<'py>,
    name: &[u8],
    file_path: Option<Bound<'py, PyString>>,
    line: u32,
    column: u32,
) -> PyResult<Py<PyAny>> {
    let mut parser = Parser::new(py, name, Position { line, column }, file_path, true)?;
    match parser.parse_global_name() {
        Ok(content) => Ok(content.into_object().unbind()),
        Err(ParseError::Syntax(error)) => Ok(error),
        Err(ParseError::Python(error)) => Err(error),
    }
}

// The module is named `parser`, which the crate's `parser` module already uses.
#[pymodule(gil_used = false, name = "parser")]
fn parser_module(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<PythonParseResult>()?;
    module.add_function(wrap_pyfunction!(parse, module)?)?;
    module.add_function(wrap_pyfunction!(parse_global_name, module)?)
}
