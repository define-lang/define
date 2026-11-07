//! The Python module that validates DCL files: `defcl.python.validator`.

use defcl_parser::{FieldPathElement, FieldPathLocation, SyntaxError, SyntaxErrorKind, parse};
use defcl_semantics::{FileDescriptorSet, SemanticError, SemanticErrorKind};
use defcl_validator::{RenderedError, ValidationError};
use prost::Message as _;
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::types::PyType;
use source_rendering::{SourceLines, SourceLocation};
use std::path::PathBuf;

/// The Python classes that the module returns and raises.
struct PythonClasses {
    source_location: Py<PyType>,
    field_path_location: Py<PyType>,
    dcl_error: Py<PyType>,
    unexpected_character_error: Py<PyType>,
    dcl_error_kind: Py<PyType>,
    invalid_schema_error: Py<PyType>,
    dcl_diagnostic: Py<PyType>,
    unknown_field_name_diagnostic: Py<PyType>,
    unknown_enum_value_diagnostic: Py<PyType>,
    integer_out_of_range_diagnostic: Py<PyType>,
    float_out_of_range_diagnostic: Py<PyType>,
    second_field_of_oneof_diagnostic: Py<PyType>,
    diagnostic_kind: Py<PyType>,
}

static PYTHON_CLASSES: PyOnceLock<PythonClasses> = PyOnceLock::new();

impl PythonClasses {
    fn get(py: Python<'_>) -> PyResult<&'static Self> {
        PYTHON_CLASSES.get_or_try_init(py, || Self::import(py))
    }

    fn import(py: Python<'_>) -> PyResult<Self> {
        let errors = py.import("defcl.python.errors")?;
        let error_types = py.import("defcl.python.error_types")?;
        let locations = py.import("defcl.python.locations")?;
        Ok(Self {
            source_location: class(&locations, "SourceLocation")?,
            field_path_location: class(&locations, "FieldPathLocation")?,
            dcl_error: class(&errors, "DclError")?,
            unexpected_character_error: class(&errors, "UnexpectedCharacterError")?,
            dcl_error_kind: class(&error_types, "DclErrorKind")?,
            invalid_schema_error: class(&errors, "InvalidSchemaError")?,
            dcl_diagnostic: class(&errors, "DclDiagnostic")?,
            unknown_field_name_diagnostic: class(&errors, "UnknownFieldNameDiagnostic")?,
            unknown_enum_value_diagnostic: class(&errors, "UnknownEnumValueDiagnostic")?,
            integer_out_of_range_diagnostic: class(&errors, "IntegerOutOfRangeDiagnostic")?,
            float_out_of_range_diagnostic: class(&errors, "FloatOutOfRangeDiagnostic")?,
            second_field_of_oneof_diagnostic: class(&errors, "SecondFieldOfOneofDiagnostic")?,
            diagnostic_kind: class(&error_types, "DiagnosticKind")?,
        })
    }

    fn source_location<'py>(
        &self,
        py: Python<'py>,
        location: SourceLocation,
    ) -> PyResult<Bound<'py, PyAny>> {
        self.source_location.bind(py).call1((
            location.start.line,
            location.start.column,
            location.end.line,
            location.end.column,
        ))
    }

    fn field_path_location<'py>(
        &self,
        py: Python<'py>,
        location: FieldPathLocation,
    ) -> PyResult<Bound<'py, PyAny>> {
        let name = location
            .name
            .map(|name| self.source_location(py, name))
            .transpose()?;
        self.field_path_location.bind(py).call1((
            name,
            self.source_location(py, location.value)?,
            location.is_whole_path,
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
        let kind = self.dcl_error_kind.bind(py).getattr(kind)?;
        let message = error.to_string();
        let location = self.source_location(py, error.location)?;
        let rendered = &rendered_error.rendered;
        if let SyntaxErrorKind::UnexpectedCharacter { character } = error.kind {
            return self
                .unexpected_character_error
                .bind(py)
                .call1((kind, message, location, rendered, character));
        }
        self.dcl_error
            .bind(py)
            .call1((kind, message, location, rendered))
    }

    fn dcl_diagnostic<'py>(
        &self,
        py: Python<'py>,
        rendered_error: &RenderedError<SemanticError>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let error = &rendered_error.error;
        let kind: &'static str = (&error.kind).into();
        let kind = self.diagnostic_kind.bind(py).getattr(kind)?;
        let message = error.to_string();
        let location = self.source_location(py, error.location)?;
        let field_name = &error.field_name;
        let rendered = &rendered_error.rendered;
        match &error.kind {
            SemanticErrorKind::UnknownFieldName { message_type } => self
                .unknown_field_name_diagnostic
                .bind(py)
                .call1((kind, message, location, field_name, rendered, message_type)),
            SemanticErrorKind::UnknownEnumValue { enum_type } => self
                .unknown_enum_value_diagnostic
                .bind(py)
                .call1((kind, message, location, field_name, rendered, enum_type)),
            SemanticErrorKind::IntegerOutOfRange { field_type } => {
                self.integer_out_of_range_diagnostic.bind(py).call1((
                    kind,
                    message,
                    location,
                    field_name,
                    rendered,
                    field_type.to_string(),
                ))
            }
            SemanticErrorKind::FloatOutOfRange { field_type } => {
                self.float_out_of_range_diagnostic.bind(py).call1((
                    kind,
                    message,
                    location,
                    field_name,
                    rendered,
                    field_type.to_string(),
                ))
            }
            SemanticErrorKind::SecondFieldOfOneof { oneof } => self
                .second_field_of_oneof_diagnostic
                .bind(py)
                .call1((kind, message, location, field_name, rendered, oneof)),
            _ => self
                .dcl_diagnostic
                .bind(py)
                .call1((kind, message, location, field_name, rendered)),
        }
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
#[expect(
    clippy::needless_pass_by_value,
    reason = "pyo3 can only extract a path argument as an owned PathBuf"
)]
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

/// An element of a field path from Python: a field name, or the index of an
/// element of the repeated value before it.
#[derive(FromPyObject)]
enum PythonFieldPathElement {
    Field(String),
    Index(usize),
}

/// Where the DCL text `source` writes the field at `field_path`, a sequence of
/// field names and indices of repeated values' elements whose first element is
/// a top-level message, or the nearest field on the path that it writes, as a
/// `FieldPathLocation`, or `None` if it does not write the path's top-level
/// message. Raises `DclError` for the first syntax error.
#[pyfunction]
#[expect(
    clippy::needless_pass_by_value,
    reason = "pyo3 can only extract a sequence argument as an owned Vec"
)]
fn location_of<'py>(
    py: Python<'py>,
    source: &str,
    field_path: Vec<PythonFieldPathElement>,
) -> PyResult<Option<Bound<'py, PyAny>>> {
    let classes = PythonClasses::get(py)?;
    let mut path = Vec::with_capacity(field_path.len());
    for element in &field_path {
        path.push(match element {
            PythonFieldPathElement::Field(name) => FieldPathElement::Field(name),
            PythonFieldPathElement::Index(index) => FieldPathElement::Index(*index),
        });
    }
    let file = parse(source).map_err(|error| {
        raise(classes.dcl_error(
            py,
            &RenderedError {
                rendered: error.render(&SourceLines::new(source), None),
                error,
            },
        ))
    })?;
    file.location_of(&path)
        .map(|location| classes.field_path_location(py, location))
        .transpose()
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
    use super::{location_of, validate, validate_file};
}
