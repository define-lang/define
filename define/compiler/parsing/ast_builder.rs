use crate::ast::AstClasses;
use crate::node_construction::SourceLocation;
use crate::scanner::SourceText;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyString;
use rustc_hash::FxHashMap;
use source_rendering::Position;

/// Constructs the Python AST for one parse.
pub struct AstBuilder<'py> {
    py: Python<'py>,
    classes: &'static AstClasses,
    file_path: Option<Bound<'py, PyString>>,
    /// The interned Python string for each distinct text that this parse
    /// interns.
    interned_texts: FxHashMap<Box<[u8]>, Bound<'py, PyString>>,
}

impl<'py> AstBuilder<'py> {
    pub fn new(py: Python<'py>, file_path: Option<Bound<'py, PyString>>) -> PyResult<Self> {
        Ok(Self {
            py,
            classes: AstClasses::get(py)?,
            file_path,
            interned_texts: FxHashMap::default(),
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
    pub fn interned(&mut self, text: SourceText<'_>) -> PyResult<Bound<'py, PyString>> {
        if let Some(interned) = self.interned_texts.get(text.bytes) {
            return Ok(interned.clone());
        }
        let interned = PyString::intern(self.py, utf8(text)?);
        self.interned_texts
            .insert(text.bytes.into(), interned.clone());
        Ok(interned)
    }

    /// Returns a new Python string for `text`, such as literal content, which
    /// is not interned because it is rarely the same as other text.
    pub fn string(&self, text: SourceText<'_>) -> PyResult<Bound<'py, PyString>> {
        Ok(PyString::new(self.py, utf8(text)?))
    }

    pub fn location(&self, start: Position, end: Position) -> PyResult<SourceLocation<'py>> {
        // `end` is the position after the last character.
        let location = source_rendering::SourceLocation {
            start,
            end: end.previous_column(),
        };
        SourceLocation::new(self.py, location, self.file_path.as_ref())
    }
}

/// Returns `text`, which the parser has already checked is UTF-8, as a `str`.
#[expect(
    unsafe_code,
    reason = "Only an unchecked conversion skips checking text that a scan \
              already found is ASCII."
)]
fn utf8(text: SourceText<'_>) -> PyResult<&str> {
    if text.is_known_ascii {
        // SAFETY: Text that is known to be ASCII is valid UTF-8.
        return Ok(unsafe { std::str::from_utf8_unchecked(text.bytes) });
    }
    std::str::from_utf8(text.bytes)
        .map_err(|error| PyValueError::new_err(format!("text is not valid UTF-8: {error}")))
}
