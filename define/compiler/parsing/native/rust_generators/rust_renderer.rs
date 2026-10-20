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
            Self::String {} => write!(formatter, "Bound<'py, PyString>"),
            Self::Integer {} => write!(formatter, "Bound<'py, PyInt>"),
            Self::Boolean {} => write!(formatter, "bool"),
            Self::Enum { name } => write!(formatter, "{name}"),
            Self::FilePath {} => write!(formatter, "FilePath<'py>"),
        }
    }
}

/// A constructor parameter for a field that is not derived.
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
    fn rust_type(&self) -> String {
        if self.is_optional {
            format!("Option<{}>", self.field_type)
        } else {
            self.field_type.to_string()
        }
    }
}

/// How to call a class. The first `positional_count` parameters are passed by
/// position and the rest by keyword.
#[pyclass(frozen, from_py_object)]
#[derive(Clone)]
struct Constructor {
    parameters: Vec<Parameter>,
    positional_count: usize,
}

#[pymethods]
impl Constructor {
    #[new]
    const fn new(parameters: Vec<Parameter>, positional_count: usize) -> Self {
        Self {
            parameters,
            positional_count,
        }
    }
}

impl Constructor {
    fn positional_parameters(&self) -> &[Parameter] {
        &self.parameters[..self.positional_count]
    }

    fn keyword_parameters(&self) -> &[Parameter] {
        &self.parameters[self.positional_count..]
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
    /// `None` for abstract and generic classes, which are never constructed.
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
}

#[pymethods]
impl EnumMember {
    #[new]
    const fn new(python_name: String, rust_name: String) -> Self {
        Self {
            python_name,
            rust_name,
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

/// A diagnostic class that the parser can report.
#[pyclass(frozen, from_py_object)]
#[derive(Clone)]
struct ParserDiagnostic {
    name: String,
    snake_case_name: String,
    /// The names of the fields after `location`, which are all integers.
    integer_fields: Vec<String>,
}

#[pymethods]
impl ParserDiagnostic {
    #[new]
    const fn new(name: String, snake_case_name: String, integer_fields: Vec<String>) -> Self {
        Self {
            name,
            snake_case_name,
            integer_fields,
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
        AstDescription, Constructor, EnumMember, FieldEnum, FieldType, NodeClass, NodeUnion,
        Parameter, ParserDiagnostic, ParserDiagnosticsDescription, ParserException,
        SyntaxErrorsDescription, render_ast_nodes, render_parser_diagnostics, render_syntax_errors,
    };
}
