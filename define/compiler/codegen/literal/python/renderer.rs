use askama::Template;
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;

#[derive(FromPyObject)]
struct ClassReference {
    module_name: String,
    class_name: String,
}

impl ClassReference {
    /// Returns the name that code in `module_name` uses for this class.
    fn name_in_module(&self, module_name: &str) -> String {
        // A module's own classes are referenced while it is still loading, before
        // its name is bound on its parent package.
        if self.module_name == module_name {
            self.class_name.clone()
        } else {
            format!("{}.{}", self.module_name, self.class_name)
        }
    }
}

#[derive(FromPyObject)]
struct FunctionReference {
    module_name: String,
    function_name: String,
}

impl FunctionReference {
    /// Returns the name that code in `module_name` uses for this function.
    fn name_in_module(&self, module_name: &str) -> String {
        if self.module_name == module_name {
            self.function_name.clone()
        } else {
            format!("{}.{}", self.module_name, self.function_name)
        }
    }
}

#[derive(Template)]
#[template(path = "module_header.j2", escape = "none")]
struct ModuleHeader {
    imports: Vec<String>,
    typing_names: Vec<String>,
    needs_runtime_import: bool,
}

#[derive(FromPyObject, Template)]
#[template(path = "position_definition.j2", escape = "none")]
struct PositionDefinition {
    class_name: String,
    module_name: String,
    constraints: Vec<ClassReference>,
    implied_qualities: Vec<ClassReference>,
    value_type: String,
}

#[derive(FromPyObject)]
struct PositionExpression {
    local_position_name: Option<String>,
    from_contract_particle: bool,
    chain_elements: Vec<ChainElement>,
}

enum ChainElement {
    PositionFromPosition(ClassReference),
    ActionFromPosition(ClassReference),
    PositionFromAction(String, Option<String>),
    ImpliedAction(ClassReference),
    ImpliedPosition(ClassReference),
}

impl<'a, 'py> FromPyObject<'a, 'py> for ChainElement {
    type Error = PyErr;
    fn extract(object: pyo3::Borrowed<'a, 'py, PyAny>) -> PyResult<Self> {
        let accessor: String = object.getattr("accessor")?.getattr("name")?.extract()?;
        match accessor.as_str() {
            "POSITION_FROM_POSITION" => Ok(Self::PositionFromPosition(
                object.getattr("class_reference")?.extract()?,
            )),
            "ACTION_FROM_POSITION" => Ok(Self::ActionFromPosition(
                object.getattr("class_reference")?.extract()?,
            )),
            "POSITION_FROM_ACTION" => Ok(Self::PositionFromAction(
                object.getattr("typed_name")?.extract()?,
                object.getattr("value_type")?.extract()?,
            )),
            "IMPLIED_ACTION" => Ok(Self::ImpliedAction(
                object.getattr("class_reference")?.extract()?,
            )),
            "IMPLIED_POSITION" => Ok(Self::ImpliedPosition(
                object.getattr("class_reference")?.extract()?,
            )),
            _ => Err(PyRuntimeError::new_err(format!(
                "Unknown chain accessor: {accessor}"
            ))),
        }
    }
}

#[derive(FromPyObject)]
struct LocalPosition {
    name: String,
    local_typed_name: String,
    constraints: Vec<ClassReference>,
    value_type: String,
}

#[derive(FromPyObject)]
struct ParticleOperation {
    position: PositionExpression,
}

#[derive(FromPyObject)]
struct MoveParticle {
    position: PositionExpression,
    to_position: PositionExpression,
}

#[derive(FromPyObject)]
struct SetValue {
    position: PositionExpression,
    value: String,
}

#[derive(FromPyObject)]
struct SetValueFrom {
    position: PositionExpression,
    source_position: PositionExpression,
}

#[derive(FromPyObject)]
struct ContractArgument {
    class_name: String,
    forwarded_methods: Vec<String>,
}

#[derive(FromPyObject)]
struct RunAction {
    position: PositionExpression,
    destruction_contract: Option<ContractArgument>,
}

#[derive(FromPyObject)]
struct ContractContribution {
    position: PositionExpression,
    contract_method: String,
}

#[derive(FromPyObject)]
enum OperationArgument {
    Position(PositionExpression),
    Literal(String),
}

#[derive(FromPyObject)]
struct ExecuteOperation {
    function: FunctionReference,
    arguments: Vec<OperationArgument>,
    outputs: Vec<PositionExpression>,
    result_names: Vec<String>,
}

struct Statement {
    kind: StatementKind,
    operation_label: Option<String>,
}

enum StatementKind {
    LocalPosition(LocalPosition),
    CreateParticle(ParticleOperation),
    MoveParticle(MoveParticle),
    DestroyParticle(ParticleOperation),
    SetValue(SetValue),
    SetValueFrom(SetValueFrom),
    RunAction(RunAction),
    ContractContribution(ContractContribution),
    ExecuteOperation(ExecuteOperation),
}

impl<'a, 'py> FromPyObject<'a, 'py> for Statement {
    type Error = PyErr;
    fn extract(object: pyo3::Borrowed<'a, 'py, PyAny>) -> PyResult<Self> {
        Ok(Self {
            kind: object.extract()?,
            operation_label: object.getattr("operation_label")?.extract()?,
        })
    }
}

impl<'a, 'py> FromPyObject<'a, 'py> for StatementKind {
    type Error = PyErr;
    fn extract(object: pyo3::Borrowed<'a, 'py, PyAny>) -> PyResult<Self> {
        let kind: String = object.getattr("kind")?.getattr("name")?.extract()?;
        match kind.as_str() {
            "LOCAL_POSITION" => Ok(Self::LocalPosition(object.extract()?)),
            "CREATE_PARTICLE" => Ok(Self::CreateParticle(object.extract()?)),
            "MOVE_PARTICLE" => Ok(Self::MoveParticle(object.extract()?)),
            "DESTROY_PARTICLE" => Ok(Self::DestroyParticle(object.extract()?)),
            "SET_VALUE" => Ok(Self::SetValue(object.extract()?)),
            "SET_VALUE_FROM" => Ok(Self::SetValueFrom(object.extract()?)),
            "RUN_ACTION" => Ok(Self::RunAction(object.extract()?)),
            "RUN_CONTRACT_DESTRUCTORS" | "DESTROY_CONTRACT_CHILDREN" => {
                Ok(Self::ContractContribution(object.extract()?))
            }
            "EXECUTE_OPERATION" => Ok(Self::ExecuteOperation(object.extract()?)),
            _ => Err(PyRuntimeError::new_err(format!(
                "Unknown statement kind: {kind}"
            ))),
        }
    }
}

#[derive(FromPyObject)]
struct InterfacePosition {
    typed_name: String,
    constraints: Vec<ClassReference>,
    value_type: String,
}

#[derive(FromPyObject)]
struct ForwardedContribution {
    method_name: String,
    position: Option<PositionExpression>,
}

#[derive(FromPyObject)]
struct ContractMethod {
    name: String,
    forwarded: Vec<ForwardedContribution>,
    statements: Vec<Statement>,
}

#[derive(FromPyObject)]
struct ContractDefinition {
    class_name: String,
    base: ClassReference,
    forwarded_methods: Vec<String>,
    methods: Vec<ContractMethod>,
}

#[derive(FromPyObject, Template)]
#[template(path = "action_definition.j2", escape = "none")]
struct ActionDefinition {
    class_name: String,
    module_name: String,
    implied_qualities: Vec<ClassReference>,
    interface_positions: Vec<InterfacePosition>,
    statements: Vec<Statement>,
    contract_class_name: Option<String>,
    contract_methods: Vec<String>,
    contract_definitions: Vec<ContractDefinition>,
}

enum BinaryOperator {
    Add,
    Subtract,
    Multiply,
    And,
    Or,
    ExclusiveOr,
    BitwiseAnd,
    BitwiseOr,
    Equal,
    LessThan,
    LessThanOrEqual,
}

impl<'a, 'py> FromPyObject<'a, 'py> for BinaryOperator {
    type Error = PyErr;
    fn extract(object: pyo3::Borrowed<'a, 'py, PyAny>) -> PyResult<Self> {
        let name: String = object.getattr("name")?.extract()?;
        match name.as_str() {
            "ADD" => Ok(Self::Add),
            "SUBTRACT" => Ok(Self::Subtract),
            "MULTIPLY" => Ok(Self::Multiply),
            "AND" => Ok(Self::And),
            "OR" => Ok(Self::Or),
            "EXCLUSIVE_OR" => Ok(Self::ExclusiveOr),
            "BITWISE_AND" => Ok(Self::BitwiseAnd),
            "BITWISE_OR" => Ok(Self::BitwiseOr),
            "EQUAL" => Ok(Self::Equal),
            "LESS_THAN" => Ok(Self::LessThan),
            "LESS_THAN_OR_EQUAL" => Ok(Self::LessThanOrEqual),
            _ => Err(PyRuntimeError::new_err(format!(
                "Unknown binary operator: {name}"
            ))),
        }
    }
}

#[derive(FromPyObject)]
struct BinaryOperation {
    operator: BinaryOperator,
    left: String,
    right: String,
    result: String,
}

enum PrefixOperator {
    Negate,
    Not,
}

impl<'a, 'py> FromPyObject<'a, 'py> for PrefixOperator {
    type Error = PyErr;
    fn extract(object: pyo3::Borrowed<'a, 'py, PyAny>) -> PyResult<Self> {
        let name: String = object.getattr("name")?.extract()?;
        match name.as_str() {
            "NEGATE" => Ok(Self::Negate),
            "NOT" => Ok(Self::Not),
            _ => Err(PyRuntimeError::new_err(format!(
                "Unknown prefix operator: {name}"
            ))),
        }
    }
}

#[derive(FromPyObject)]
struct PrefixOperation {
    operator: PrefixOperator,
    operand: String,
    result: String,
}

#[derive(FromPyObject)]
struct Call {
    function: FunctionReference,
    arguments: Vec<String>,
    results: Vec<String>,
}

enum EncodingOperationStatement {
    BinaryOperation(BinaryOperation),
    PrefixOperation(PrefixOperation),
    Call(Call),
}

impl<'a, 'py> FromPyObject<'a, 'py> for EncodingOperationStatement {
    type Error = PyErr;
    fn extract(object: pyo3::Borrowed<'a, 'py, PyAny>) -> PyResult<Self> {
        let kind: String = object.getattr("kind")?.getattr("name")?.extract()?;
        match kind.as_str() {
            "BINARY_OPERATION" => Ok(Self::BinaryOperation(object.extract()?)),
            "PREFIX_OPERATION" => Ok(Self::PrefixOperation(object.extract()?)),
            "CALL" => Ok(Self::Call(object.extract()?)),
            _ => Err(PyRuntimeError::new_err(format!(
                "Unknown Encoding Operation statement kind: {kind}"
            ))),
        }
    }
}

#[derive(FromPyObject, Template)]
#[template(path = "encoding_operation_definition.j2", escape = "none")]
struct EncodingOperationDefinition {
    function_name: String,
    module_name: String,
    parameters: Vec<TypedLocalName>,
    statements: Vec<EncodingOperationStatement>,
    results: Vec<TypedLocalName>,
    return_last_statement: bool,
}

#[derive(FromPyObject)]
struct TypedLocalName {
    name: String,
    python_type: String,
}

#[derive(Template)]
#[template(path = "entry_point.j2", escape = "none")]
struct EntryPoint {
    entry_reference: ClassReference,
    trace_operations: bool,
}

fn render(template: impl Template) -> PyResult<String> {
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
    render(ModuleHeader {
        imports,
        typing_names,
        needs_runtime_import,
    })
}

#[pyfunction]
fn render_position(definition: PositionDefinition) -> PyResult<String> {
    render(definition)
}

#[pyfunction]
fn render_action(definition: ActionDefinition) -> PyResult<String> {
    render(definition)
}

#[pyfunction]
fn render_encoding_operation(definition: EncodingOperationDefinition) -> PyResult<String> {
    render(definition)
}

#[pyfunction]
fn render_entry_point(entry_reference: ClassReference, trace_operations: bool) -> PyResult<String> {
    render(EntryPoint {
        entry_reference,
        trace_operations,
    })
}

#[pymodule(gil_used = false)]
fn _templates(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(render_module_header, module)?)?;
    module.add_function(wrap_pyfunction!(render_position, module)?)?;
    module.add_function(wrap_pyfunction!(render_action, module)?)?;
    module.add_function(wrap_pyfunction!(render_encoding_operation, module)?)?;
    module.add_function(wrap_pyfunction!(render_entry_point, module)?)
}
