//! The Python module that validates DCL files: `defcl.python2.validator`.

use defcl_parser::{SourceLocation, SyntaxError, SyntaxErrorKind};
use defcl_semantics::{FileDescriptorSet, SemanticError, SemanticErrorKind};
use defcl_validator::{RenderedError, ValidationError};
use prost::Message;
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::types::PyType;
use std::path::PathBuf;

/// The Python classes that the module returns and raises.
struct PythonClasses {
    source_location: Py<PyType>,
    dcl_error: Py<PyType>,
    dcl_error_kind: Py<PyType>,
    invalid_schema_error: Py<PyType>,
    dcl_diagnostic: Py<PyType>,
    diagnostic_kind: Py<PyType>,
}

static PYTHON_CLASSES: PyOnceLock<PythonClasses> = PyOnceLock::new();

impl PythonClasses {
    fn get(py: Python<'_>) -> PyResult<&'static Self> {
        PYTHON_CLASSES.get_or_try_init(py, || Self::import(py))
    }

    fn import(py: Python<'_>) -> PyResult<Self> {
        let errors = py.import("defcl.python2.errors")?;
        let error_types = py.import("defcl.python2.error_types")?;
        Ok(Self {
            source_location: class(&errors, "SourceLocation")?,
            dcl_error: class(&errors, "DclError")?,
            dcl_error_kind: class(&error_types, "DclErrorKind")?,
            invalid_schema_error: class(&errors, "InvalidSchemaError")?,
            dcl_diagnostic: class(&errors, "DclDiagnostic")?,
            diagnostic_kind: class(&error_types, "DiagnosticKind")?,
        })
    }

    fn source_location<'py>(
        &self,
        py: Python<'py>,
        location: SourceLocation,
    ) -> PyResult<Bound<'py, PyAny>> {
        self.source_location.bind(py).call1((
            location.line,
            location.column,
            location.end_line,
            location.end_column,
        ))
    }

    fn invalid_schema_error(&self, py: Python<'_>, error: &impl ToString) -> PyErr {
        raise(
            self.invalid_schema_error
                .bind(py)
                .call1((error.to_string(),)),
        )
    }

    fn dcl_error<'py>(
        &self,
        py: Python<'py>,
        rendered_error: &RenderedError<SyntaxError>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let error = &rendered_error.error;
        let kind: &'static str = error.kind.into();
        let character = match error.kind {
            SyntaxErrorKind::UnexpectedCharacter { character } => Some(character),
            _ => None,
        };
        self.dcl_error.bind(py).call1((
            self.dcl_error_kind.bind(py).getattr(kind)?,
            error.to_string(),
            self.source_location(py, error.location)?,
            character,
            &rendered_error.rendered,
        ))
    }

    fn dcl_diagnostic<'py>(
        &self,
        py: Python<'py>,
        rendered_error: &RenderedError<SemanticError>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let error = &rendered_error.error;
        let kind: &'static str = (&error.kind).into();
        let message_type = match &error.kind {
            SemanticErrorKind::UnknownFieldName { message_type } => Some(message_type),
            _ => None,
        };
        self.dcl_diagnostic.bind(py).call1((
            self.diagnostic_kind.bind(py).getattr(kind)?,
            error.to_string(),
            self.source_location(py, error.location)?,
            &error.field_name,
            message_type,
            &rendered_error.rendered,
        ))
    }
}

fn class(module: &Bound<'_, PyModule>, name: &str) -> PyResult<Py<PyType>> {
    Ok(module.getattr(name)?.cast_into::<PyType>()?.unbind())
}

/// The `PyErr` that raises `exception`, or the error that building it ended
/// in.
fn raise(exception: PyResult<Bound<'_, PyAny>>) -> PyErr {
    match exception {
        Ok(exception) => PyErr::from_value(exception),
        // Only an exception that Python raised while building the exception.
        // LCOV_EXCL_START
        Err(error) => error,
        // LCOV_EXCL_STOP
    }
}

/// Validates the DCL text `source` against the schema whose top-level message
/// type has the full name `top_level_message_type` in the binary
/// `FileDescriptorSet` `descriptor_set`, and returns a `DclDiagnostic` for each
/// semantic error, in source order. Raises `InvalidSchemaError` if the
/// descriptor set cannot be decoded or has no such message type, and
/// `DclError` for the first syntax error.
#[pyfunction]
fn validate<'py>(
    py: Python<'py>,
    source: &str,
    descriptor_set: &[u8],
    top_level_message_type: &str,
) -> PyResult<Vec<Bound<'py, PyAny>>> {
    let classes = PythonClasses::get(py)?;
    let descriptor_set = decode_descriptor_set(py, classes, descriptor_set)?;
    diagnostics(
        py,
        classes,
        defcl_validator::validate(source, descriptor_set, top_level_message_type),
    )
}

/// Validates the DCL file at `path` as `validate` validates its text, with
/// errors that name the file, and returns the file's text with the
/// diagnostics. Raises `OSError` if the file cannot be read.
#[pyfunction]
fn validate_file<'py>(
    py: Python<'py>,
    path: PathBuf,
    descriptor_set: &[u8],
    top_level_message_type: &str,
) -> PyResult<(String, Vec<Bound<'py, PyAny>>)> {
    let classes = PythonClasses::get(py)?;
    let descriptor_set = decode_descriptor_set(py, classes, descriptor_set)?;
    let (source, result) =
        defcl_validator::validate_file(&path, descriptor_set, top_level_message_type)?;
    Ok((source, diagnostics(py, classes, result)?))
}

fn decode_descriptor_set(
    py: Python<'_>,
    classes: &PythonClasses,
    descriptor_set: &[u8],
) -> PyResult<FileDescriptorSet> {
    FileDescriptorSet::decode(descriptor_set)
        .map_err(|error| classes.invalid_schema_error(py, &error))
}

/// The `DclDiagnostic`s of `result`'s semantic errors, or the exception that
/// its other errors raise.
fn diagnostics<'py>(
    py: Python<'py>,
    classes: &PythonClasses,
    result: Result<(), ValidationError>,
) -> PyResult<Vec<Bound<'py, PyAny>>> {
    match result {
        Ok(()) => Ok(Vec::new()),
        Err(ValidationError::Schema(error)) => Err(classes.invalid_schema_error(py, &error)),
        Err(ValidationError::Syntax(error)) => Err(raise(classes.dcl_error(py, &error))),
        Err(ValidationError::Semantic(errors)) => errors
            .iter()
            .map(|error| classes.dcl_diagnostic(py, error))
            .collect(),
    }
}

#[pymodule(gil_used = false)]
mod validator {
    #[pymodule_export]
    use super::{validate, validate_file};
}
