use askama::Template;
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use template_context::{
    ActionDefinition, ClassReference, EncodingOperationDefinition, PositionDefinition,
};

mod template_context;

mod filters {
    /// Writes the text as a Python string literal.
    #[askama::filter_fn]
    pub fn python_string<T: std::fmt::Display>(
        text: T,
        _: &dyn askama::Values,
    ) -> askama::Result<String> {
        let text = text.to_string();
        // Python formatters such as ruff and Black pick whichever quote needs
        // fewer escapes, preferring double quotes on a tie, so generated code
        // picks the same way to stay unchanged when formatted.
        let quote = if text.matches('"').count() > text.matches('\'').count() {
            '\''
        } else {
            '"'
        };
        // Define source cannot contain any other character that a Python string
        // literal must escape.
        let escaped = text
            .replace('\\', "\\\\")
            .replace(quote, &format!("\\{quote}"))
            .replace('\n', "\\n");
        Ok(format!("{quote}{escaped}{quote}"))
    }
}

#[derive(Template)]
#[template(path = "module_header.j2", escape = "none")]
struct ModuleHeader {
    imports: Vec<String>,
    typing_names: Vec<String>,
    needs_runtime_import: bool,
}

#[derive(Template)]
#[template(path = "entry_point.j2", escape = "none")]
struct EntryPoint {
    entry_reference: ClassReference,
    trace_operations: bool,
}

fn render(template: &impl Template) -> PyResult<String> {
    template
        .render()
        .map_err(|error| PyRuntimeError::new_err(error.to_string()))
}

#[pyfunction]
fn render_module_header(
    imports: Vec<String>,
    typing_names: Vec<String>,
    needs_runtime_import: bool,
) -> PyResult<String> {
    render(&ModuleHeader {
        imports,
        typing_names,
        needs_runtime_import,
    })
}

#[pyfunction]
fn render_position(definition: &Bound<'_, PositionDefinition>) -> PyResult<String> {
    render(definition.get())
}

#[pyfunction]
fn render_action(definition: &Bound<'_, ActionDefinition>) -> PyResult<String> {
    render(definition.get())
}

#[pyfunction]
fn render_encoding_operation(
    definition: &Bound<'_, EncodingOperationDefinition>,
) -> PyResult<String> {
    render(definition.get())
}

#[pyfunction]
fn render_entry_point(entry_reference: ClassReference, trace_operations: bool) -> PyResult<String> {
    render(&EntryPoint {
        entry_reference,
        trace_operations,
    })
}

#[pymodule(gil_used = false)]
mod renderer {
    #[pymodule_export]
    use super::template_context::{
        ActionDefinition, ActionStatement, BinaryOperator, ChainElement, ClassReference,
        DestructionContractArgument, DestructionContractDefinition, DestructionContractMethod,
        EncodingOperationDefinition, EncodingOperationStatement, ExpressionOperator,
        ForwardedContribution, FunctionReference, GuaranteedParticleDestructors, InterfacePosition,
        PositionDefinition, PositionExpression, PrefixOperator, TypedLocalName,
    };
    #[pymodule_export]
    use super::{
        render_action, render_encoding_operation, render_entry_point, render_module_header,
        render_position,
    };
}
