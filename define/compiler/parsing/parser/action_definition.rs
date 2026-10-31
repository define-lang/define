//! Action definitions and the statements in them.

use crate::ast;
use crate::node_construction::{Node, NodeTuple};
use crate::parse_error::{ParseError, ParseResult};
use crate::parser::Parser;
use crate::parser::lines::{INDENTATION_WIDTH, LineInBlock};
use crate::parser::names::{FqunWithCanonicalText, POSITION_OR_ACTION};
use crate::parser::operation_execution::{ExecutingDefinition, OperationKind};
use crate::scanner::Position;
use crate::syntax_errors::SyntaxErrors;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyString};
use terminals::{
    ACTION, BLOCK_OPEN, CHAIN_SEPARATOR, CREATE_A_PARTICLE_IN, DEFINE_THE, DEFINE_THE_POSITION,
    DEFINE_THE_POTENTIAL_POSITION, DESTROY_THE_PARTICLE_IN, EXECUTE_THE, IT_ALSO_ASSIGNS_THE,
    IT_HAPPENS_WHEN, LINE_FEED, LITERAL, MOVE_THE_PARTICLE_IN, POSITION, SET_THE_VALUE_OF, SPACE,
    SPACE_AND_IT_DOES, SPACE_HAS_A_PARTICLE, SPACE_TO, TERMINATOR, THE, THE_ACTION, THE_AND_SPACE,
    THE_POSITION, THIS_PARTICLE_IS_BEING_DESTROYED, THIS_PARTICLE_IS_CREATED,
};

/// How far the lines of an action definition block, which is always at the
/// top level, are indented.
const ACTION_DEFINITION_BLOCK_INDENTATION: usize = INDENTATION_WIDTH;
/// Expands to an array of the words that begin each statement an action
/// definition block may have before its trigger conditions block, followed
/// by `extra`.
macro_rules! action_definition_statement_starts {
    ($($extra:expr),*) => {
        [IT_ALSO_ASSIGNS_THE, DEFINE_THE_POSITION, IT_HAPPENS_WHEN, $($extra),*]
    };
}
/// Expands to an array of the words that begin each action statement,
/// followed by `extra`.
macro_rules! action_statement_starts {
    ($($extra:expr),*) => {
        [
            DEFINE_THE_POSITION,
            CREATE_A_PARTICLE_IN,
            MOVE_THE_PARTICLE_IN,
            DESTROY_THE_PARTICLE_IN,
            SET_THE_VALUE_OF,
            EXECUTE_THE,
            $($extra),*
        ]
    };
}
/// The words that begin each statement an action definition block may have
/// before its trigger conditions block.
const ACTION_DEFINITION_STATEMENT_STARTS: [&[u8]; 3] = action_definition_statement_starts!();
/// The words that begin each statement an action definition block may have
/// before its trigger conditions block, or a global position definition,
/// which belongs at the top level instead.
const ACTION_DEFINITION_BLOCK_STARTS: [&[u8]; 4] =
    action_definition_statement_starts!(DEFINE_THE_POTENTIAL_POSITION);
/// The words that begin each trigger condition statement, with each name
/// type a position presence statement may have after its `the`.
const TRIGGER_CONDITION_STARTS: [&[u8]; 4] = [
    THE_POSITION,
    THE_ACTION,
    THIS_PARTICLE_IS_CREATED,
    THIS_PARTICLE_IS_BEING_DESTROYED,
];
/// The words that begin each action statement.
const ACTION_STATEMENT_STARTS: [&[u8]; 6] = action_statement_starts!();
/// The words that begin each action statement, or a global position
/// definition, which belongs at the top level instead.
const ACTION_STATEMENTS_BLOCK_STARTS: [&[u8]; 7] =
    action_statement_starts!(DEFINE_THE_POTENTIAL_POSITION);

/// Each interface position of an action definition with its source typed
/// name.
type NamedInterfacePositions<'py> = Vec<(Bound<'py, PyString>, ast::LocalPositionDefinition<'py>)>;

impl<'py, 'source> Parser<'py, 'source> {
    /// Parses the rest of an action definition after its `action`, given the
    /// positions of the definition's start and of its `action`, and returns
    /// the definition with the position after its last character.
    ///
    /// ```ebnf
    /// action_definition =
    ///     "define the potential", " ", fully_qualified_global_action_name,
    ///     action_definition_block ;
    /// action_definition_block =
    ///     block_open,
    ///     { quality_implication_statement },
    ///     { local_position_definition },
    ///     trigger_conditions_block, " ", action_statements_block,
    ///     block_close ;
    /// ```
    pub(crate) fn parse_action_definition(
        &mut self,
        start: Position,
        typed_name_start: Position,
    ) -> ParseResult<(ast::ActionDefinition<'py>, Position)> {
        let (name_content, name_text, fqun) = self.parse_global_name_definition_content()?;
        let typed_name_location = self.ast.location(typed_name_start, self.scanner.position)?;
        let typed_name = self.global_typed_name_in_definition(
            typed_name_location,
            ast::NameType::Action,
            name_content,
            name_text,
        )?;
        let block_open_end = self.parse_block_open()?;
        // `content_end` is where the block's content ends so far, for the
        // error when the block ends before its trigger conditions block.
        let (implications, line, content_end) =
            self.parse_quality_implications(block_open_end, &fqun)?;
        let (interface_positions, named_interface_positions, line, content_end) =
            self.parse_interface_positions(line, content_end, &fqun)?;
        let (trigger_conditions, trigger_name, action_statements) =
            self.parse_trigger_and_action(line, content_end, &fqun)?;
        let end = self.parse_block_close_after_content(
            start,
            block_open_end,
            0,
            Self::statement_instead_of_action_close,
        )?;
        let (interface_positions_by_name, trigger_position) = self
            .interface_positions_by_name_and_trigger_position(
                named_interface_positions,
                trigger_name,
            )?;
        let location = self.ast.location(start, end)?;
        let definition = self.ast.action_definition(
            location,
            typed_name,
            implications,
            interface_positions,
            trigger_conditions,
            action_statements,
            interface_positions_by_name,
            trigger_position,
        )?;
        Ok((definition, end))
    }

    /// Returns the dict from each source typed name of an interface position in
    /// `named_interface_positions` to the interface position it refers to, and
    /// the interface position named `trigger_name`, whose particle triggers
    /// the action, if there is one.
    fn interface_positions_by_name_and_trigger_position(
        &self,
        named_interface_positions: NamedInterfacePositions<'py>,
        trigger_name: Option<Bound<'py, PyString>>,
    ) -> PyResult<(
        Bound<'py, PyDict>,
        Option<ast::LocalPositionDefinition<'py>>,
    )> {
        let interface_positions_by_name = PyDict::new(self.ast.py());
        for (name, position) in &named_interface_positions {
            // As in `ActionDefinition.__post_init__`, a name refers to the
            // first interface position with that name.
            if !interface_positions_by_name.contains(name)? {
                interface_positions_by_name.set_item(name, position.clone().into_object())?;
            }
        }
        // An action has only a few interface positions, and their names are
        // interned, so comparing identities is cheaper than a dict lookup.
        let trigger_position = trigger_name.and_then(|trigger_name| {
            named_interface_positions
                .into_iter()
                .find(|(name, _)| name.is(&trigger_name))
                .map(|(_, position)| position)
        });
        Ok((interface_positions_by_name, trigger_position))
    }

    /// Parses the quality implication statements at the start of an action
    /// definition block, after its `{` at `block_open_end`, whose references
    /// take their default FQUN from `fqun`. Returns them with the line in the
    /// block after them and where the block's content ends before that line.
    ///
    /// ```ebnf
    /// { quality_implication_statement }
    /// ```
    fn parse_quality_implications(
        &mut self,
        block_open_end: Position,
        fqun: &FqunWithCanonicalText<'py, 'source>,
    ) -> ParseResult<(
        NodeTuple<'py, ast::QualityImplicationStatement<'py>>,
        LineInBlock,
        Position,
    )> {
        let implications = self.nodes.start::<ast::QualityImplicationStatement>();
        let mut content_end = block_open_end;
        let mut line = self.next_line_in_block(0, &ACTION_DEFINITION_STATEMENT_STARTS)?;
        while matches!(line, LineInBlock::Statement)
            && self.scanner.next_bytes_are(IT_ALSO_ASSIGNS_THE)
        {
            let (implication, end) = self.parse_quality_implication_statement(fqun)?;
            self.nodes.push(&implications, implication);
            content_end = end;
            line = self.next_line_in_block(0, &ACTION_DEFINITION_STATEMENT_STARTS)?;
        }
        Ok((self.nodes.finish_tuple(implications)?, line, content_end))
    }

    /// Parses the local position definitions in an action definition block,
    /// starting at `line`, after content that ends at `content_end`, whose
    /// references take their default FQUN from `fqun`. Returns them, and each
    /// of them with its source typed name, with the line in the block after
    /// them and where the block's content ends before that line.
    ///
    /// ```ebnf
    /// { local_position_definition }
    /// ```
    fn parse_interface_positions(
        &mut self,
        mut line: LineInBlock,
        mut content_end: Position,
        fqun: &FqunWithCanonicalText<'py, 'source>,
    ) -> ParseResult<(
        NodeTuple<'py, ast::LocalPositionDefinition<'py>>,
        NamedInterfacePositions<'py>,
        LineInBlock,
        Position,
    )> {
        let interface_positions = self.nodes.start::<ast::LocalPositionDefinition>();
        let mut named_interface_positions = Vec::new();
        loop {
            if !matches!(line, LineInBlock::Statement) {
                break;
            }
            let start = self.scanner.position;
            let Some(typed_name_start) =
                self.scanner.consume_definition_start(DEFINE_THE, POSITION)
            else {
                break;
            };
            let (position, name, end) = self.parse_local_position_definition(
                start,
                typed_name_start,
                ACTION_DEFINITION_BLOCK_INDENTATION,
                fqun,
            )?;
            named_interface_positions.push((name, position.clone()));
            self.nodes.push(&interface_positions, position);
            content_end = end;
            line = self.next_line_in_block(0, &ACTION_DEFINITION_STATEMENT_STARTS)?;
        }
        Ok((
            self.nodes.finish_tuple(interface_positions)?,
            named_interface_positions,
            line,
            content_end,
        ))
    }

    /// Parses a quality implication statement, whose reference takes its
    /// default FQUN from `fqun`, through the end of its line, and returns it
    /// with the position after its `.`.
    ///
    /// ```ebnf
    /// quality_implication_statement = "it also assigns the", " ", typed_global_name, terminator ;
    /// ```
    fn parse_quality_implication_statement(
        &mut self,
        fqun: &FqunWithCanonicalText<'py, 'source>,
    ) -> ParseResult<(ast::QualityImplicationStatement<'py>, Position)> {
        let start = self.scanner.position;
        self.scanner.consume(IT_ALSO_ASSIGNS_THE);
        // The line ends, or a non-letter character comes, where the typed name
        // belongs.
        if !self.space_before_word()? {
            return Err(self.expected_position_or_action());
        }
        let (typed_name, _) = self.parse_typed_global_name_reference(
            fqun,
            &POSITION_OR_ACTION,
            Self::expected_position_or_action,
        )?;
        let end = self.parse_statement_terminator()?;
        let location = self.ast.location(start, end)?;
        let implication = self
            .ast
            .quality_implication_statement(location, typed_name)?;
        Ok((implication, end))
    }

    /// Parses the rest of a local position definition after its `position`,
    /// given the positions of the definition's start and of its `position`,
    /// where the definition is indented `indentation` spaces and its
    /// references take their default FQUN from `fqun`, and returns it with its
    /// source typed name and the position after its last character.
    ///
    /// ```ebnf
    /// local_position_definition =
    ///     "define the", " ", "position", "<", local_name, ">", position_definition_end ;
    /// ```
    fn parse_local_position_definition(
        &mut self,
        start: Position,
        typed_name_start: Position,
        indentation: usize,
        fqun: &FqunWithCanonicalText<'py, 'source>,
    ) -> ParseResult<(
        ast::LocalPositionDefinition<'py>,
        Bound<'py, PyString>,
        Position,
    )> {
        let name = self.parse_local_name_content()?;
        let typed_name_location = self.ast.location(typed_name_start, self.scanner.position)?;
        let (typed_name, source_typed_name) =
            self.local_typed_name_reference(typed_name_location, ast::NameType::Position, name)?;
        let (quality_assignment_block, end) = if self.scanner.next_bytes_are(BLOCK_OPEN) {
            let (block, end) = self.parse_position_definition_block(start, indentation, fqun)?;
            (Some(block), end)
        } else {
            // There is no `.` or ` {`.
            let Some(end) = self.parse_terminator()? else {
                return Err(self.missing_terminator_or_brace());
            };
            (None, end)
        };
        let location = self.ast.location(start, end)?;
        let definition =
            self.ast
                .local_position_definition(location, typed_name, quality_assignment_block)?;
        Ok((definition, source_typed_name, end))
    }

    /// Parses the trigger conditions block at `line` in an action definition
    /// block, whose content ends at `content_end` before it, and the action
    /// statements block after it, whose references take their default FQUN
    /// from `fqun`. Returns them with the source typed name of the position
    /// whose particle triggers the action, if a particle in a position does.
    ///
    /// ```ebnf
    /// trigger_conditions_block = "it happens when", block_open, trigger_condition_statement, "}" ;
    /// action_statements_block = "and it does", block_open, { action_statement }, block_close ;
    /// ```
    fn parse_trigger_and_action(
        &mut self,
        line: LineInBlock,
        content_end: Position,
        fqun: &FqunWithCanonicalText<'py, 'source>,
    ) -> ParseResult<(
        ast::TriggerConditionsBlock<'py>,
        Option<Bound<'py, PyString>>,
        ast::ActionStatementsBlock<'py>,
    )> {
        match line {
            LineInBlock::Statement if self.scanner.next_bytes_are(IT_HAPPENS_WHEN) => {}
            LineInBlock::Statement => return Err(self.invalid_action_definition_block()),
            // The block closes before its trigger conditions block.
            LineInBlock::Close => {
                let close = self.scanner.position;
                return Err(self.errors.missing_action_definition_syntax(close, close));
            }
            // The block ends before its trigger conditions block.
            LineInBlock::Unclosed => {
                return Err(self
                    .errors
                    .missing_action_definition_syntax(content_end, content_end));
            }
        };
        let start = self.scanner.position;
        self.scanner.consume(IT_HAPPENS_WHEN);
        let block_open_end = self.parse_block_open()?;
        let (condition, trigger_name) = match self.next_line_in_block(
            ACTION_DEFINITION_BLOCK_INDENTATION,
            &TRIGGER_CONDITION_STARTS,
        )? {
            LineInBlock::Statement => self.parse_trigger_condition()?,
            // The block is empty.
            LineInBlock::Close => {
                let close = self.scanner.position;
                return Err(self.errors.missing_trigger_condition_content(close, close));
            }
            // The block ends where its condition belongs.
            LineInBlock::Unclosed => {
                return Err(self
                    .errors
                    .missing_trigger_condition_content(block_open_end, block_open_end));
            }
        };
        match self.next_line_in_block(ACTION_DEFINITION_BLOCK_INDENTATION, &[])? {
            LineInBlock::Close => {}
            // A statement is where the block's `}` belongs.
            LineInBlock::Statement => {
                return Err(self.statement_instead_of_close_brace());
            }
            // The block ends before its `}`.
            LineInBlock::Unclosed => {
                return Err(self.missing_close_brace(start, block_open_end));
            }
        };
        self.scanner.consume_bytes(1);
        let location = self.ast.location(start, self.scanner.position)?;
        let trigger_conditions = self.ast.trigger_conditions_block(location, condition)?;
        let statements_start = self.scanner.position.next_column();
        // There is no ` and it does` after the `}`.
        if !self.scanner.consume(SPACE_AND_IT_DOES) {
            return Err(self.missing_action_statements_block());
        }
        let statements_open_end = self.parse_block_open()?;
        let statements = self.nodes.start::<ast::ActionStatement>();
        loop {
            match self.next_line_in_block(
                ACTION_DEFINITION_BLOCK_INDENTATION,
                &ACTION_STATEMENT_STARTS,
            )? {
                LineInBlock::Statement => {
                    let statement = self.parse_action_statement(
                        ACTION_DEFINITION_BLOCK_INDENTATION + INDENTATION_WIDTH,
                        fqun,
                    )?;
                    self.nodes.push(&statements, statement);
                }
                LineInBlock::Close => break,
                // The block ends before its `}`.
                LineInBlock::Unclosed => {
                    return Err(self.missing_close_brace(statements_start, statements_open_end));
                }
            }
        }
        let end = self.parse_block_close()?;
        let statements = self.nodes.finish_tuple(statements)?;
        let location = self.ast.location(statements_start, end)?;
        let action_statements = self.ast.action_statements_block(location, statements)?;
        Ok((trigger_conditions, trigger_name, action_statements))
    }

    /// Parses a trigger condition statement through the end of its line, and
    /// returns it with the source typed name of the position it names, if it
    /// is a position presence statement.
    ///
    /// ```ebnf
    /// trigger_condition_statement =
    ///     position_presence_statement
    ///     | constructor_condition_statement
    ///     | destructor_condition_statement ;
    /// ```
    fn parse_trigger_condition(
        &mut self,
    ) -> ParseResult<(
        ast::TriggerConditionStatement<'py>,
        Option<Bound<'py, PyString>>,
    )> {
        let start = self.scanner.position;
        if self.scanner.consume(THIS_PARTICLE_IS_CREATED) {
            let end = self.parse_statement_terminator()?;
            let location = self.ast.location(start, end)?;
            let condition = self.ast.constructor_condition_statement(location)?;
            return Ok((condition.into(), None));
        }
        if self.scanner.consume(THIS_PARTICLE_IS_BEING_DESTROYED) {
            let end = self.parse_statement_terminator()?;
            let location = self.ast.location(start, end)?;
            let condition = self.ast.destructor_condition_statement(location)?;
            return Ok((condition.into(), None));
        }
        // The statement is not a trigger condition statement.
        if !self.scanner.next_bytes_are(THE_AND_SPACE) {
            return Err(self.invalid_trigger_conditions_block());
        }
        let (condition, name) = self.parse_position_presence_statement()?;
        Ok((condition.into(), Some(name)))
    }

    /// Parses a position presence statement through the end of its line, and
    /// returns it with the source typed name of the position it names.
    ///
    /// ```ebnf
    /// position_presence_statement =
    ///     "the", " ", ( "position" | "action" ), "<", local_name, ">", " ", "has a particle", terminator ;
    /// ```
    fn parse_position_presence_statement(
        &mut self,
    ) -> ParseResult<(ast::PositionPresenceStatement<'py>, Bound<'py, PyString>)> {
        let start = self.scanner.position;
        self.scanner.consume(THE);
        // The line ends, or a non-letter character comes, where the typed name
        // belongs.
        if !self.space_before_word()? {
            return Err(self.expected_position_or_action());
        }
        let (typed_name, source_typed_name, typed_name_location) =
            self.parse_typed_local_name_reference()?;
        // There is no ` has a particle` after the typed name.
        if !self.scanner.consume(SPACE_HAS_A_PARTICLE) {
            return Err(self.invalid_has_a_particle_syntax());
        }
        let end = self.parse_statement_terminator()?;
        let typed_names = self.nodes.start::<ast::TypedNameReference>();
        self.nodes.push(&typed_names, typed_name.clone());
        let typed_names = self.nodes.finish_tuple(typed_names)?;
        let canonical_names = self.texts.start();
        self.texts.push(&canonical_names, source_typed_name.clone());
        let canonical_chained_name_tuple = self.texts.finish_tuple(canonical_names)?;
        let position_reference = self.ast.position_reference(
            typed_name_location,
            typed_names,
            canonical_chained_name_tuple,
            true,
        )?;
        let location = self.ast.location(start, end)?;
        let statement =
            self.ast
                .position_presence_statement(location, typed_name, position_reference)?;
        Ok((statement, source_typed_name))
    }

    /// Parses an action statement, indented `indentation` spaces, whose
    /// references take their default FQUN from `fqun`, through the end of its
    /// line.
    ///
    /// ```ebnf
    /// action_statement =
    ///     local_position_definition
    ///     | create_particle_statement
    ///     | move_particle_statement
    ///     | destroy_particle_statement
    ///     | value_setting_statement
    ///     | operation_execution_statement ;
    /// ```
    fn parse_action_statement(
        &mut self,
        indentation: usize,
        fqun: &FqunWithCanonicalText<'py, 'source>,
    ) -> ParseResult<ast::ActionStatement<'py>> {
        let start = self.scanner.position;
        if let Some(typed_name_start) = self.scanner.consume_definition_start(DEFINE_THE, POSITION)
        {
            let (definition, _, _) =
                self.parse_local_position_definition(start, typed_name_start, indentation, fqun)?;
            return Ok(definition.into());
        }
        if self.scanner.consume(CREATE_A_PARTICLE_IN) {
            let target = self.parse_statement_position_reference(fqun)?;
            let end = self.parse_reference_terminator()?;
            let location = self.ast.location(start, end)?;
            return Ok(self.ast.create_particle_statement(location, target)?.into());
        }
        if self.scanner.consume(DESTROY_THE_PARTICLE_IN) {
            let target = self.parse_statement_position_reference(fqun)?;
            let end = self.parse_reference_terminator()?;
            let location = self.ast.location(start, end)?;
            return Ok(self
                .ast
                .destroy_particle_statement(location, target)?
                .into());
        }
        if self.scanner.next_bytes_are(MOVE_THE_PARTICLE_IN) {
            return Ok(self.parse_move_particle_statement(fqun)?.into());
        }
        if self.scanner.next_bytes_are(SET_THE_VALUE_OF) {
            return Ok(self.parse_value_setting_statement(fqun)?.into());
        }
        if self.scanner.next_bytes_are(EXECUTE_THE) {
            return Ok(self
                .parse_operation_execution_statement(
                    ExecutingDefinition::Action,
                    OperationKind::Value,
                    indentation,
                    fqun,
                )?
                .into());
        }
        Err(self.invalid_action_statements_block())
    }

    /// Parses a move particle statement, whose references take their default
    /// FQUN from `fqun`, through the end of its line.
    ///
    /// ```ebnf
    /// move_particle_statement =
    ///     "move the particle in", " ", position_reference, " to ", position_reference, terminator ;
    /// ```
    fn parse_move_particle_statement(
        &mut self,
        fqun: &FqunWithCanonicalText<'py, 'source>,
    ) -> ParseResult<ast::MoveParticleStatement<'py>> {
        let start = self.scanner.position;
        self.scanner.consume(MOVE_THE_PARTICLE_IN);
        let source = self.parse_statement_position_reference(fqun)?;
        // There is no ` to` after the source position.
        if !self.consume_to() {
            return Err(self.missing_connecting_word(SyntaxErrors::invalid_move_statement_syntax));
        }
        let target = self.parse_statement_position_reference(fqun)?;
        let end = self.parse_reference_terminator()?;
        let location = self.ast.location(start, end)?;
        Ok(self.ast.move_particle_statement(location, target, source)?)
    }

    /// Parses a value setting statement, whose references take their default
    /// FQUN from `fqun`, through the end of its line.
    ///
    /// ```ebnf
    /// value_setting_statement =
    ///     "set the value of", " ", position_reference, " to ", ( position_reference | literal ), terminator ;
    /// ```
    fn parse_value_setting_statement(
        &mut self,
        fqun: &FqunWithCanonicalText<'py, 'source>,
    ) -> ParseResult<ast::ValueSettingStatement<'py>> {
        let start = self.scanner.position;
        self.scanner.consume(SET_THE_VALUE_OF);
        let target = self.parse_statement_position_reference(fqun)?;
        // TODO: Change "to" in Value Setting Statements to "from".
        // There is no ` to` after the target position.
        if !self.consume_to() {
            return Err(
                self.missing_connecting_word(SyntaxErrors::invalid_value_setting_statement_syntax)
            );
        }
        // The line ends, or a non-letter character comes, where the value's
        // source belongs.
        if !self.space_before_word()? {
            let missing = self.scanner.position;
            return Err(self.errors.missing_value_source(missing, missing));
        }
        // There is no value source where it belongs.
        if self.scanner.is_at_line_end() || self.scanner.next_byte_is(TERMINATOR) {
            let missing = self.scanner.position;
            return Err(self.errors.missing_value_source(missing, missing));
        }
        let (source, end) = self.parse_value_source(fqun, Self::expected_value_source)?;
        let location = self.ast.location(start, end)?;
        Ok(self.ast.value_setting_statement(location, target, source)?)
    }

    /// Parses a value's source, a position reference or a literal, whose
    /// references take their default FQUN from `fqun`, and the `.` after it,
    /// and returns the source with the position after the `.`. `wrong_source`
    /// returns the error for a source that is neither.
    ///
    /// ```ebnf
    /// ( position_reference | literal ), terminator
    /// ```
    pub(crate) fn parse_value_source<Source>(
        &mut self,
        fqun: &FqunWithCanonicalText<'py, 'source>,
        wrong_source: fn(&Self) -> ParseError,
    ) -> ParseResult<(Source, Position)>
    where
        Source: From<ast::PositionReference<'py>> + From<ast::Literal<'py>>,
    {
        if self.scanner.next_bytes_are(LITERAL) {
            let literal = self.parse_literal(fqun)?;
            let end = self.parse_statement_terminator()?;
            return Ok((literal.into(), end));
        }
        // The value's source is neither a position reference nor a literal.
        if !POSITION_OR_ACTION
            .iter()
            .any(|&(keyword, _)| self.scanner.next_bytes_are(keyword))
        {
            return Err(wrong_source(self));
        }
        let reference = self.parse_position_reference(fqun)?;
        Ok((reference.into(), self.parse_reference_terminator()?))
    }

    /// Parses the space and position reference that follow the words that
    /// begin a statement, whose global names take their default FQUN from
    /// `fqun`.
    ///
    /// ```ebnf
    /// " ", position_reference
    /// ```
    fn parse_statement_position_reference(
        &mut self,
        fqun: &FqunWithCanonicalText<'py, 'source>,
    ) -> ParseResult<ast::PositionReference<'py>> {
        // The line ends, or a non-letter character comes, where the position
        // reference belongs.
        if !self.space_before_word()? {
            let missing = self.scanner.position;
            return Err(self.errors.missing_position_reference(missing, missing));
        }
        self.parse_position_reference(fqun)
    }

    /// Parses the terminator after a statement that ends with a position
    /// reference, through the end of its line, and returns the position after
    /// its `.`.
    ///
    /// ```ebnf
    /// terminator
    /// ```
    pub(crate) fn parse_reference_terminator(&mut self) -> ParseResult<Position> {
        // There is no `.` or `::` after the position reference.
        let Some(end) = self.parse_terminator()? else {
            if let Some(error) = self.disallowed_character_ahead(0) {
                return Err(error);
            }
            let missing = self.scanner.position;
            return Err(self
                .errors
                .expected_chain_separator_or_terminator(missing, missing));
        };
        Ok(end)
    }

    /// Consumes ` to` when it is the word after a position reference.
    fn consume_to(&mut self) -> bool {
        let Some(after_to) = self.scanner.rest_after(SPACE_TO) else {
            return false;
        };
        // `to` is a whole word, not the start of another one, when a space,
        // the end of the line, or the `.` or name type where what follows `to`
        // belongs comes after it. A missing reference after a whole `to` is
        // reported where the reference belongs.
        let is_word = matches!(
            after_to.first(),
            None | Some(&(SPACE | TERMINATOR | LINE_FEED))
        ) || after_to.starts_with(LITERAL)
            || POSITION_OR_ACTION
                .iter()
                .any(|&(keyword, _)| after_to.starts_with(keyword));
        if is_word {
            self.scanner.consume(SPACE_TO);
        }
        is_word
    }
}

// The functions that only run on an error path.
impl<'py, 'source> Parser<'py, 'source> {
    /// Returns the error for the name type, at the scanner's position, of a
    /// value setting statement's source that is not `position`, `action`, or
    /// `literal`.
    #[cold]
    #[inline(never)]
    fn expected_value_source(&self) -> ParseError {
        if let Some(error) = self.disallowed_character_after_any(&[POSITION, ACTION, LITERAL]) {
            return error;
        }
        let start = self.scanner.position;
        self.errors
            .expected_position_or_action_or_literal(start, self.scanner.end_of_word())
    }

    /// Returns the error for a statement at the scanner's position in an
    /// action definition block before its trigger conditions block that does
    /// not belong there.
    #[cold]
    #[inline(never)]
    fn invalid_action_definition_block(&self) -> ParseError {
        if let Some(error) = self.disallowed_character_after_any(&ACTION_DEFINITION_BLOCK_STARTS) {
            return error;
        }
        let start = self.scanner.position;
        // Quality implication statements must come first in the block.
        if self.scanner.next_bytes_are(IT_ALSO_ASSIGNS_THE) {
            let end = start.after_ascii(IT_ALSO_ASSIGNS_THE).previous_column();
            return self.errors.quality_implication_in_wrong_order(start, end);
        }
        if let Some(error) = self.global_position_definition_in_local_context() {
            return error;
        }
        // The line begins like a statement of the block, but with extra or
        // missing spaces between two of its words.
        if let Some(error) = self.misspaced_words_in_any(&ACTION_DEFINITION_STATEMENT_STARTS) {
            return error;
        }
        self.errors
            .invalid_action_definitions_block(start, self.end_of_line())
    }

    /// Returns the error for a global position definition at the scanner's
    /// position, which belongs only at the top level.
    #[cold]
    fn global_position_definition_in_local_context(&self) -> Option<ParseError> {
        let start = self.scanner.position;
        // A global position definition is inside an action definition.
        if self.scanner.next_bytes_are(DEFINE_THE_POTENTIAL_POSITION) {
            let end = start
                .after_ascii(DEFINE_THE_POTENTIAL_POSITION)
                .previous_column();
            return Some(
                self.errors
                    .global_position_definition_in_local_context(start, end),
            );
        }
        None
    }

    /// Returns the error for a statement at the scanner's position, after an
    /// action definition's action statements block, where the definition's
    /// `}` belongs.
    #[cold]
    #[inline(never)]
    fn statement_instead_of_action_close(&self) -> ParseError {
        // A local position definition comes after the action statements block.
        if self.scanner.next_bytes_are(DEFINE_THE_POSITION) {
            let start = self.scanner.position;
            let end = start.after_ascii(DEFINE_THE_POSITION).previous_column();
            return self
                .errors
                .invalid_position_definition_location_in_action(start, end);
        }
        self.statement_instead_of_close_brace()
    }

    /// Returns the error for the text at the scanner's position, right after a
    /// trigger conditions block's `}`, where ` and it does` belongs.
    #[cold]
    #[inline(never)]
    fn missing_action_statements_block(&mut self) -> ParseError {
        if let Some(error) = self.disallowed_character_ahead(self.scanner.next_space_count()) {
            return error;
        }
        let start = self.scanner.position;
        match self.space_before_word() {
            // The spaces before the next word are missing or extra.
            Err(error) => error,
            // The word after the `}` is not `and it does`, or the line ends
            // where it belongs.
            Ok(_) => self.errors.missing_action_statements_block(start, start),
        }
    }

    /// Returns the error for a statement at the scanner's position in a
    /// trigger conditions block that is not a trigger condition statement.
    #[cold]
    #[inline(never)]
    fn invalid_trigger_conditions_block(&self) -> ParseError {
        if let Some(error) = self.disallowed_character_after_any(&TRIGGER_CONDITION_STARTS) {
            return error;
        }
        // The line begins like a trigger condition statement, but with extra or
        // missing spaces between two of its words.
        if let Some(error) = self.misspaced_words_in_any(&TRIGGER_CONDITION_STARTS) {
            return error;
        }
        let start = self.scanner.position;
        self.errors
            .invalid_trigger_conditions_block(start, self.end_of_line())
    }

    /// Returns the error for the text at the scanner's position, right after
    /// the typed name of a position presence statement, where
    /// ` has a particle` belongs.
    #[cold]
    #[inline(never)]
    fn invalid_has_a_particle_syntax(&mut self) -> ParseError {
        if let Some(error) = self.disallowed_character_ahead(self.scanner.next_space_count()) {
            return error;
        }
        let start = self.scanner.position;
        // A chained name is where the statement's single local name belongs.
        if self.scanner.next_bytes_are(CHAIN_SEPARATOR) {
            return self
                .errors
                .chained_name_in_position_presence_statement(start, start.next_column());
        }
        match self.space_before_word() {
            // The spaces before the next word are missing or extra.
            Err(error) => error,
            // The word after the typed name is not `has a particle`, or the
            // line ends where it belongs.
            Ok(_) => self.errors.invalid_has_a_particle_syntax(start, start),
        }
    }

    /// Returns the error for the text at the scanner's position, right after a
    /// reference, where the words that connect it to the rest of its statement
    /// belong, such as ` to`. `wrong_word` returns the statement's error for
    /// whatever is there instead.
    #[cold]
    #[inline(never)]
    pub(crate) fn missing_connecting_word(
        &mut self,
        wrong_word: fn(&SyntaxErrors<'py>, Position, Position) -> ParseError,
    ) -> ParseError {
        if let Some(error) = self.disallowed_character_ahead(self.scanner.next_space_count()) {
            return error;
        }
        let start = self.scanner.position;
        match self.space_before_word() {
            // The spaces before the next word are missing or extra.
            Err(error) => error,
            // The error covers the word after the space where the connecting
            // words belong.
            Ok(true) => wrong_word(
                &self.errors,
                self.scanner.position,
                self.scanner.end_of_word(),
            ),
            // The line ends where the connecting words belong.
            Ok(false) => wrong_word(&self.errors, start, start),
        }
    }

    /// Returns the error for a statement at the scanner's position in an
    /// action statements block that is not an action statement.
    #[cold]
    #[inline(never)]
    fn invalid_action_statements_block(&self) -> ParseError {
        if let Some(error) = self.disallowed_character_after_any(&ACTION_STATEMENTS_BLOCK_STARTS) {
            return error;
        }
        if let Some(error) = self.global_position_definition_in_local_context() {
            return error;
        }
        // The line begins like an action statement, but with extra or missing
        // spaces between two of its words.
        if let Some(error) = self.misspaced_words_in_any(&ACTION_STATEMENT_STARTS) {
            return error;
        }
        let start = self.scanner.position;
        self.errors
            .invalid_action_statements_block(start, self.end_of_line())
    }
}
