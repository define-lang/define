//! The Python module that renders locations in source files:
//! `crates.source_rendering.python.rendering`.

use pyo3::basic::CompareOp;
use pyo3::exceptions::PyValueError;
use pyo3::ffi;
use pyo3::prelude::*;
use pyo3::types::{PyCapsule, PyString};
use rustc_hash::FxHasher;
use source_rendering::Position;
use source_rendering_capsule::NewSourceLocation;
use std::hash::{Hash as _, Hasher as _};

/// The part of a source file that something, such as a diagnostic, covers.
/// Lines and columns are 1-based, columns count characters, and `end_line` and
/// `end_column` are the position of the last character that it covers.
// A program has millions of these, so each holds the Rust location itself
// rather than a Python object for each number.
#[pyclass(
    frozen,
    name = "SourceLocation",
    module = "crates.source_rendering.python.rendering"
)]
struct PySourceLocation {
    location: source_rendering::SourceLocation,
    file_path: Option<Py<PyString>>,
}

const fn location(
    line: u32,
    column: u32,
    end_line: u32,
    end_column: u32,
) -> source_rendering::SourceLocation {
    source_rendering::SourceLocation {
        start: Position { line, column },
        end: Position {
            line: end_line,
            column: end_column,
        },
    }
}

#[pymethods]
impl PySourceLocation {
    #[new]
    #[pyo3(signature = (*, line, column, end_line, end_column, file_path = None))]
    const fn new(
        line: u32,
        column: u32,
        end_line: u32,
        end_column: u32,
        file_path: Option<Py<PyString>>,
    ) -> Self {
        Self {
            location: location(line, column, end_line, end_column),
            file_path,
        }
    }

    #[getter]
    const fn line(&self) -> u32 {
        self.location.start.line
    }

    #[getter]
    const fn column(&self) -> u32 {
        self.location.start.column
    }

    #[getter]
    const fn end_line(&self) -> u32 {
        self.location.end.line
    }

    #[getter]
    const fn end_column(&self) -> u32 {
        self.location.end.column
    }

    #[getter]
    fn file_path(&self, py: Python<'_>) -> Option<Py<PyString>> {
        self.file_path
            .as_ref()
            .map(|file_path| file_path.clone_ref(py))
    }

    /// The location from `line`, `column` through `end_line`, `end_column` in
    /// the same file as this one.
    #[pyo3(signature = (*, line, column, end_line, end_column))]
    fn at(&self, py: Python<'_>, line: u32, column: u32, end_line: u32, end_column: u32) -> Self {
        Self {
            location: location(line, column, end_line, end_column),
            file_path: self.file_path(py),
        }
    }

    /// The location as diagnostics show it: a header that names its file, if
    /// it has one, then `source_line`, the line that it starts on, with carets
    /// under the part that it covers. With no `source_line`, only the header.
    fn render(&self, py: Python<'_>, source_line: Option<&str>) -> PyResult<String> {
        let file_path = match &self.file_path {
            Some(file_path) => Some(file_path.bind(py).to_str()?),
            None => None,
        };
        Ok(self.location.render(source_line, file_path))
    }

    fn __richcmp__(&self, other: &Bound<'_, PyAny>, operator: CompareOp) -> PyResult<Py<PyAny>> {
        let py = other.py();
        let Ok(other) = other.cast::<Self>() else {
            return Ok(py.NotImplemented());
        };
        let other = other.get();
        let is_equal = self.location == other.location
            && match (&self.file_path, &other.file_path) {
                (None, None) => true,
                (Some(file_path), Some(other_file_path)) => {
                    file_path.is(other_file_path)
                        || file_path.bind(py).as_any().eq(other_file_path.bind(py))?
                }
                _ => false,
            };
        match operator {
            CompareOp::Eq => Ok(is_equal.into_pyobject(py)?.to_owned().into_any().unbind()),
            CompareOp::Ne => Ok((!is_equal)
                .into_pyobject(py)?
                .to_owned()
                .into_any()
                .unbind()),
            CompareOp::Lt | CompareOp::Le | CompareOp::Gt | CompareOp::Ge => {
                Ok(py.NotImplemented())
            }
        }
    }

    fn __hash__(&self, py: Python<'_>) -> PyResult<u64> {
        let mut hasher = FxHasher::default();
        self.location.hash(&mut hasher);
        if let Some(file_path) = &self.file_path {
            hasher.write_isize(file_path.bind(py).hash()?);
        }
        Ok(hasher.finish())
    }

    fn __repr__(&self, py: Python<'_>) -> PyResult<String> {
        let file_path = match &self.file_path {
            Some(file_path) => file_path.bind(py).repr()?.to_string(),
            None => String::from("None"),
        };
        Ok(format!(
            "SourceLocation(line={}, column={}, end_line={}, end_column={}, file_path={file_path})",
            self.location.start.line,
            self.location.start.column,
            self.location.end.line,
            self.location.end.column,
        ))
    }
}

/// Shows locations with their source lines, reading each registered file again
/// only when a location in it is first shown, and showing no source lines for a
/// file that changed after it was registered.
#[pyclass(
    frozen,
    name = "SourceMap",
    module = "crates.source_rendering.python.rendering"
)]
struct PySourceMap {
    source_map: source_rendering::SourceMap,
}

#[pymethods]
impl PySourceMap {
    #[new]
    #[pyo3(signature = (in_memory_source = None))]
    fn new(in_memory_source: Option<String>) -> Self {
        Self {
            source_map: source_rendering::SourceMap::new(in_memory_source),
        }
    }

    /// Records that the file at `path` was validated with a text whose digest
    /// is `digest`, as an extension that has the text computes it with the
    /// `source_rendering` crate, so that the text is not copied into Python.
    fn register_file_digest(&self, path: &str, digest: u64) {
        self.source_map.register_file_digest(path, digest);
    }

    /// The header that names the file at `path`, then, if the file was
    /// registered but no longer has the text it was registered with, why its
    /// source lines cannot be shown.
    fn render_header_without_position(&self, path: &str) -> String {
        self.source_map.render_header_without_position(path)
    }

    /// `location` as diagnostics show it, with its source line when its file
    /// is unchanged.
    fn render_location(&self, location: &Bound<'_, PySourceLocation>) -> PyResult<String> {
        let py = location.py();
        let location = location.get();
        let Some(file_path) = &location.file_path else {
            return self
                .source_map
                .render_in_memory(location.location)
                .map_err(|error| PyValueError::new_err(error.to_string()));
        };
        Ok(self
            .source_map
            .render_in_file(location.location, file_path.bind(py).to_str()?))
    }
}

/// The constructor that the module's capsule holds, as
/// `source_rendering_capsule::NewSourceLocation` describes it.
#[expect(
    unsafe_code,
    reason = "Only a C function can cross from one extension to another."
)]
unsafe extern "C" fn new_source_location(
    location: source_rendering::SourceLocation,
    file_path: *mut ffi::PyObject,
) -> *mut ffi::PyObject {
    // SAFETY: Callers must be attached to the interpreter.
    let py = unsafe { Python::assume_attached() };
    // SAFETY: `file_path` is null or a reference that the caller holds for the
    // whole call.
    let file_path = unsafe { Bound::from_borrowed_ptr_or_opt(py, file_path) };
    // SAFETY: Callers pass a `str`, as `NewSourceLocation` requires.
    let file_path =
        file_path.map(|file_path| unsafe { file_path.cast_into_unchecked::<PyString>() }.unbind());
    match Py::new(
        py,
        PySourceLocation {
            location,
            file_path,
        },
    ) {
        Ok(location) => location.into_ptr(),
        Err(error) => {
            error.restore(py);
            std::ptr::null_mut()
        }
    }
}

static NEW_SOURCE_LOCATION: NewSourceLocation = new_source_location;

#[pymodule(gil_used = false)]
mod rendering {
    use super::{NEW_SOURCE_LOCATION, PyCapsule};
    use pyo3::prelude::*;
    use source_rendering_capsule::CAPSULE_NAME;

    #[pymodule_export]
    use super::{PySourceLocation, PySourceMap};

    #[pymodule_init]
    #[expect(
        unsafe_code,
        reason = "A capsule holds a raw pointer, which only unsafe code can make."
    )]
    fn init(module: &Bound<'_, PyModule>) -> PyResult<()> {
        let pointer = std::ptr::NonNull::from(&NEW_SOURCE_LOCATION).cast();
        // SAFETY: The pointer is to a static, which lives as long as the
        // process.
        let capsule = unsafe { PyCapsule::new_with_pointer(module.py(), pointer, CAPSULE_NAME)? };
        module.add("_new_source_location", capsule)
    }
}
