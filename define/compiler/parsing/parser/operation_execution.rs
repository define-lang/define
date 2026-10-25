//! Operation execution statements and their operation arguments blocks.

use crate::ast;
use crate::node_construction::NodeTuple;
use crate::parse_error::{ParseError, ParseResult};
use crate::parser::Parser;
use crate::parser::lines::LineInBlock;
use crate::parser::names::{FqunWithCanonicalText, POSITION_OR_ACTION};
use crate::scanner::Position;
use crate::syntax_errors::SyntaxErrors;
use pyo3::intern;
use pyo3::prelude::*;
use pyo3::types::PyString;
use terminals::{
    ACTION, BLOCK_OPEN, ENCODING_OPERATION, EXECUTE_THE, EXECUTE_THE_COMPUTER_OPERATION,
    EXECUTE_THE_ENCODING_OPERATION, LITERAL, OPERATION, POSITION, SPACE_LOOKING_AT, VIEW, WITH,
};

/// The one name type that a Value Operation Execution Statement allows.
const OPERATION_NAME_TYPE: [(&[u8], ast::NameType); 1] = [(OPERATION, ast::NameType::Operation)];
/// The one name type that an Encoding Operation Execution Statement allows.
const ENCODING_OPERATION_NAME_TYPE: [(&[u8], ast::NameType); 1] =
    [(ENCODING_OPERATION, ast::NameType::EncodingOperation)];
/// Whether an operation is a Value Operation or an Encoding Operation.
#[derive(Clone, Copy)]
pub(crate) enum OperationKind {
    Value,
    Encoding,
}

/// The kind of definition that has an operation execution statement, which
/// decides what its operation arguments may look at besides literals.
#[derive(Clone, Copy, PartialEq, Eq)]
pub(crate) enum ExecutingDefinition {
    /// An action, whose arguments may look at positions.
    Action,
    /// A Value Operation or an Encoding Operation, whose arguments may look at
    /// views.
    Operation,
}

impl OperationKind {
    /// The words of the statement that executes the implementation of an
    /// operation of this kind: `execute the encoding operation` or
    /// `execute the computer operation`.
    pub(crate) const fn implementation_execution_statement(self) -> &'static [u8] {
        match self {
            Self::Value => EXECUTE_THE_ENCODING_OPERATION,
            Self::Encoding => EXECUTE_THE_COMPUTER_OPERATION,
        }
    }
}

impl<'py, 'source> Parser<'py, 'source> {
    /// Parses an operation execution statement in an `executing_definition`
    /// that executes an operation of `kind`, indented `indentation` spaces,
    /// whose references take their default FQUN from `fqun`, through the end
    /// of its last line.
    ///
    /// ```ebnf
    /// operation_execution_statement = "execute the", " ", operation_name, operation_execution_end ;
    /// operation_execution_end = terminator | operation_arguments_block ;
    /// ```
    pub(crate) fn parse_operation_execution_statement(
        &mut self,
        executing_definition: ExecutingDefinition,
        kind: OperationKind,
        indentation: usize,
        fqun: &FqunWithCanonicalText<'py, 'source>,
    ) -> ParseResult<ast::OperationExecutionStatement<'py>> {
        let start = self.scanner.position;
        self.scanner.consume(EXECUTE_THE);
        // The line ends, or a non-letter character comes, where the operation's
        // typed name belongs.
        if !self.space_before_word()? {
            return Err(self.wrong_operation_name_type(kind));
        }
        let (operation, _) = match kind {
            OperationKind::Value => self.parse_typed_global_name_reference(
                fqun,
                &OPERATION_NAME_TYPE,
                Self::expected_operation,
            )?,
            OperationKind::Encoding => self.parse_typed_global_name_reference(
                fqun,
                &ENCODING_OPERATION_NAME_TYPE,
                Self::expected_encoding_operation,
            )?,
        };
        if self.scanner.next_bytes_are(BLOCK_OPEN) {
            let (arguments, end) = self.parse_operation_arguments_block(
                executing_definition,
                start,
                indentation,
                fqun,
            )?;
            let location = self.ast.location(start, end)?;
            return Ok(self
                .ast
                .operation_execution_statement(location, operation, arguments)?);
        }
        // There is no `.` or ` {`.
        let Some(end) = self.parse_terminator()? else {
            return Err(self.missing_terminator_or_brace());
        };
        let arguments = self.nodes.start::<ast::OperationArgumentStatement>();
        let arguments = self.nodes.finish_tuple(arguments)?;
        let location = self.ast.location(start, end)?;
        Ok(self
            .ast
            .operation_execution_statement(location, operation, arguments)?)
    }

    /// Parses the operation arguments block of the operation execution
    /// statement in an `executing_definition` that begins at `start`, indented
    /// `indentation` spaces, whose references take their default FQUN from
    /// `fqun`, and returns its arguments with the position after its `}`.
    ///
    /// ```ebnf
    /// operation_arguments_block =
    ///     block_open,
    ///     operation_argument_statement,
    ///     { operation_argument_statement },
    ///     block_close ;
    /// ```
    fn parse_operation_arguments_block(
        &mut self,
        executing_definition: ExecutingDefinition,
        start: Position,
        indentation: usize,
        fqun: &FqunWithCanonicalText<'py, 'source>,
    ) -> ParseResult<(
        NodeTuple<'py, ast::OperationArgumentStatement<'py>>,
        Position,
    )> {
        let block_open_end = self.parse_block_open()?;
        match self.next_line_in_block(indentation, &[WITH])? {
            LineInBlock::Statement => {}
            // The block is empty.
            LineInBlock::Close => {
                let close = self.scanner.position;
                return Err(self
                    .errors
                    .missing_operation_arguments_content(close, close));
            }
            // The block ends where its first argument belongs.
            LineInBlock::Unclosed => {
                return Err(self
                    .errors
                    .missing_operation_arguments_content(block_open_end, block_open_end));
            }
        }
        let arguments = self.nodes.start::<ast::OperationArgumentStatement>();
        loop {
            let argument = self.parse_operation_argument_statement(executing_definition, fqun)?;
            self.nodes.push(&arguments, argument);
            match self.next_line_in_block(indentation, &[WITH])? {
                LineInBlock::Statement => {}
                LineInBlock::Close => break,
                // The block ends before its `}`.
                LineInBlock::Unclosed => {
                    return Err(self.missing_close_brace(start, block_open_end));
                }
            }
        }
        let end = self.parse_block_close()?;
        Ok((self.nodes.finish_tuple(arguments)?, end))
    }

    /// Parses an operation argument statement in an `executing_definition`,
    /// whose references take their default FQUN from `fqun`, through the end
    /// of its line.
    ///
    /// ```ebnf
    /// operation_argument_statement =
    ///     "with", " ", local_view_name, " looking at ", operation_argument_source, terminator ;
    /// ```
    fn parse_operation_argument_statement(
        &mut self,
        executing_definition: ExecutingDefinition,
        fqun: &FqunWithCanonicalText<'py, 'source>,
    ) -> ParseResult<ast::OperationArgumentStatement<'py>> {
        let start = self.scanner.position;
        // The statement is not an operation argument statement.
        if !self.scanner.consume(WITH) {
            return Err(self.invalid_operation_arguments_block_statement());
        }
        // The line ends, or a non-letter character comes, where the view's
        // typed name belongs.
        if !self.space_before_word()? {
            return Err(self.expected_view());
        }
        let (view, _) = self.parse_view_reference()?;
        // There is no ` looking at` after the view.
        if !self.scanner.consume(SPACE_LOOKING_AT) {
            return Err(
                self.missing_connecting_word(SyntaxErrors::invalid_operation_argument_syntax)
            );
        }
        // The line ends, or a non-letter character comes, where what the view
        // looks at belongs.
        if !self.space_before_word()? {
            return Err(self.expected_argument_source());
        }
        let (looking_at, end) = self.parse_operation_argument_source(executing_definition, fqun)?;
        let location = self.ast.location(start, end)?;
        Ok(self
            .ast
            .operation_argument_statement(location, view, looking_at)?)
    }

    /// Parses what an operation argument's view in an `executing_definition`
    /// looks at, whose references take their default FQUN from `fqun`, and the
    /// `.` after it, and returns it with the position after the `.`.
    ///
    /// ```ebnf
    /// operation_argument_source = ( position_reference | local_view_name | literal ), terminator ;
    /// ```
    // An action's arguments may not look at views, and an operation's may not
    // look at positions. The argument is still the one that was meant, so
    // these get diagnostics and stay in the AST.
    fn parse_operation_argument_source(
        &mut self,
        executing_definition: ExecutingDefinition,
        fqun: &FqunWithCanonicalText<'py, 'source>,
    ) -> ParseResult<(
        ast::PositionReferenceOrLocalTypedNameReferenceOrLiteral<'py>,
        Position,
    )> {
        let start = self.scanner.position;
        if self.scanner.next_bytes_are(VIEW) {
            let (view, source_typed_name) = self.parse_view_reference()?;
            // An action's argument looks at a view.
            if executing_definition == ExecutingDefinition::Action {
                let last = self.scanner.position.previous_column();
                self.diagnostics.operation_argument_view_diagnostic(
                    start,
                    last,
                    source_typed_name.to_str()?,
                )?;
            }
            let end = self.parse_statement_terminator()?;
            return Ok((view.into(), end));
        }
        if executing_definition == ExecutingDefinition::Action
            || self.scanner.next_bytes_are(LITERAL)
        {
            return self.parse_value_source(fqun, Self::expected_argument_source);
        }
        // What the view looks at is neither a position reference, a view, nor
        // a literal.
        if !POSITION_OR_ACTION
            .iter()
            .any(|&(keyword, _)| self.scanner.next_bytes_are(keyword))
        {
            return Err(self.expected_argument_source());
        }
        let reference = self.parse_position_reference(fqun)?;
        // An operation's argument looks at a position.
        self.operation_argument_position_diagnostic(start, &reference)?;
        let end = self.parse_reference_terminator()?;
        Ok((reference.into(), end))
    }

    /// Parses a typed name with the name type `view`.
    ///
    /// ```ebnf
    /// local_view_name = "view", "<", local_name, ">" ;
    /// ```
    fn parse_view_reference(
        &mut self,
    ) -> ParseResult<(ast::LocalTypedNameReference<'py>, Bound<'py, PyString>)> {
        let start = self.scanner.position;
        // The name type is not `view`.
        if !self.scanner.consume(VIEW) {
            return Err(self.expected_view());
        }
        let name = self.parse_local_name_content()?;
        let location = self.ast.location(start, self.scanner.position)?;
        Ok(self.local_typed_name_reference(location, ast::NameType::View, name)?)
    }
}

// The functions that only run on an error path.
impl<'py, 'source> Parser<'py, 'source> {
    /// Adds the diagnostic for an operation's argument that begins at `start`
    /// and looks at the position `reference`, which ends at the scanner's
    /// position.
    #[cold]
    #[inline(never)]
    fn operation_argument_position_diagnostic(
        &mut self,
        start: Position,
        reference: &ast::PositionReference<'py>,
    ) -> PyResult<()> {
        // The parser keeps only the full typed name of each part, so this
        // joins the source typed names that the parts' nodes hold.
        let node = &reference.0;
        let position_name = node
            .getattr(intern!(node.py(), "source_chained_name"))?
            .cast_into::<PyString>()?;
        let last = self.scanner.position.previous_column();
        self.diagnostics.operation_argument_position_diagnostic(
            start,
            last,
            position_name.to_str()?,
        )
    }

    /// Returns the error for a name type, at the scanner's position, that is
    /// not the one an operation execution statement that executes an
    /// operation of `kind` allows.
    #[cold]
    #[inline(never)]
    fn wrong_operation_name_type(&self, kind: OperationKind) -> ParseError {
        match kind {
            OperationKind::Value => self.expected_operation(),
            OperationKind::Encoding => self.expected_encoding_operation(),
        }
    }

    /// Returns the error for a name type, at the scanner's position, that is
    /// not `operation`, in a Value Operation Execution Statement.
    #[cold]
    #[inline(never)]
    fn expected_operation(&self) -> ParseError {
        if let Some(error) = self.disallowed_character_after(OPERATION) {
            return error;
        }
        let start = self.scanner.position;
        self.errors
            .expected_operation(start, self.scanner.end_of_word())
    }

    /// Returns the error for a name type, at the scanner's position, that is
    /// not `encoding_operation`, in an Encoding Operation Execution Statement.
    #[cold]
    #[inline(never)]
    fn expected_encoding_operation(&self) -> ParseError {
        if let Some(error) = self.disallowed_character_after(ENCODING_OPERATION) {
            return error;
        }
        let start = self.scanner.position;
        self.errors
            .expected_encoding_operation(start, self.scanner.end_of_word())
    }

    /// Returns the error for a name type, at the scanner's position, that is
    /// not `view`, where a view's typed name belongs.
    #[cold]
    #[inline(never)]
    fn expected_view(&self) -> ParseError {
        if let Some(error) = self.disallowed_character_after(VIEW) {
            return error;
        }
        let start = self.scanner.position;
        self.errors.expected_view(start, self.scanner.end_of_word())
    }

    /// Returns the error for the name type, at the scanner's position, of
    /// what an operation argument's view looks at that is not `position`,
    /// `action`, `view`, or `literal`.
    #[cold]
    #[inline(never)]
    fn expected_argument_source(&self) -> ParseError {
        if let Some(error) = self.disallowed_character_after_any(&[POSITION, ACTION, VIEW, LITERAL])
        {
            return error;
        }
        let start = self.scanner.position;
        self.errors
            .expected_value_source(start, self.scanner.end_of_word())
    }

    /// Returns the error for a statement at the scanner's position in an
    /// operation arguments block that is not an operation argument statement.
    #[cold]
    #[inline(never)]
    fn invalid_operation_arguments_block_statement(&self) -> ParseError {
        if let Some(error) = self.disallowed_character_after(WITH) {
            return error;
        }
        let start = self.scanner.position;
        self.errors
            .invalid_operation_arguments_block(start, self.end_of_line())
    }
}
