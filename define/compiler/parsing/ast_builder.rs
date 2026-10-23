use crate::ast::{AstClasses, SourceLocation};
use crate::node_construction::FilePath;
use crate::scanner::Position;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyInt, PyString};
use rustc_hash::FxHashMap;

/// Constructs the Python AST for one parse.
pub struct AstBuilder<'py> {
    py: Python<'py>,
    classes: &'static AstClasses,
    file_path: Option<FilePath<'py>>,
    /// The interned Python string for each distinct text that this parse
    /// interns.
    interned_texts: FxHashMap<Box<[u8]>, Bound<'py, PyString>>,
    /// The Python int for each line number, indexed by line number minus one.
    line_numbers: Vec<Bound<'py, PyInt>>,
}

impl<'py> AstBuilder<'py> {
    pub fn new(py: Python<'py>, file_path: Option<FilePath<'py>>) -> PyResult<Self> {
        Ok(Self {
            py,
            classes: AstClasses::get(py)?,
            file_path,
            interned_texts: FxHashMap::default(),
            line_numbers: Vec::new(),
        })
    }

    pub const fn py(&self) -> Python<'py> {
        self.py
    }

    pub const fn classes(&self) -> &'static AstClasses {
        self.classes
    }

    /// Returns the interned Python string for `text`, creating it only the
    /// first time this parse interns that text. CPython's own interning would
    /// create a new string on every call, only to discard it when the text is
    /// already interned.
    pub fn interned(&mut self, text: &[u8]) -> PyResult<Bound<'py, PyString>> {
        if let Some(interned) = self.interned_texts.get(text) {
            return Ok(interned.clone());
        }
        let interned = PyString::intern(self.py, utf8(text)?);
        self.interned_texts.insert(text.into(), interned.clone());
        Ok(interned)
    }

    /// Returns a new Python string for `text`, such as literal content, which
    /// is not interned because it is rarely the same as other text.
    pub fn string(&self, text: &[u8]) -> PyResult<Bound<'py, PyString>> {
        Ok(PyString::new(self.py, utf8(text)?))
    }

    pub fn location(&mut self, start: Position, end: Position) -> PyResult<SourceLocation<'py>> {
        let line = self.line_number(start.line);
        let end_line = self.line_number(end.line);
        self.source_location(
            line,
            PyInt::new(self.py, start.column),
            end_line,
            // `end` is the position after the last character.
            PyInt::new(self.py, end.column - 1),
            self.file_path.clone(),
        )
    }

    fn line_number(&mut self, line: usize) -> Bound<'py, PyInt> {
        while self.line_numbers.len() < line {
            let next_line = self.line_numbers.len() + 1;
            self.line_numbers.push(PyInt::new(self.py, next_line));
        }
        self.line_numbers[line - 1].clone()
    }
}

/// Returns `text`, which the parser has already checked is UTF-8, as a `str`.
fn utf8(text: &[u8]) -> PyResult<&str> {
    std::str::from_utf8(text)
        .map_err(|error| PyValueError::new_err(format!("text is not valid UTF-8: {error}")))
}
