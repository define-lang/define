use askama::Template;
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use std::fmt;

/// The type of a constructor parameter, apart from whether it may be `None`.
#[pyclass(frozen, from_py_object)]
#[derive(Clone)]
enum FieldType {
    /// An AST class or a union of AST classes.
    Node {
        name: String,
    },
    /// A tuple of any length whose elements are all one AST class or union.
    Tuple {
        element_name: String,
    },
    /// A tuple of strings.
    StringTuple {},
    /// A frozen set of strings.
    StringSet {},
    /// A dict from strings to AST nodes.
    Dict {},
    String {},
    Integer {},
    Boolean {},
    /// An enum whose members are passed as Rust enum variants.
    Enum {
        name: String,
    },
    /// A `pathlib.PurePosixPath`.
    FilePath {},
}

/// Writes the Rust type of a parameter of this type.
impl fmt::Display for FieldType {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Node { name } => write!(formatter, "{name}<'py>"),
            Self::Tuple { element_name } => {
                write!(formatter, "NodeTuple<'py, {element_name}<'py>>")
            }
            Self::StringTuple {} => write!(formatter, "Bound<'py, PyTuple>"),
            Self::StringSet {} => write!(formatter, "Bound<'py, PyFrozenSet>"),
            Self::Dict {} => write!(formatter, "Bound<'py, PyDict>"),
            Self::String {} => write!(formatter, "Bound<'py, PyString>"),
            Self::Integer {} => write!(formatter, "Bound<'py, PyInt>"),
            Self::Boolean {} => write!(formatter, "bool"),
            Self::Enum { name } => write!(formatter, "{name}"),
            Self::FilePath {} => write!(formatter, "FilePath<'py>"),
        }
    }
}

/// A constructor parameter for a field.
#[pyclass(frozen, from_py_object)]
#[derive(Clone)]
struct Parameter {
    name: String,
    field_type: FieldType,
    /// Whether the field may be `None`.
    is_optional: bool,
}

#[pymethods]
impl Parameter {
    #[new]
    const fn new(name: String, field_type: FieldType, is_optional: bool) -> Self {
        Self {
            name,
            field_type,
            is_optional,
        }
    }
}

impl Parameter {
    /// The parameter's name in Rust, which leaves out the `_` that starts the
    /// name of a private field, since in Rust it would mark the parameter
    /// unused.
    fn rust_name(&self) -> &str {
        self.name.trim_start_matches('_')
    }

    fn rust_type(&self) -> String {
        if self.is_optional {
            format!("Option<{}>", self.field_type)
        } else {
            self.field_type.to_string()
        }
    }
}

/// The fields that a constructor sets.
#[pyclass(frozen, from_py_object)]
#[derive(Clone)]
struct Constructor {
    parameters: Vec<Parameter>,
    /// The names of the fields that the constructor sets to `None`, which are
    /// computed on first use.
    computed_on_first_use: Vec<String>,
}

#[pymethods]
impl Constructor {
    #[new]
    const fn new(parameters: Vec<Parameter>, computed_on_first_use: Vec<String>) -> Self {
        Self {
            parameters,
            computed_on_first_use,
        }
    }
}

impl Constructor {
    fn field_count(&self) -> usize {
        self.parameters.len() + self.computed_on_first_use.len()
    }
}

/// An AST class.
#[pyclass(frozen, from_py_object)]
#[derive(Clone)]
struct NodeClass {
    name: String,
    snake_case_name: String,
    /// The AST classes that this class inherits from.
    ancestors: Vec<String>,
    /// `None` for abstract and generic classes, and for classes with subclasses,
    /// which the parser never constructs.
    constructor: Option<Constructor>,
    /// Whether the class also gets a constructor that needs no `AstBuilder`.
    has_standalone_constructor: bool,
}

#[pymethods]
impl NodeClass {
    #[new]
    const fn new(
        name: String,
        snake_case_name: String,
        ancestors: Vec<String>,
        constructor: Option<Constructor>,
        has_standalone_constructor: bool,
    ) -> Self {
        Self {
            name,
            snake_case_name,
            ancestors,
            constructor,
            has_standalone_constructor,
        }
    }
}

/// A union of AST classes, named by its type alias when it has one.
#[pyclass(frozen, from_py_object, get_all)]
#[derive(Clone)]
struct NodeUnion {
    name: String,
    is_type_alias: bool,
    /// Every AST class that is an instance of the union, including subclasses.
    member_classes: Vec<String>,
}

#[pymethods]
impl NodeUnion {
    #[new]
    const fn new(name: String, is_type_alias: bool, member_classes: Vec<String>) -> Self {
        Self {
            name,
            is_type_alias,
            member_classes,
        }
    }
}

/// A member of an enum.
#[pyclass(frozen, from_py_object)]
#[derive(Clone)]
struct EnumMember {
    python_name: String,
    rust_name: String,
    /// The member's value, which is a string.
    value: String,
}

#[pymethods]
impl EnumMember {
    #[new]
    const fn new(python_name: String, rust_name: String, value: String) -> Self {
        Self {
            python_name,
            rust_name,
            value,
        }
    }
}

/// An enum used as a field type.
#[pyclass(frozen, from_py_object, get_all)]
#[derive(Clone)]
struct FieldEnum {
    name: String,
    snake_case_name: String,
    module_name: String,
    members: Vec<EnumMember>,
}

#[pymethods]
impl FieldEnum {
    #[new]
    const fn new(
        name: String,
        snake_case_name: String,
        module_name: String,
        members: Vec<EnumMember>,
    ) -> Self {
        Self {
            name,
            snake_case_name,
            module_name,
            members,
        }
    }
}

/// Everything that the AST node template renders.
#[pyclass(frozen, from_py_object)]
#[derive(Clone, Template)]
#[template(path = "ast_nodes.rs.j2", escape = "none")]
struct AstDescription {
    module_name: String,
    classes: Vec<NodeClass>,
    unions: Vec<NodeUnion>,
    enums: Vec<FieldEnum>,
}

#[pymethods]
impl AstDescription {
    #[new]
    const fn new(
        module_name: String,
        classes: Vec<NodeClass>,
        unions: Vec<NodeUnion>,
        enums: Vec<FieldEnum>,
    ) -> Self {
        Self {
            module_name,
            classes,
            unions,
            enums,
        }
    }
}

/// The constructors of the classes in an `AstDescription`, which are methods
/// of `AstBuilder`.
#[derive(Template)]
#[template(path = "ast_constructors.rs.j2", escape = "none")]
struct AstConstructors<'a> {
    description: &'a AstDescription,
}

/// An exception class that the parser can raise.
#[pyclass(frozen, from_py_object)]
#[derive(Clone)]
struct ParserException {
    name: String,
    snake_case_name: String,
    /// The names of the constructor's parameters after `location`, which are
    /// all strings.
    text_parameters: Vec<String>,
}

#[pymethods]
impl ParserException {
    #[new]
    const fn new(name: String, snake_case_name: String, text_parameters: Vec<String>) -> Self {
        Self {
            name,
            snake_case_name,
            text_parameters,
        }
    }
}

/// Everything that the syntax errors template renders.
#[pyclass(frozen, from_py_object)]
#[derive(Clone, Template)]
#[template(path = "syntax_errors.rs.j2", escape = "none")]
struct SyntaxErrorsDescription {
    module_name: String,
    exceptions: Vec<ParserException>,
}

#[pymethods]
impl SyntaxErrorsDescription {
    #[new]
    const fn new(module_name: String, exceptions: Vec<ParserException>) -> Self {
        Self {
            module_name,
            exceptions,
        }
    }
}

/// The type of a diagnostic's field after its location.
#[pyclass(frozen, from_py_object)]
#[derive(Clone)]
enum DiagnosticFieldType {
    Integer {},
    Text {},
}

/// A diagnostic's field after its location.
#[pyclass(frozen, from_py_object)]
#[derive(Clone)]
struct DiagnosticField {
    name: String,
    field_type: DiagnosticFieldType,
}

#[pymethods]
impl DiagnosticField {
    #[new]
    const fn new(name: String, field_type: DiagnosticFieldType) -> Self {
        Self { name, field_type }
    }
}

impl DiagnosticField {
    /// The Rust type of the parameter that takes the field's value.
    const fn rust_type(&self) -> &'static str {
        match self.field_type {
            DiagnosticFieldType::Integer {} => "usize",
            DiagnosticFieldType::Text {} => "&str",
        }
    }

    /// The expression that passes the parameter's value to the diagnostic's
    /// class.
    fn python_value(&self) -> String {
        match self.field_type {
            DiagnosticFieldType::Integer {} => format!("PyInt::new(self.py, {})", self.name),
            DiagnosticFieldType::Text {} => self.name.clone(),
        }
    }
}

/// A diagnostic class that the parser can report.
#[pyclass(frozen, from_py_object)]
#[derive(Clone)]
struct ParserDiagnostic {
    name: String,
    snake_case_name: String,
    /// The fields after `location`, in the order the class takes them.
    fields: Vec<DiagnosticField>,
}

#[pymethods]
impl ParserDiagnostic {
    #[new]
    const fn new(name: String, snake_case_name: String, fields: Vec<DiagnosticField>) -> Self {
        Self {
            name,
            snake_case_name,
            fields,
        }
    }
}

/// Everything that the parser diagnostics template renders.
#[pyclass(frozen, from_py_object)]
#[derive(Clone, Template)]
#[template(path = "parser_diagnostics.rs.j2", escape = "none")]
struct ParserDiagnosticsDescription {
    module_name: String,
    diagnostics: Vec<ParserDiagnostic>,
}

#[pymethods]
impl ParserDiagnosticsDescription {
    #[new]
    const fn new(module_name: String, diagnostics: Vec<ParserDiagnostic>) -> Self {
        Self {
            module_name,
            diagnostics,
        }
    }
}

#[pyfunction]
fn render_ast_nodes(description: AstDescription) -> PyResult<String> {
    description
        .render()
        .map_err(|error| PyRuntimeError::new_err(error.to_string()))
}

#[pyfunction]
fn render_ast_constructors(description: AstDescription) -> PyResult<String> {
    AstConstructors {
        description: &description,
    }
    .render()
    .map_err(|error| PyRuntimeError::new_err(error.to_string()))
}

#[pyfunction]
fn render_syntax_errors(description: SyntaxErrorsDescription) -> PyResult<String> {
    description
        .render()
        .map_err(|error| PyRuntimeError::new_err(error.to_string()))
}

#[pyfunction]
fn render_parser_diagnostics(description: ParserDiagnosticsDescription) -> PyResult<String> {
    description
        .render()
        .map_err(|error| PyRuntimeError::new_err(error.to_string()))
}

#[pymodule(gil_used = false)]
mod rust_renderer {
    #[pymodule_export]
    use super::{
        AstDescription, Constructor, DiagnosticField, DiagnosticFieldType, EnumMember, FieldEnum,
        FieldType, NodeClass, NodeUnion, Parameter, ParserDiagnostic, ParserDiagnosticsDescription,
        ParserException, SyntaxErrorsDescription, render_ast_constructors, render_ast_nodes,
        render_parser_diagnostics, render_syntax_errors,
    };
}
