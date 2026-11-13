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
mod load_failures;
#[rustfmt::skip]
mod parser_diagnostics;

use node_construction::Node as _;
use parse_error::ParseError;
use parser::{ParsedProgram, Parser};
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
    /// The `ast.Program`, unless the parse ended in `load_failure`.
    program: Option<Py<PyAny>>,
    /// The diagnostics that the parse found, in the order it found them.
    diagnostics: Py<PyList>,
    /// The `syntax_errors.FileLoadFailureDiagnostic` that ended the parse, if
    /// any.
    load_failure: Option<Py<PyAny>>,
}

impl From<ParsedProgram<'_>> for PythonParseResult {
    fn from(parsed: ParsedProgram<'_>) -> Self {
        Self {
            program: parsed.program.map(Bound::unbind),
            diagnostics: parsed.diagnostics.unbind(),
            load_failure: parsed.load_failure,
        }
    }
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
    parser::parse_source(py, source, file_path, check_indentation).map(PythonParseResult::from)
}

/// Reads the Define source file at `file_path`, registers it with the
/// `SourceMap` `source_map`, and parses it as `parse` does, checking
/// indentation. A file that does not exist ends the parse in a
/// `syntax_errors.SourceFileNotFound`, and one that cannot be read for any
/// other reason in a `syntax_errors.SourceFileUnreadable`.
#[pyfunction]
fn parse_file<'py>(
    file_path: Bound<'py, PyString>,
    source_map: &Bound<'py, PyAny>,
) -> PyResult<PythonParseResult> {
    parser::parse_file(file_path, source_map).map(PythonParseResult::from)
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
        Err(error) => error.into_load_failure(),
    }
}

// The module is named `parser`, which the crate's `parser` module already uses.
#[pymodule(gil_used = false, name = "parser")]
fn parser_module(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<PythonParseResult>()?;
    module.add_function(wrap_pyfunction!(parse, module)?)?;
    module.add_function(wrap_pyfunction!(parse_file, module)?)?;
    module.add_function(wrap_pyfunction!(parse_global_name, module)?)
}
