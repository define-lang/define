//! The Python module that validates defcl files: `defcl.python.validator`.

use defcl_parser::{FieldPathElement, ParsedFile, SyntaxError, SyntaxErrorKind};
use defcl_semantics::{FileDescriptorSet, SemanticError, SemanticErrorKind};
use defcl_validator::FileErrors;
use prost::Message as _;
use pyo3::exceptions::{PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::sync::PyOnceLock;
use pyo3::types::{PyInt, PyString, PyTuple, PyType};
use source_rendering_capsule::new_source_location;
use std::path::Path;

/// The Python classes that the module returns and raises.
struct PythonClasses {
    syntax_diagnostic: Py<PyType>,
    unexpected_character_diagnostic: Py<PyType>,
    control_character_diagnostic: Py<PyType>,
    invisible_character_diagnostic: Py<PyType>,
    invalid_encoding_diagnostic: Py<PyType>,
    wrong_indentation_diagnostic: Py<PyType>,
    syntax_diagnostic_kind: Py<PyType>,
    invalid_schema_error: Py<PyType>,
    semantic_diagnostic: Py<PyType>,
    unknown_field_name_diagnostic: Py<PyType>,
    unknown_enum_value_diagnostic: Py<PyType>,
    integer_out_of_range_diagnostic: Py<PyType>,
    float_out_of_range_diagnostic: Py<PyType>,
    second_field_of_oneof_diagnostic: Py<PyType>,
    field_out_of_order_diagnostic: Py<PyType>,
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
            control_character_diagnostic: class(&errors, "ControlCharacterDiagnostic")?,
            invisible_character_diagnostic: class(&errors, "InvisibleCharacterDiagnostic")?,
            invalid_encoding_diagnostic: class(&errors, "InvalidEncodingDiagnostic")?,
            wrong_indentation_diagnostic: class(&errors, "WrongIndentationDiagnostic")?,
            syntax_diagnostic_kind: class(&error_types, "SyntaxDiagnosticKind")?,
            invalid_schema_error: class(&errors, "InvalidSchemaError")?,
            semantic_diagnostic: class(&errors, "SemanticDiagnostic")?,
            unknown_field_name_diagnostic: class(&errors, "UnknownFieldNameDiagnostic")?,
            unknown_enum_value_diagnostic: class(&errors, "UnknownEnumValueDiagnostic")?,
            integer_out_of_range_diagnostic: class(&errors, "IntegerOutOfRangeDiagnostic")?,
            float_out_of_range_diagnostic: class(&errors, "FloatOutOfRangeDiagnostic")?,
            second_field_of_oneof_diagnostic: class(&errors, "SecondFieldOfOneofDiagnostic")?,
            field_out_of_order_diagnostic: class(&errors, "FieldOutOfOrderDiagnostic")?,
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
        let location = error
            .location
            .map(|location| new_source_location(py, location, file_path))
            .transpose()?;
        match error.kind {
            SyntaxErrorKind::UnexpectedCharacter { character } => self
                .unexpected_character_diagnostic
                .bind(py)
                .call1((message, location, file_path, kind, character)),
            SyntaxErrorKind::ControlCharacter { character } => self
                .control_character_diagnostic
                .bind(py)
                .call1((message, location, file_path, kind, character)),
            SyntaxErrorKind::InvisibleCharacter { character } => self
                .invisible_character_diagnostic
                .bind(py)
                .call1((message, location, file_path, kind, character)),
            SyntaxErrorKind::InvalidEncoding { byte } => self
                .invalid_encoding_diagnostic
                .bind(py)
                .call1((message, location, file_path, kind, byte)),
            SyntaxErrorKind::WrongIndentation { expected_spaces } => self
                .wrong_indentation_diagnostic
                .bind(py)
                .call1((message, location, file_path, kind, expected_spaces)),
            _ => self
                .syntax_diagnostic
                .bind(py)
                .call1((message, location, file_path, kind)),
        }
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
                .call1((message, location, file_path, kind, field_name, message_type)),
            SemanticErrorKind::UnknownEnumValue { enum_type } => self
                .unknown_enum_value_diagnostic
                .bind(py)
                .call1((message, location, file_path, kind, field_name, enum_type)),
            SemanticErrorKind::IntegerOutOfRange { field_type } => {
                self.integer_out_of_range_diagnostic.bind(py).call1((
                    message,
                    location,
                    file_path,
                    kind,
                    field_name,
                    field_type.to_string(),
                ))
            }
            SemanticErrorKind::FloatOutOfRange { field_type } => {
                self.float_out_of_range_diagnostic.bind(py).call1((
                    message,
                    location,
                    file_path,
                    kind,
                    field_name,
                    field_type.to_string(),
                ))
            }
            SemanticErrorKind::SecondFieldOfOneof { oneof } => self
                .second_field_of_oneof_diagnostic
                .bind(py)
                .call1((message, location, file_path, kind, field_name, oneof)),
            SemanticErrorKind::FieldOutOfOrder { later_field } => self
                .field_out_of_order_diagnostic
                .bind(py)
                .call1((message, location, file_path, kind, field_name, later_field)),
            _ => self
                .semantic_diagnostic
                .bind(py)
                .call1((message, location, file_path, kind, field_name)),
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

/// Validates the defcl text `source` against the schema whose top-level message
/// type has the full name `top_level_message_type` in the binary
/// `FileDescriptorSet` `descriptor_set`. Returns whether the text still means
/// exactly one message despite its diagnostics, with a `SyntaxDiagnostic` for
/// each of its syntax errors, in the order the parser found them, then, unless
/// one of them stopped the parse, a `SemanticDiagnostic` for each semantic
/// error, in source order. Raises `InvalidSchemaError` if the descriptor set
/// cannot be decoded or has no such message type.
#[pyfunction]
fn validate<'py>(
    py: Python<'py>,
    source: &str,
    descriptor_set: &[u8],
    top_level_message_type: &str,
) -> PyResult<(bool, Vec<Bound<'py, PyAny>>)> {
    let classes = PythonClasses::get(py)?;
    let descriptor_set = decode_descriptor_set(py, classes, descriptor_set)?;
    let errors = defcl_validator::validate(source, descriptor_set, top_level_message_type)
        .map_err(|error| classes.invalid_schema_error(py, &error))?;
    Ok((errors.understood, diagnostics(py, classes, &errors, None)?))
}

/// Validates the defcl file at `path` as `validate` validates its text, registers
/// it with the `SourceMap` `source_map`, and returns the `ValidatedFile` if it
/// still means exactly one message, or else `None`, with the diagnostics, whose
/// locations are in the file at `path`. Raises `OSError` if the file cannot be
/// read.
#[pyfunction]
fn validate_file<'py>(
    path: &Bound<'py, PyString>,
    source_map: &Bound<'py, PyAny>,
    descriptor_set: &[u8],
    top_level_message_type: &str,
) -> PyResult<(Option<ValidatedFile>, Vec<Bound<'py, PyAny>>)> {
    let py = path.py();
    let classes = PythonClasses::get(py)?;
    let descriptor_set = decode_descriptor_set(py, classes, descriptor_set)?;
    let (source, errors) = defcl_validator::validate_file(
        Path::new(path.to_str()?),
        descriptor_set,
        top_level_message_type,
    )?;
    let bytes = match &source {
        Ok(parsed) => parsed.text.as_bytes(),
        Err(bytes) => bytes,
    };
    let _: Bound<'_, PyAny> = source_map.call_method1(
        "register_file_digest",
        (path, source_rendering::source_digest(bytes)),
    )?;
    let errors = errors.map_err(|error| classes.invalid_schema_error(py, &error))?;
    let diagnostics = diagnostics(py, classes, &errors, Some(path))?;
    // Only a file whose parse a syntax error did not stop means exactly one
    // message, so an understood file always has a syntax tree.
    let validated = if errors.understood
        && let Ok(parsed) = source
        && let Some(file) = parsed.file
    {
        Some(ValidatedFile {
            text: parsed.text,
            file,
            path: path.clone().unbind(),
        })
    } else {
        None
    };
    Ok((validated, diagnostics))
}

/// The element of a field path that `object` is: a field name if it is a
/// `str`, or an index if it is an `int`.
fn field_path_element<'object>(
    object: &'object Bound<'_, PyAny>,
) -> PyResult<FieldPathElement<'object>> {
    if let Ok(name) = object.cast::<PyString>() {
        return Ok(FieldPathElement::Field(name.to_str()?));
    }
    // A bool is also an int, but is not an index.
    if let Ok(index) = object.cast_exact::<PyInt>() {
        return Ok(FieldPathElement::Index(index.extract()?));
    }
    Err(PyTypeError::new_err(
        "a field path element must be a str or an int",
    ))
}

/// A defcl file that still means exactly one message: its text, and the
/// syntax tree that validating it parsed, so that finding the location of a
/// field does not parse it again.
#[pyclass(frozen, name = "ValidatedFile", module = "defcl.python.validator")]
struct ValidatedFile {
    text: String,
    file: ParsedFile,
    path: Py<PyString>,
}

#[pymethods]
impl ValidatedFile {
    /// The file's text, copied into a new `str`.
    fn text(&self) -> &str {
        &self.text
    }

    /// The location of the field that `field_path` names: a tuple of field
    /// names and indices of repeated values' elements whose first element is a
    /// top-level message. A field that appears in the file is located at its
    /// value. A field that is missing from the file is located at the name of
    /// the nearest field on its path that appears in the file. Raises
    /// `ValueError` if the path's top-level message does not appear in the
    /// file.
    fn location_of<'py>(&self, field_path: &Bound<'py, PyTuple>) -> PyResult<Bound<'py, PyAny>> {
        let elements = field_path
            .as_slice()
            .iter()
            .map(field_path_element)
            .collect::<PyResult<Vec<_>>>()?;
        let location = self
            .file
            .location_of(&self.text, &elements)
            .map_err(|error| PyValueError::new_err(error.to_string()))?;
        let path = self.path.bind(field_path.py());
        new_source_location(path.py(), location, Some(path))
    }
}

fn decode_descriptor_set(
    py: Python<'_>,
    classes: &PythonClasses,
    descriptor_set: &[u8],
) -> PyResult<FileDescriptorSet> {
    FileDescriptorSet::decode(descriptor_set)
        .map_err(|error| classes.invalid_schema_error(py, &error))
}

/// The `DefclDiagnostic`s of `errors`' syntax errors and then its semantic
/// errors, in the file at `file_path` if the text is from a file.
fn diagnostics<'py>(
    py: Python<'py>,
    classes: &PythonClasses,
    errors: &FileErrors,
    file_path: Option<&Bound<'py, PyString>>,
) -> PyResult<Vec<Bound<'py, PyAny>>> {
    let mut diagnostics =
        Vec::with_capacity(errors.syntax_errors.len() + errors.semantic_errors.len());
    for error in &errors.syntax_errors {
        diagnostics.push(classes.syntax_diagnostic(py, error, file_path)?);
    }
    for error in &errors.semantic_errors {
        diagnostics.push(classes.semantic_diagnostic(py, error, file_path)?);
    }
    Ok(diagnostics)
}

#[pymodule(gil_used = false)]
mod validator {
    #[pymodule_export]
    use super::{ValidatedFile, validate, validate_file};
}
