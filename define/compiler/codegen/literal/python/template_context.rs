//! The data that the Python code generator gives the templates, and the
//! templates of the definitions that it renders.

use crate::filters;
use askama::Template;
use pyo3::prelude::*;
use std::collections::HashSet;

/// A reference to a generated class, including its module location.
#[pyclass(frozen, from_py_object, get_all)]
#[derive(Clone)]
pub struct ClassReference {
    pub class_name: String,
    pub module_name: String,
}

#[pymethods]
impl ClassReference {
    #[new]
    const fn new(class_name: String, module_name: String) -> Self {
        Self {
            class_name,
            module_name,
        }
    }
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

/// A reference to a Python function, including its module location.
#[pyclass(frozen, from_py_object, get_all)]
#[derive(Clone)]
pub struct FunctionReference {
    function_name: String,
    module_name: String,
}

#[pymethods]
impl FunctionReference {
    #[new]
    const fn new(function_name: String, module_name: String) -> Self {
        Self {
            function_name,
            module_name,
        }
    }
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

/// A position definition class.
#[pyclass(frozen, from_py_object, get_all)]
#[derive(Clone, Template)]
#[template(path = "position_definition.j2", escape = "none")]
pub struct PositionDefinition {
    class_name: String,
    module_name: String,
    constraints: Vec<ClassReference>,
    implied_qualities: Vec<ClassReference>,
    value_type: String,
    /// The modules, other than its own, that the definition uses.
    imports: HashSet<String>,
}

#[pymethods]
impl PositionDefinition {
    #[new]
    const fn new(
        class_name: String,
        module_name: String,
        constraints: Vec<ClassReference>,
        implied_qualities: Vec<ClassReference>,
        value_type: String,
        imports: HashSet<String>,
    ) -> Self {
        Self {
            class_name,
            module_name,
            constraints,
            implied_qualities,
            value_type,
            imports,
        }
    }
}

/// How a position expression gets from what comes before an element in its
/// chain to the position or action that the element names.
#[pyclass(frozen, from_py_object)]
#[derive(Clone)]
pub enum ChainElement {
    PositionFromPosition {
        class_reference: ClassReference,
    },
    ActionFromPosition {
        class_reference: ClassReference,
    },
    /// An interface position.
    PositionFromAction {
        typed_name: String,
        /// The Python type of the position's value, when the expression uses
        /// it.
        value_type: Option<String>,
    },
    ImpliedAction {
        class_reference: ClassReference,
    },
    ImpliedPosition {
        class_reference: ClassReference,
    },
}

/// An expression for a position or action in generated code.
#[pyclass(frozen, from_py_object)]
#[derive(Clone)]
pub struct PositionExpression {
    local_position_name: Option<String>,
    chain_elements: Vec<ChainElement>,
    from_contract_particle: bool,
}

#[pymethods]
impl PositionExpression {
    #[new]
    const fn new(
        local_position_name: Option<String>,
        chain_elements: Vec<ChainElement>,
        from_contract_particle: bool,
    ) -> Self {
        Self {
            local_position_name,
            chain_elements,
            from_contract_particle,
        }
    }
}

/// A per-invocation contract object and the contributions it forwards.
#[pyclass(frozen, from_py_object)]
#[derive(Clone)]
pub struct DestructionContractArgument {
    class_name: String,
    forwarded_methods: Vec<String>,
}

#[pymethods]
impl DestructionContractArgument {
    #[new]
    const fn new(class_name: String, forwarded_methods: Vec<String>) -> Self {
        Self {
            class_name,
            forwarded_methods,
        }
    }
}

/// A value that an Operation Execution Statement passes to its function.
#[derive(Clone, FromPyObject, IntoPyObject)]
pub enum OperationArgument {
    /// A position whose value is read.
    Position(PositionExpression),
    /// A literal already in the view's encoding.
    Literal(String),
}

/// A statement in an action, or in a method of its generated class. An
/// `operation_label` is the trace label of the operation that the statement
/// performs, if the trace records it.
#[pyclass(frozen, from_py_object)]
#[derive(Clone)]
pub enum ActionStatement {
    LocalPosition {
        name: String,
        local_typed_name: String,
        constraints: Vec<ClassReference>,
        value_type: String,
    },
    CreateParticle {
        position: PositionExpression,
        operation_label: Option<String>,
    },
    MoveParticle {
        position: PositionExpression,
        to_position: PositionExpression,
        operation_label: Option<String>,
    },
    DestroyParticle {
        position: PositionExpression,
        operation_label: Option<String>,
    },
    /// Sets the value of a particle from a literal.
    SetValue {
        position: PositionExpression,
        value: String,
        operation_label: Option<String>,
    },
    /// Sets the value of a particle from another particle's value.
    SetValueFrom {
        position: PositionExpression,
        source_position: PositionExpression,
        operation_label: Option<String>,
    },
    /// Runs an action with its destruction contract, if it has one.
    #[pyo3(constructor = (position, destruction_contract = None))]
    RunAction {
        position: PositionExpression,
        destruction_contract: Option<DestructionContractArgument>,
    },
    /// Runs the Destructors for what an action left at and below a position.
    RunGuaranteedParticleDestructors {
        action: ClassReference,
        method_name: String,
        position: PositionExpression,
    },
    /// Runs a contribution of the caller's for a contracted particle.
    ContractContribution {
        position: PositionExpression,
        contract_method: String,
    },
    /// Calls the function of the Encoding Operation that an Operation
    /// Execution Statement executes.
    ExecuteOperation {
        function: FunctionReference,
        arguments: Vec<OperationArgument>,
        /// The positions whose values are set, in the order the function
        /// returns them.
        outputs: Vec<PositionExpression>,
        /// The local names that hold the returned values when there is more
        /// than one.
        result_names: Vec<String>,
        operation_label: Option<String>,
    },
}

impl ActionStatement {
    const fn operation_label(&self) -> Option<&String> {
        match self {
            Self::CreateParticle {
                operation_label, ..
            }
            | Self::MoveParticle {
                operation_label, ..
            }
            | Self::DestroyParticle {
                operation_label, ..
            }
            | Self::SetValue {
                operation_label, ..
            }
            | Self::SetValueFrom {
                operation_label, ..
            }
            | Self::ExecuteOperation {
                operation_label, ..
            } => operation_label.as_ref(),
            Self::LocalPosition { .. }
            | Self::RunAction { .. }
            | Self::RunGuaranteedParticleDestructors { .. }
            | Self::ContractContribution { .. } => None,
        }
    }
}

/// An interface position of an action definition.
#[pyclass(frozen, from_py_object, get_all)]
#[derive(Clone)]
pub struct InterfacePosition {
    typed_name: String,
    constraints: Vec<ClassReference>,
    value_type: String,
}

#[pymethods]
impl InterfacePosition {
    #[new]
    const fn new(typed_name: String, constraints: Vec<ClassReference>, value_type: String) -> Self {
        Self {
            typed_name,
            constraints,
            value_type,
        }
    }
}

/// A caller contribution applied to its contracted particle.
#[pyclass(frozen, from_py_object)]
#[derive(Clone)]
pub struct ForwardedContribution {
    method_name: String,
    position: Option<PositionExpression>,
}

#[pymethods]
impl ForwardedContribution {
    #[new]
    const fn new(method_name: String, position: Option<PositionExpression>) -> Self {
        Self {
            method_name,
            position,
        }
    }
}

/// One named contribution to a callee's destruction.
#[pyclass(frozen, from_py_object)]
#[derive(Clone)]
pub struct DestructionContractMethod {
    name: String,
    forwarded: Vec<ForwardedContribution>,
    statements: Vec<ActionStatement>,
}

#[pymethods]
impl DestructionContractMethod {
    #[new]
    const fn new(
        name: String,
        forwarded: Vec<ForwardedContribution>,
        statements: Vec<ActionStatement>,
    ) -> Self {
        Self {
            name,
            forwarded,
            statements,
        }
    }
}

/// Methods implementing caller-contributed destruction work.
#[pyclass(frozen, from_py_object, get_all)]
#[derive(Clone)]
pub struct DestructionContractDefinition {
    class_name: String,
    base: ClassReference,
    forwarded_methods: Vec<String>,
    methods: Vec<DestructionContractMethod>,
}

#[pymethods]
impl DestructionContractDefinition {
    #[new]
    const fn new(
        class_name: String,
        base: ClassReference,
        forwarded_methods: Vec<String>,
        methods: Vec<DestructionContractMethod>,
    ) -> Self {
        Self {
            class_name,
            base,
            forwarded_methods,
            methods,
        }
    }
}

/// The method that runs the Destructors for what an action left at and below
/// one position.
#[pyclass(frozen, from_py_object)]
#[derive(Clone)]
pub struct GuaranteedParticleDestructors {
    method_name: String,
    statements: Vec<ActionStatement>,
}

#[pymethods]
impl GuaranteedParticleDestructors {
    #[new]
    const fn new(method_name: String, statements: Vec<ActionStatement>) -> Self {
        Self {
            method_name,
            statements,
        }
    }
}

/// An action definition class and the statements it runs.
#[pyclass(frozen, from_py_object, get_all)]
#[derive(Clone, Template)]
#[template(path = "action_definition.j2", escape = "none")]
pub struct ActionDefinition {
    class_name: String,
    module_name: String,
    statements: Vec<ActionStatement>,
    interface_positions: Vec<InterfacePosition>,
    implied_qualities: Vec<ClassReference>,
    trace_operations: bool,
    /// The modules, other than its own, that the definition uses.
    imports: HashSet<String>,
    contract_class_name: Option<String>,
    contract_methods: Vec<String>,
    contract_definitions: Vec<DestructionContractDefinition>,
    guaranteed_particle_destructors: Vec<GuaranteedParticleDestructors>,
}

#[pymethods]
impl ActionDefinition {
    #[new]
    #[expect(
        clippy::too_many_arguments,
        reason = "Python passes each field by keyword"
    )]
    const fn new(
        class_name: String,
        module_name: String,
        statements: Vec<ActionStatement>,
        interface_positions: Vec<InterfacePosition>,
        implied_qualities: Vec<ClassReference>,
        trace_operations: bool,
        imports: HashSet<String>,
        contract_class_name: Option<String>,
        contract_methods: Vec<String>,
        contract_definitions: Vec<DestructionContractDefinition>,
        guaranteed_particle_destructors: Vec<GuaranteedParticleDestructors>,
    ) -> Self {
        Self {
            class_name,
            module_name,
            statements,
            interface_positions,
            implied_qualities,
            trace_operations,
            imports,
            contract_class_name,
            contract_methods,
            contract_definitions,
            guaranteed_particle_destructors,
        }
    }
}

/// An operator written between the two values it combines.
#[pyclass(frozen, from_py_object)]
#[derive(Clone)]
pub enum BinaryOperator {
    Add {},
    Subtract {},
    Multiply {},
    And {},
    Or {},
    ExclusiveOr {},
    BitwiseAnd {},
    BitwiseOr {},
    Equal {},
    LessThan {},
    LessThanOrEqual {},
    GreaterThanOrEqual {},
}

/// An operator written before the one value it applies to.
#[pyclass(frozen, from_py_object)]
#[derive(Clone)]
pub enum PrefixOperator {
    Negate {},
    Not {},
}

/// An operation written as an expression over its operands.
#[pyclass(frozen, from_py_object)]
#[derive(Clone)]
pub enum ExpressionOperator {
    SaturatingSubtract {},
    SaturatingDecrement {},
}

/// A statement in the function of an Encoding Operation. Each operand and
/// argument is a local name or a literal already in its view's encoding.
#[pyclass(frozen, from_py_object)]
#[derive(Clone)]
pub enum EncodingOperationStatement {
    BinaryOperation {
        operator: BinaryOperator,
        left: String,
        right: String,
        result: String,
    },
    PrefixOperation {
        operator: PrefixOperator,
        operand: String,
        result: String,
    },
    ExpressionOperation {
        operator: ExpressionOperator,
        operands: Vec<String>,
        result: String,
    },
    /// Calls the function of another Encoding Operation.
    Call {
        function: FunctionReference,
        arguments: Vec<String>,
        /// The local names that receive the returned values.
        results: Vec<String>,
    },
}

/// A Python local name and the type of its value.
#[pyclass(frozen, from_py_object, get_all)]
#[derive(Clone)]
pub struct TypedLocalName {
    name: String,
    python_type: String,
}

#[pymethods]
impl TypedLocalName {
    #[new]
    const fn new(name: String, python_type: String) -> Self {
        Self { name, python_type }
    }
}

/// The function of an Encoding Operation.
#[pyclass(frozen, from_py_object, get_all)]
#[derive(Clone, Template)]
#[template(path = "encoding_operation_definition.j2", escape = "none")]
pub struct EncodingOperationDefinition {
    function_name: String,
    module_name: String,
    parameters: Vec<TypedLocalName>,
    statements: Vec<EncodingOperationStatement>,
    results: Vec<TypedLocalName>,
    /// Whether the last statement writes exactly the results, so the function
    /// returns its expression instead.
    return_last_statement: bool,
    /// The modules, other than its own, that the function uses.
    imports: HashSet<String>,
}

#[pymethods]
impl EncodingOperationDefinition {
    #[new]
    const fn new(
        function_name: String,
        module_name: String,
        parameters: Vec<TypedLocalName>,
        statements: Vec<EncodingOperationStatement>,
        results: Vec<TypedLocalName>,
        return_last_statement: bool,
        imports: HashSet<String>,
    ) -> Self {
        Self {
            function_name,
            module_name,
            parameters,
            statements,
            results,
            return_last_statement,
            imports,
        }
    }
}
