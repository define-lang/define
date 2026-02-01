"""Semantic validation for the Define language AST."""

from typing import ClassVar

from compiler.prototype import ast

# Type aliases for commonly used dictionary types
# Maps type name to its declaration
DeclaredTypes = dict[str, ast.BaseTypeDeclaration]
# Maps entity name to its creation statement
DeclaredEntities = dict[str, ast.EntityCreation]
# Maps type name to a dictionary of property name -> property type
DeclaredProperties = dict[str, dict[str, str]]
# Maps type name to a dictionary of action name -> action declaration
DeclaredActions = dict[str, dict[str, ast.ActionDeclaration]]


class SemanticError(Exception):
    """Base class for all semantic validation errors."""


class UnknownStatementTypeError(SemanticError):
    """Raised when an unknown statement type is encountered."""


class DuplicateUniverseError(SemanticError):
    """Raised when multiple blocks of the same universe type exist."""


class UndeclaredTypeError(SemanticError):
    """Raised when a type is referenced before it is declared."""


class UndeclaredEntityError(SemanticError):
    """Raised when an entity is referenced but does not exist."""


class UndeclaredPropertyError(SemanticError):
    """Raised when a property is referenced but not declared on the type."""


class UndeclaredActionError(SemanticError):
    """Raised when an action is referenced but not declared."""


class NameConflictError(SemanticError):
    """Raised when there is a name conflict between types and entities."""


class InvalidCreatorError(SemanticError):
    """Raised when a non-ViewPoint attempts to create an entity."""


class InvalidKnowerError(SemanticError):
    """Raised when a non-ViewPoint attempts to know about an entity."""


class InvalidActorError(SemanticError):
    """Raised when a non-ViewPoint attempts to execute an action."""


class InvalidPropertyAssignmentError(SemanticError):
    """Raised when a property is assigned that is not declared on the type."""


class InvalidPropertyValueTypeError(SemanticError):
    """Raised when a property value type does not match the declared property type."""


class InvalidKnowledgeStatementError(SemanticError):
    """Raised when a knowledge statement is invalid (e.g., knower == owner)."""


class ReservedWordError(SemanticError):
    """Raised when a reserved word is used as an identifier."""


class Validator:
    """Validates semantic rules for a Define program AST."""

    # Reserved words from the spec
    RESERVED_WORDS: ClassVar[set[str]] = {
        "AbstractUniverse",
        "PhysicalUniverse",
        "ViewPoint",
        "DimensionPoint",
        "Consideration",
        "String",
        "Number",
        "has",
        "a",
        "named",
        "is",
        "creates",
        "knows",
        "can",
        "using",
        "makes",
    }

    def __init__(self, program: ast.Program):
        """Initialize validator with a program AST.

        Args:
            program: The program AST to validate
        """
        self.program = program

    def validate(self):
        """Validate all semantic rules for the program.

        Raises:
            SemanticError: If any semantic rule is violated
        """
        self._validate_universes()
        self._validate_in_order()

    def _validate_universes(self):
        """Validate universe blocks (one of each max)."""
        seen_universes: set[str] = set()
        for universe in self.program.universes:
            if universe.name in seen_universes:
                raise DuplicateUniverseError(
                    f"Duplicate universe block: {universe.name!r}"
                )
            seen_universes.add(universe.name)

    def _validate_in_order(self):
        """Validate statements in order, ensuring declarations-before-use."""
        # Track what's been declared so far in this pass
        declared_types: DeclaredTypes = {}
        declared_entities: DeclaredEntities = {}
        declared_properties: DeclaredProperties = {}
        declared_actions: DeclaredActions = {}

        for universe in self.program.universes:
            for stmt in universe.statements:
                self._validate_statement(
                    stmt,
                    declared_types,
                    declared_entities,
                    declared_properties,
                    declared_actions,
                )

    def _validate_statement(
        self,
        stmt: ast.ASTNode,
        declared_types: DeclaredTypes,
        declared_entities: DeclaredEntities,
        declared_properties: DeclaredProperties,
        declared_actions: DeclaredActions,
    ):
        """Dispatch to appropriate validator method based on statement type."""
        if isinstance(stmt, ast.CompilerTypeDeclaration):
            self._validate_compiler_type_declaration(
                stmt, declared_types, declared_entities
            )
        elif isinstance(stmt, ast.TypeDeclaration):
            self._validate_type_declaration(stmt, declared_types, declared_entities)
        elif isinstance(stmt, ast.PropertyDeclaration):
            self._validate_property_declaration(
                stmt, declared_types, declared_properties
            )
        elif isinstance(stmt, ast.EntityCreation):
            self._validate_entity_creation(
                stmt,
                declared_types,
                declared_entities,
                declared_properties,
            )
        elif isinstance(stmt, ast.KnowledgeStatement):
            self._validate_knowledge_statement(stmt, declared_types, declared_entities)
        elif isinstance(stmt, ast.ActionDeclaration):
            self._validate_action_declaration(stmt, declared_types, declared_actions)
        elif isinstance(stmt, ast.ActionExecution):
            self._validate_action_execution(
                stmt,
                declared_types,
                declared_entities,
                declared_actions,
                declared_properties,
            )
        else:
            raise UnknownStatementTypeError(
                f"Unknown statement type: {type(stmt).__name__}"
            )

    def _is_viewpoint_type(
        self,
        type_name: str,
        declared_types: DeclaredTypes,
    ) -> bool:
        """Check if a type is a ViewPoint or subclass of ViewPoint using incremental state."""
        if type_name == "ViewPoint":
            return True
        if type_name not in declared_types:
            return False
        type_decl = declared_types[type_name]
        if isinstance(type_decl, ast.CompilerTypeDeclaration):
            return False
        if isinstance(type_decl, ast.TypeDeclaration):
            return self._is_viewpoint_type(type_decl.parent_type, declared_types)
        return False

    def _check_is_viewpoint(
        self,
        type_name: str,
        declared_types: DeclaredTypes,
        context: str,
    ):
        """Check if a type is a ViewPoint.

        Args:
            type_name: The type name to check
            declared_types: Types declared so far
            context: Context string for error messages

        Raises:
            InvalidCreatorError, InvalidKnowerError, or InvalidActorError: If type is not a ViewPoint
        """
        if not self._is_viewpoint_type(type_name, declared_types):
            error_class = InvalidCreatorError
            if "knower" in context.lower() or "owner" in context.lower():
                error_class = InvalidKnowerError
            elif "actor" in context.lower():
                error_class = InvalidActorError
            else:
                error_class = InvalidCreatorError
            raise error_class(f"{context}: {type_name!r} is not a ViewPoint")

    def _check_reserved_word(self, name: str, context: str):
        """Check if a name is a reserved word.

        Args:
            name: The name to check
            context: Context string for error messages

        Raises:
            ReservedWordError: If name is a reserved word
        """
        if name in self.RESERVED_WORDS:
            raise ReservedWordError(f"{context} {name!r} is a reserved word")

    def _validate_base_type_declaration(
        self,
        stmt: ast.BaseTypeDeclaration,
        declared_types: DeclaredTypes,
        declared_entities: DeclaredEntities,
    ):
        self._check_reserved_word(stmt.type_name, "Type name")
        if stmt.type_name in declared_types:
            raise NameConflictError(f"Type {stmt.type_name!r} is already defined")
        if stmt.type_name in declared_entities:
            raise NameConflictError(
                f"Type {stmt.type_name!r} conflicts with entity of same name"
            )

    def _validate_compiler_type_declaration(
        self,
        stmt: ast.CompilerTypeDeclaration,
        declared_types: DeclaredTypes,
        declared_entities: DeclaredEntities,
    ):
        """Validate a compiler type declaration."""
        self._validate_base_type_declaration(stmt, declared_types, declared_entities)
        declared_types[stmt.type_name] = stmt

    def _validate_type_declaration(
        self,
        stmt: ast.TypeDeclaration,
        declared_types: DeclaredTypes,
        declared_entities: DeclaredEntities,
    ):
        """Validate a type declaration."""
        self._validate_base_type_declaration(stmt, declared_types, declared_entities)
        if stmt.parent_type not in declared_types:
            raise UndeclaredTypeError(
                f"Type {stmt.type_name!r} extends undefined type {stmt.parent_type!r}. "
                f"Type {stmt.parent_type!r} must be declared before it can be used as a parent type."
            )
        # Mark as declared
        declared_types[stmt.type_name] = stmt

    def _validate_property_declaration(
        self,
        stmt: ast.PropertyDeclaration,
        declared_types: DeclaredTypes,
        declared_properties: DeclaredProperties,
    ):
        """Validate a property declaration."""
        # Check type exists (must be declared before)
        if stmt.type_name not in declared_types:
            raise UndeclaredTypeError(
                f"Property {stmt.property_name!r} is declared on undefined type {stmt.type_name!r}. "
                f"Type {stmt.type_name!r} must be declared before properties can be added to it."
            )
        # Check property type exists (must be declared before)
        if stmt.property_type not in declared_types:
            raise UndeclaredTypeError(
                f"Property {stmt.property_name!r} on type {stmt.type_name!r} has undefined type {stmt.property_type!r}. "
                f"Type {stmt.property_type!r} must be declared before it can be used as a property type."
            )
        # Track property declaration
        if stmt.type_name not in declared_properties:
            declared_properties[stmt.type_name] = {}
        declared_properties[stmt.type_name][stmt.property_name] = stmt.property_type

    def _validate_entity_creation(
        self,
        stmt: ast.EntityCreation,
        declared_types: DeclaredTypes,
        declared_entities: DeclaredEntities,
        declared_properties: DeclaredProperties,
    ):
        """Validate an entity creation."""
        # Check creator is a ViewPoint (must be declared before)
        if stmt.creator not in declared_types:
            raise UndeclaredTypeError(
                f"Entity {stmt.entity_name!r} is created by undefined type {stmt.creator!r}. "
                f"Type {stmt.creator!r} must be declared before it can create entities."
            )
        self._check_is_viewpoint(stmt.creator, declared_types, "Creator")
        # Check type exists (must be declared before)
        if stmt.type_name not in declared_types:
            raise UndeclaredTypeError(
                f"Entity {stmt.entity_name!r} has undefined type {stmt.type_name!r}. "
                f"Type {stmt.type_name!r} must be declared before entities of this type can be created."
            )
        # Check for name conflicts (check against both types and entities)
        if stmt.entity_name in declared_types:
            raise NameConflictError(
                f"Entity {stmt.entity_name!r} conflicts with type of same name"
            )
        if stmt.entity_name in declared_entities:
            raise NameConflictError(f"Entity {stmt.entity_name!r} is already defined")
        # Check reserved words
        self._check_reserved_word(stmt.entity_name, "Entity name")
        # Validate property assignments
        declared_props = declared_properties.get(stmt.type_name, {})
        for prop_assignment in stmt.properties:
            # Property must be declared
            if prop_assignment.name not in declared_props:
                raise InvalidPropertyAssignmentError(
                    f"Property {prop_assignment.name!r} not declared on type {stmt.type_name!r}"
                )
            # Validate property value type
            expected_type = declared_props[prop_assignment.name]
            self._validate_property_value_type(
                prop_assignment.value,
                expected_type,
                prop_assignment.name,
                declared_types,
                declared_entities,
                declared_properties,
            )
        # Validate property value references (declarations-before-use)
        for prop_assignment in stmt.properties:
            self._validate_value_reference(
                prop_assignment.value,
                declared_types,
                declared_entities,
                declared_properties,
            )
        # Mark as declared
        declared_entities[stmt.entity_name] = stmt

    def _validate_knowledge_statement(
        self,
        stmt: ast.KnowledgeStatement,
        declared_types: DeclaredTypes,
        declared_entities: DeclaredEntities,
    ):
        """Validate a knowledge statement."""
        # Check knower is a ViewPoint (must be declared before)
        if stmt.knower not in declared_types:
            raise UndeclaredTypeError(
                f"Knowledge statement has undefined knower type {stmt.knower!r}. "
                f"Type {stmt.knower!r} must be declared before it can know about entities."
            )
        self._check_is_viewpoint(stmt.knower, declared_types, "Knower")
        # Check owner is a ViewPoint (must be declared before)
        if stmt.owner not in declared_types:
            raise UndeclaredTypeError(
                f"Knowledge statement has undefined owner type {stmt.owner!r}. "
                f"Type {stmt.owner!r} must be declared before it can own entities."
            )
        self._check_is_viewpoint(stmt.owner, declared_types, "Owner")
        # Check knower != owner
        if stmt.knower == stmt.owner:
            raise InvalidKnowledgeStatementError(
                f"Knower {stmt.knower!r} cannot know about its own entity {stmt.entity_name!r}"
            )
        # Check entity exists (must be declared before)
        if stmt.entity_name not in declared_entities:
            raise UndeclaredEntityError(
                f"Entity {stmt.entity_name!r} not found for knowledge statement"
            )
        # Check entity is owned by owner
        entity = declared_entities[stmt.entity_name]
        if entity.creator != stmt.owner:
            raise InvalidKnowledgeStatementError(
                f"Entity {stmt.entity_name!r} is not owned by {stmt.owner!r}"
            )

    def _validate_action_declaration(
        self,
        stmt: ast.ActionDeclaration,
        declared_types: DeclaredTypes,
        declared_actions: DeclaredActions,
    ):
        """Validate an action declaration."""
        # Check type exists (must be declared before)
        if stmt.type_name not in declared_types:
            raise UndeclaredTypeError(
                f"Action {stmt.action_name!r} is declared on undefined type {stmt.type_name!r}. "
                f"Type {stmt.type_name!r} must be declared before actions can be added to it."
            )
        # Check parameter types exist (must be declared before)
        for param in stmt.parameters:
            if param.param_type not in declared_types:
                raise UndeclaredTypeError(
                    f"Action {stmt.action_name!r} on type {stmt.type_name!r} has parameter with undefined type {param.param_type!r}. "
                    f"Type {param.param_type!r} must be declared before it can be used as a parameter type."
                )
        # Track action declaration
        if stmt.type_name not in declared_actions:
            declared_actions[stmt.type_name] = {}
        declared_actions[stmt.type_name][stmt.action_name] = stmt

    def _validate_action_execution(
        self,
        stmt: ast.ActionExecution,
        declared_types: DeclaredTypes,
        declared_entities: DeclaredEntities,
        declared_actions: DeclaredActions,
        declared_properties: DeclaredProperties,
    ):
        """Validate an action execution."""
        # Check actor is a ViewPoint (must be declared before)
        if stmt.actor not in declared_types:
            raise UndeclaredTypeError(
                f"Action execution has undefined actor type {stmt.actor!r}. "
                f"Type {stmt.actor!r} must be declared before it can execute actions."
            )
        self._check_is_viewpoint(stmt.actor, declared_types, "Actor")
        # Check target entity exists (must be declared before)
        target_entity_name = stmt.target.property_name
        if target_entity_name not in declared_entities:
            raise UndeclaredEntityError(
                f"Target entity {target_entity_name!r} not found for action execution"
            )
        # Check target is owned by target owner
        target_entity = declared_entities[target_entity_name]
        if target_entity.creator != stmt.target.owner:
            raise InvalidKnowledgeStatementError(
                f"Target entity {target_entity_name!r} is not owned by {stmt.target.owner!r}"
            )
        # Check action exists on target type (must be declared before)
        target_type = target_entity.type_name
        actions_for_type = declared_actions.get(target_type, {})
        if stmt.action_name not in actions_for_type:
            raise UndeclaredActionError(
                f"Action {stmt.action_name!r} not found on type {target_type!r}"
            )
        # Validate argument types
        action_decl = actions_for_type[stmt.action_name]
        if len(stmt.arguments) != len(action_decl.parameters):
            raise SemanticError(
                f"Action {stmt.action_name!r} expects {len(action_decl.parameters)} arguments, got {len(stmt.arguments)}"
            )
        for arg, param in zip(stmt.arguments, action_decl.parameters, strict=True):
            self._validate_argument_type(
                arg,
                param.param_type,
                declared_types,
                declared_entities,
                declared_properties,
            )
        # Validate argument references (declarations-before-use)
        for arg in stmt.arguments:
            self._validate_value_reference(
                arg, declared_types, declared_entities, declared_properties
            )

    def _validate_value_reference(
        self,
        value: ast.ValueReference,
        declared_types: DeclaredTypes,
        declared_entities: DeclaredEntities,
        declared_properties: DeclaredProperties,
    ):
        """Validate a value reference (declarations-before-use)."""
        if isinstance(value, ast.PropertyOrEntityReference):
            # Check owner exists (must be a ViewPoint or entity, declared before)
            owner_is_viewpoint = (
                self._is_viewpoint_type(value.owner, declared_types)
                or value.owner in declared_types
            )
            owner_is_entity = value.owner in declared_entities
            if not owner_is_viewpoint and not owner_is_entity:
                raise UndeclaredEntityError(
                    f"Owner {value.owner!r} not found for reference {value.property_name!r}"
                )
            # If owner is an entity, check property exists
            if owner_is_entity:
                entity = declared_entities[value.owner]
                entity_type = entity.type_name
                entity_props = declared_properties.get(entity_type, {})
                if value.property_name not in entity_props:
                    raise UndeclaredPropertyError(
                        f"Property {value.property_name!r} not found on entity {value.owner!r} of type {entity_type!r}"
                    )
            # If owner is a ViewPoint, check entity exists (declared before)
            elif owner_is_viewpoint:
                if value.property_name not in declared_entities:
                    raise UndeclaredEntityError(
                        f"Entity {value.property_name!r} not found for ViewPoint {value.owner!r}"
                    )

    def _validate_property_value_type(
        self,
        value: ast.ValueReference,
        expected_type: str,
        property_name: str,
        declared_types: DeclaredTypes,
        declared_entities: DeclaredEntities,
        declared_properties: DeclaredProperties,
    ):
        """Validate that a property value matches the expected type."""
        if isinstance(value, ast.StringLiteral):
            if expected_type != "String":
                raise InvalidPropertyValueTypeError(
                    f"Property {property_name!r} expects type {expected_type!r}, got String"
                )
        elif isinstance(value, ast.NumberLiteral):
            if expected_type != "Number":
                raise InvalidPropertyValueTypeError(
                    f"Property {property_name!r} expects type {expected_type!r}, got Number"
                )
        elif isinstance(value, ast.PropertyOrEntityReference):
            # For references, we need to determine the actual type
            actual_type = self._get_reference_type(
                value, declared_types, declared_entities, declared_properties
            )
            if not self._is_subtype(actual_type, expected_type, declared_types):
                raise InvalidPropertyValueTypeError(
                    f"Property {property_name!r} expects type {expected_type!r}, got {actual_type!r}"
                )

    def _validate_argument_type(
        self,
        value: ast.ValueReference,
        expected_type: str,
        declared_types: DeclaredTypes,
        declared_entities: DeclaredEntities,
        declared_properties: DeclaredProperties,
    ):
        """Validate that an argument matches the expected type."""
        if isinstance(value, ast.StringLiteral):
            if expected_type != "String":
                raise InvalidPropertyValueTypeError(
                    f"Argument expects type {expected_type!r}, got String"
                )
        elif isinstance(value, ast.NumberLiteral):
            if expected_type != "Number":
                raise InvalidPropertyValueTypeError(
                    f"Argument expects type {expected_type!r}, got Number"
                )
        elif isinstance(value, ast.PropertyOrEntityReference):
            actual_type = self._get_reference_type(
                value, declared_types, declared_entities, declared_properties
            )
            if not self._is_subtype(actual_type, expected_type, declared_types):
                raise InvalidPropertyValueTypeError(
                    f"Argument expects type {expected_type!r}, got {actual_type!r}"
                )

    def _get_reference_type(
        self,
        ref: ast.PropertyOrEntityReference,
        declared_types: DeclaredTypes,
        declared_entities: DeclaredEntities,
        declared_properties: DeclaredProperties | None = None,
    ) -> str:
        """Get the type of a property or entity reference."""
        if ref.owner in declared_entities:
            # It's a property reference
            entity = declared_entities[ref.owner]
            entity_type = entity.type_name
            if declared_properties and entity_type in declared_properties:
                return declared_properties[entity_type].get(
                    ref.property_name, "Unknown"
                )
            return "Unknown"
        if (
            self._is_viewpoint_type(ref.owner, declared_types)
            or ref.owner in declared_types
        ) and ref.property_name in declared_entities:
            # It's an entity reference
            entity = declared_entities[ref.property_name]
            return entity.type_name
        return "Unknown"

    def _is_subtype(
        self,
        subtype: str,
        supertype: str,
        declared_types: DeclaredTypes,
    ) -> bool:
        """Check if a type is a subtype of another type."""
        if subtype == supertype:
            return True
        if subtype not in declared_types:
            return False
        type_decl = declared_types[subtype]
        if isinstance(type_decl, ast.TypeDeclaration):
            return self._is_subtype(type_decl.parent_type, supertype, declared_types)
        return False
