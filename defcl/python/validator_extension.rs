//! The Python module that validates DCL files: `defcl.python.validator`.

use defcl_parser::{SyntaxError, SyntaxErrorKind};
use defcl_semantics::{FileDescriptorSet, SemanticError, SemanticErrorKind};
use defcl_validator::ValidationError;
use prost::Message as _;
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::types::{PyBytes, PyString, PyType};
use source_rendering_capsule::new_source_location;
use std::path::Path;

/// The Python classes that the module returns and raises.
struct PythonClasses {
    syntax_diagnostic: Py<PyType>,
    unexpected_character_diagnostic: Py<PyType>,
    syntax_diagnostic_kind: Py<PyType>,
    invalid_schema_error: Py<PyType>,
    semantic_diagnostic: Py<PyType>,
    unknown_field_name_diagnostic: Py<PyType>,
    unknown_enum_value_diagnostic: Py<PyType>,
    integer_out_of_range_diagnostic: Py<PyType>,
    float_out_of_range_diagnostic: Py<PyType>,
    second_field_of_oneof_diagnostic: Py<PyType>,
    semantic_diagnostic_kind: Py<PyType>,
}

static PYTHON_CLASSES: PyOnceLock<PythonClasses> = PyOnceLock::new();

impl PythonClasses {
    fn get(py: Python<'_>) -> PyResult<&'static Self> {
        PYTHON_CLASSES.get_or_try_init(py, || Self::import(py))
    }

    fn import(py: Python<'_>) -> PyResult<Self> {
        let errors = py.import("defcl.python.errors")?;
        let error_types = py.import("defcl.python.error_types")?;
        Ok(Self {
            syntax_diagnostic: class(&errors, "SyntaxDiagnostic")?,
            unexpected_character_diagnostic: class(&errors, "UnexpectedCharacterDiagnostic")?,
            syntax_diagnostic_kind: class(&error_types, "SyntaxDiagnosticKind")?,
            invalid_schema_error: class(&errors, "InvalidSchemaError")?,
            semantic_diagnostic: class(&errors, "SemanticDiagnostic")?,
            unknown_field_name_diagnostic: class(&errors, "UnknownFieldNameDiagnostic")?,
            unknown_enum_value_diagnostic: class(&errors, "UnknownEnumValueDiagnostic")?,
            integer_out_of_range_diagnostic: class(&errors, "IntegerOutOfRangeDiagnostic")?,
            float_out_of_range_diagnostic: class(&errors, "FloatOutOfRangeDiagnostic")?,
            second_field_of_oneof_diagnostic: class(&errors, "SecondFieldOfOneofDiagnostic")?,
            semantic_diagnostic_kind: class(&error_types, "SemanticDiagnosticKind")?,
        })
    }

    fn invalid_schema_error(&self, py: Python<'_>, error: &impl ToString) -> PyErr {
        raise(
            self.invalid_schema_error
                .bind(py)
                .call1((error.to_string(),)),
        )
    }

    fn syntax_diagnostic<'py>(
        &self,
        py: Python<'py>,
        error: &SyntaxError,
        file_path: Option<&Bound<'py, PyString>>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let kind: &'static str = error.kind.into();
        let kind = self.syntax_diagnostic_kind.bind(py).getattr(kind)?;
        let message = error.to_string();
        let location = new_source_location(py, error.location, file_path)?;
        if let SyntaxErrorKind::UnexpectedCharacter { character } = error.kind {
            return self
                .unexpected_character_diagnostic
                .bind(py)
                .call1((message, location, kind, character));
        }
        self.syntax_diagnostic
            .bind(py)
            .call1((message, location, kind))
    }

    fn semantic_diagnostic<'py>(
        &self,
        py: Python<'py>,
        error: &SemanticError,
        file_path: Option<&Bound<'py, PyString>>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let kind: &'static str = (&error.kind).into();
        let kind = self.semantic_diagnostic_kind.bind(py).getattr(kind)?;
        let message = error.to_string();
        let location = new_source_location(py, error.location, file_path)?;
        let field_name = &error.field_name;
        match &error.kind {
            SemanticErrorKind::UnknownFieldName { message_type } => self
                .unknown_field_name_diagnostic
                .bind(py)
                .call1((message, location, kind, field_name, message_type)),
            SemanticErrorKind::UnknownEnumValue { enum_type } => self
                .unknown_enum_value_diagnostic
                .bind(py)
                .call1((message, location, kind, field_name, enum_type)),
            SemanticErrorKind::IntegerOutOfRange { field_type } => self
                .integer_out_of_range_diagnostic
                .bind(py)
                .call1((message, location, kind, field_name, field_type.to_string())),
            SemanticErrorKind::FloatOutOfRange { field_type } => self
                .float_out_of_range_diagnostic
                .bind(py)
                .call1((message, location, kind, field_name, field_type.to_string())),
            SemanticErrorKind::SecondFieldOfOneof { oneof } => self
                .second_field_of_oneof_diagnostic
                .bind(py)
                .call1((message, location, kind, field_name, oneof)),
            _ => self
                .semantic_diagnostic
                .bind(py)
                .call1((message, location, kind, field_name)),
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
/// `FileDescriptorSet` `descriptor_set`, and returns a `SyntaxDiagnostic` for
/// its first syntax error, or else a `SemanticDiagnostic` for each semantic
/// error, in source order. Raises `InvalidSchemaError` if the descriptor set
/// cannot be decoded or has no such message type.
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
        None,
    )
}

/// Validates the DCL file at `path` as `validate` validates its text, registers
/// it with the `SourceMap` `source_map`, and returns the file's text with the
/// diagnostics, whose locations are in the file at `path`. Raises `OSError` if
/// the file cannot be read.
#[pyfunction]
fn validate_file<'py>(
    path: &Bound<'py, PyString>,
    source_map: &Bound<'py, PyAny>,
    descriptor_set: &[u8],
    top_level_message_type: &str,
) -> PyResult<(String, Vec<Bound<'py, PyAny>>)> {
    let py = path.py();
    let classes = PythonClasses::get(py)?;
    let descriptor_set = decode_descriptor_set(py, classes, descriptor_set)?;
    let (source, result) = defcl_validator::validate_file(
        Path::new(path.to_str()?),
        descriptor_set,
        top_level_message_type,
    )?;
    let _: Bound<'_, PyAny> =
        source_map.call_method1("register_file", (path, PyBytes::new(py, source.as_bytes())))?;
    Ok((source, diagnostics(py, classes, result, Some(path))?))
}

fn decode_descriptor_set(
    py: Python<'_>,
    classes: &PythonClasses,
    descriptor_set: &[u8],
) -> PyResult<FileDescriptorSet> {
    FileDescriptorSet::decode(descriptor_set)
        .map_err(|error| classes.invalid_schema_error(py, &error))
}

/// The `DclDiagnostic`s of `result`'s syntax or semantic errors, in the file at
/// `file_path` if the text is from a file, or the exception that its schema
/// error raises.
fn diagnostics<'py>(
    py: Python<'py>,
    classes: &PythonClasses,
    result: Result<(), ValidationError>,
    file_path: Option<&Bound<'py, PyString>>,
) -> PyResult<Vec<Bound<'py, PyAny>>> {
    match result {
        Ok(()) => Ok(Vec::new()),
        Err(ValidationError::Schema(error)) => Err(classes.invalid_schema_error(py, &error)),
        Err(ValidationError::Syntax(error)) => {
            Ok(vec![classes.syntax_diagnostic(py, &error, file_path)?])
        }
        Err(ValidationError::Semantic(errors)) => errors
            .iter()
            .map(|error| classes.semantic_diagnostic(py, error, file_path))
            .collect(),
    }
}

#[pymodule(gil_used = false)]
mod validator {
    #[pymodule_export]
    use super::{validate, validate_file};
}
