//! Lets other Python extensions, such as Define's parser and defcl, construct
//! `source_rendering.python.rendering.SourceLocation`s from Rust. Only the
//! rendering extension can construct the class natively, so it exports its
//! constructor in a capsule, which this crate imports once and calls.

use pyo3::ffi;
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::types::{PyCapsule, PyString};
use source_rendering::SourceLocation;
use std::ffi::CStr;

/// The constructor that the capsule holds.
///
/// It takes the location's file path as a borrowed reference to a `str`, or
/// null for no file path, and returns a new reference, or null with an
/// exception set. Callers must be attached to the interpreter.
pub type NewSourceLocation =
    unsafe extern "C" fn(SourceLocation, *mut ffi::PyObject) -> *mut ffi::PyObject;

/// The name of the capsule, which is also where the rendering extension's module
/// holds it.
pub const CAPSULE_NAME: &CStr = c"source_rendering.python.rendering._new_source_location";

static CONSTRUCTOR: PyOnceLock<NewSourceLocation> = PyOnceLock::new();

/// A new `source_rendering.python.rendering.SourceLocation` for `location` in
/// the file at `file_path`.
///
/// # Errors
///
/// The error that Python raised while importing the rendering extension or
/// constructing the location.
#[expect(
    unsafe_code,
    reason = "Only a C function can cross from one extension to another."
)]
pub fn new_source_location<'py>(
    py: Python<'py>,
    location: SourceLocation,
    file_path: Option<&Bound<'py, PyString>>,
) -> PyResult<Bound<'py, PyAny>> {
    let constructor = *CONSTRUCTOR.get_or_try_init(py, || import_constructor(py))?;
    let file_path = file_path.map_or(std::ptr::null_mut(), Bound::as_ptr);
    // SAFETY: `py` shows that the caller is attached, and `file_path` is null
    // or a `str` that the caller holds for the whole call.
    let location = unsafe { constructor(location, file_path) };
    // SAFETY: The constructor returns a new reference, or null with an
    // exception set.
    unsafe { Bound::from_owned_ptr_or_err(py, location) }
}

#[expect(
    unsafe_code,
    reason = "A capsule holds a raw pointer, which only unsafe code can read."
)]
fn import_constructor(py: Python<'_>) -> PyResult<NewSourceLocation> {
    // Importing a capsule only imports the top-level package and then looks up
    // each name after it, so a submodule that nothing has imported yet would
    // not be found.
    let _: Bound<'_, PyModule> = py.import("source_rendering.python.rendering")?;
    let pointer = PyCapsule::import_pointer(py, CAPSULE_NAME)?;
    // SAFETY: The rendering extension's capsule points to a static
    // `NewSourceLocation`.
    Ok(unsafe { *pointer.cast::<NewSourceLocation>().as_ptr() })
}
