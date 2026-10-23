use crate::ast::{AstClasses, SourceLocation};
use crate::node_construction::{FilePath, Node, NodeTuple};
use crate::scanner::Position;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyFrozenSet, PyInt, PyString, PyTuple};
use rustc_hash::FxHashMap;
use std::marker::PhantomData;

/// Where the elements of a tuple start on the builder's element stack. It is
/// not `Copy`, so that each tuple is finished exactly once.
pub struct TupleStart<Element> {
    index: usize,
    element: PhantomData<Element>,
}

/// Where the texts of a tuple or set start on the builder's text stack. It is
/// not `Copy`, so that each tuple or set is finished exactly once.
pub struct TextsStart {
    index: usize,
}

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
    /// The elements of the tuples being built. A construct pushes its elements
    /// after any elements of the constructs it belongs to, and takes them off
    /// before it returns, so one stack serves every construct.
    tuple_elements: Vec<Bound<'py, PyAny>>,
    /// The texts of the tuples and sets of texts being built, which are taken
    /// off like `tuple_elements`.
    text_elements: Vec<Bound<'py, PyString>>,
}

impl<'py> AstBuilder<'py> {
    pub fn new(py: Python<'py>, file_path: Option<FilePath<'py>>) -> PyResult<Self> {
        Ok(Self {
            py,
            classes: AstClasses::get(py)?,
            file_path,
            interned_texts: FxHashMap::default(),
            line_numbers: Vec::new(),
            tuple_elements: Vec::new(),
            text_elements: Vec::new(),
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

    pub const fn start_tuple<Element>(&self) -> TupleStart<Element> {
        TupleStart {
            index: self.tuple_elements.len(),
            element: PhantomData,
        }
    }

    // `_start` makes the element's type the one that its tuple holds.
    pub fn push<Element: Node<'py>>(
        &mut self,
        _start: &TupleStart<Element>,
        element: impl Into<Element>,
    ) {
        self.tuple_elements.push(element.into().into_object());
    }

    pub const fn start_texts(&self) -> TextsStart {
        TextsStart {
            index: self.text_elements.len(),
        }
    }

    // `_start` is the tuple or set that the text belongs to.
    pub fn push_text(&mut self, _start: &TextsStart, text: Bound<'py, PyString>) {
        self.text_elements.push(text);
    }

    pub fn finish_text_tuple(&mut self, start: TextsStart) -> PyResult<Bound<'py, PyTuple>> {
        PyTuple::new(self.py, self.text_elements.drain(start.index..))
    }

    pub fn finish_text_set(&mut self, start: TextsStart) -> PyResult<Bound<'py, PyFrozenSet>> {
        PyFrozenSet::new(self.py, self.text_elements.drain(start.index..))
    }

    pub fn finish_tuple<Element>(
        &mut self,
        start: TupleStart<Element>,
    ) -> PyResult<NodeTuple<'py, Element>> {
        Ok(NodeTuple::new(PyTuple::new(
            self.py,
            self.tuple_elements.drain(start.index..),
        )?))
    }
}

/// Returns `text`, which the parser has already checked is UTF-8, as a `str`.
fn utf8(text: &[u8]) -> PyResult<&str> {
    std::str::from_utf8(text)
        .map_err(|error| PyValueError::new_err(format!("text is not valid UTF-8: {error}")))
}
