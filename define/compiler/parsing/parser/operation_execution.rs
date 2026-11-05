//! Operation execution statements, Logical Operation Execution Statements,
//! and their operation arguments blocks.

use crate::ast;
use crate::node_construction::{Node, NodeTuple};
use crate::parse_error::{ParseError, ParseResult};
use crate::parser::Parser;
use crate::parser::lines::LineInBlock;
use crate::parser::names::FqunWithCanonicalText;
use crate::scanner::Position;
use crate::syntax_errors::SyntaxErrors;
use terminals::{
    BLOCK_OPEN, ENCODING_OPERATION, EXECUTE_THE, EXECUTE_THE_COMPUTER_OPERATION,
    EXECUTE_THE_ENCODING_OPERATION, LITERAL, LOGICAL_OPERATION, NAME_CONTENT_START, OPERATION,
    SPACE_LOOKING_AT, VIEW, WITH,
};

/// The one name type that a Value Operation Execution Statement allows.
const OPERATION_NAME_TYPE: [(&[u8], ast::NameType); 1] = [(OPERATION, ast::NameType::Operation)];
/// The one name type that an Encoding Operation Execution Statement allows.
const ENCODING_OPERATION_NAME_TYPE: [(&[u8], ast::NameType); 1] =
    [(ENCODING_OPERATION, ast::NameType::EncodingOperation)];
/// The one name type that a Logical Operation Execution Statement allows.
const LOGICAL_OPERATION_NAME_TYPE: [(&[u8], ast::NameType); 1] =
    [(LOGICAL_OPERATION, ast::NameType::LogicalOperation)];
/// Parses one argument statement of an operation arguments block, whose
/// references take their default FQUN from the second argument.
type ArgumentParser<'py, 'source, Argument> =
    fn(&mut Parser<'py, 'source>, &FqunWithCanonicalText<'py, 'source>) -> ParseResult<Argument>;

/// Whether an operation is a Value Operation or an Encoding Operation.
#[derive(Clone, Copy)]
pub(crate) enum OperationKind {
    Value,
    Encoding,
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
    /// Parses an operation execution statement in an action, indented
    /// `indentation` spaces, whose references take their default FQUN from
    /// `fqun`, through the end of its last line.
    ///
    /// ```ebnf
    /// operation_execution_statement = "execute the", " ", operation_name, operation_execution_end ;
    /// operation_argument_statement = operation_argument_statement_in_action ;
    /// ```
    pub(crate) fn parse_operation_execution_statement_in_action(
        &mut self,
        indentation: usize,
        fqun: &FqunWithCanonicalText<'py, 'source>,
    ) -> ParseResult<ast::OperationExecutionStatementOfPositionReferenceOrLiteral<'py>> {
        let (location, operation, arguments) = self.parse_operation_execution_statement(
            OperationKind::Value,
            Self::expected_operation,
            Self::parse_operation_argument_statement_in_action,
            indentation,
            fqun,
        )?;
        Ok(self
            .ast
            .operation_execution_statement_of_position_reference_or_literal(
                location, operation, arguments,
            )?)
    }

    /// Parses an operation execution statement in a Value Operation or an
    /// Encoding Operation that executes an operation of `kind`, indented
    /// `indentation` spaces, whose references take their default FQUN from
    /// `fqun`, through the end of its last line.
    ///
    /// ```ebnf
    /// operation_execution_statement = "execute the", " ", operation_name, operation_execution_end ;
    /// operation_argument_statement = operation_argument_statement_in_operation ;
    /// ```
    pub(crate) fn parse_operation_execution_statement_in_operation(
        &mut self,
        kind: OperationKind,
        indentation: usize,
        fqun: &FqunWithCanonicalText<'py, 'source>,
    ) -> ParseResult<ast::OperationExecutionStatementOfLocalTypedNameReferenceOrLiteral<'py>> {
        let (location, operation, arguments) = self.parse_operation_execution_statement(
            kind,
            // A Value Operation may also execute logical operations.
            Self::expected_operation_or_logical_operation,
            Self::parse_operation_argument_statement_in_operation,
            indentation,
            fqun,
        )?;
        Ok(self
            .ast
            .operation_execution_statement_of_local_typed_name_reference_or_literal(
                location, operation, arguments,
            )?)
    }

    /// Parses an operation execution statement that executes an operation of
    /// `kind`, indented `indentation` spaces, whose references take their
    /// default FQUN from `fqun`, through the end of its last line, and returns
    /// its location, the operation it executes, and its arguments.
    /// `wrong_value_operation` returns the error for a name type that is not
    /// allowed where a Value Operation's name belongs, and `parse_argument`
    /// parses each argument.
    ///
    /// ```ebnf
    /// operation_execution_statement = "execute the", " ", operation_name, operation_execution_end ;
    /// operation_execution_end = terminator | operation_arguments_block ;
    /// ```
    fn parse_operation_execution_statement<Argument: Node<'py>>(
        &mut self,
        kind: OperationKind,
        wrong_value_operation: fn(&Self) -> ParseError,
        parse_argument: ArgumentParser<'py, 'source, Argument>,
        indentation: usize,
        fqun: &FqunWithCanonicalText<'py, 'source>,
    ) -> ParseResult<(
        ast::SourceLocation<'py>,
        ast::GlobalTypedNameReference<'py>,
        NodeTuple<'py, Argument>,
    )> {
        let start = self.scanner.position;
        self.scanner.consume(EXECUTE_THE);
        let (name_type, wrong_name_type): (_, fn(&Self) -> ParseError) = match kind {
            OperationKind::Encoding => (
                &ENCODING_OPERATION_NAME_TYPE,
                Self::expected_encoding_operation,
            ),
            OperationKind::Value => (&OPERATION_NAME_TYPE, wrong_value_operation),
        };
        // The line ends, or a non-letter character comes, where the operation's
        // typed name belongs.
        if !self.space_before_word()? {
            return Err(wrong_name_type(self));
        }
        let (operation, _) =
            self.parse_typed_global_name_reference(fqun, name_type, wrong_name_type)?;
        if self.scanner.next_bytes_are(BLOCK_OPEN) {
            let (arguments, end) =
                self.parse_operation_arguments_block(parse_argument, start, indentation, fqun)?;
            let location = self.ast.location(start, end)?;
            return Ok((location, operation, arguments));
        }
        // There is no `.` or ` {`.
        let Some(end) = self.parse_terminator()? else {
            return Err(self.missing_terminator_or_brace());
        };
        let arguments = self.nodes.start::<Argument>();
        let arguments = self.nodes.finish_tuple(arguments)?;
        let location = self.ast.location(start, end)?;
        Ok((location, operation, arguments))
    }

    /// Parses a Logical Operation Execution Statement in a Value Operation,
    /// indented `indentation` spaces, whose references take their default FQUN
    /// from `fqun`, through the end of its last line.
    ///
    /// ```ebnf
    /// logical_operation_execution_statement =
    ///     "execute the", " ", logical_operation_name, operation_arguments_block ;
    /// ```
    pub(crate) fn parse_logical_operation_execution_statement(
        &mut self,
        indentation: usize,
        fqun: &FqunWithCanonicalText<'py, 'source>,
    ) -> ParseResult<ast::LogicalOperationExecutionStatement<'py>> {
        let start = self.scanner.position;
        // The caller found `execute the logical_operation`, so exactly one
        // space follows `execute the`.
        self.scanner.consume_bytes(EXECUTE_THE.len() + 1);
        let (logical_operation, _) = self.parse_typed_global_name_reference(
            fqun,
            &LOGICAL_OPERATION_NAME_TYPE,
            Self::expected_operation_or_logical_operation,
        )?;
        let (arguments, end) = self.parse_operation_arguments_block(
            Self::parse_logical_operation_argument_statement,
            start,
            indentation,
            fqun,
        )?;
        let location = self.ast.location(start, end)?;
        Ok(self.ast.logical_operation_execution_statement(
            location,
            logical_operation,
            arguments,
        )?)
    }

    /// Parses the operation arguments block of the operation execution
    /// statement that begins at `start`, indented `indentation` spaces, whose
    /// references take their default FQUN from `fqun`, with `parse_argument`,
    /// and returns its arguments with the position after its `}`.
    ///
    /// ```ebnf
    /// operation_arguments_block =
    ///     block_open,
    ///     operation_argument_statement,
    ///     { operation_argument_statement },
    ///     block_close ;
    /// ```
    fn parse_operation_arguments_block<Argument: Node<'py>>(
        &mut self,
        parse_argument: ArgumentParser<'py, 'source, Argument>,
        start: Position,
        indentation: usize,
        fqun: &FqunWithCanonicalText<'py, 'source>,
    ) -> ParseResult<(NodeTuple<'py, Argument>, Position)> {
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
        let arguments = self.nodes.start::<Argument>();
        loop {
            let argument = parse_argument(self, fqun)?;
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

    /// Parses an operation argument statement in an action, whose references
    /// take their default FQUN from `fqun`, through the end of its line.
    ///
    /// ```ebnf
    /// operation_argument_statement_in_action =
    ///     operation_argument_view, ( position_reference | literal ), terminator ;
    /// ```
    fn parse_operation_argument_statement_in_action(
        &mut self,
        fqun: &FqunWithCanonicalText<'py, 'source>,
    ) -> ParseResult<ast::OperationArgumentStatementOfPositionReferenceOrLiteral<'py>> {
        let (start, view) =
            self.parse_operation_argument_view(Self::expected_position_or_action_or_literal)?;
        let (looking_at, end) =
            self.parse_value_source(fqun, Self::expected_position_or_action_or_literal)?;
        let location = self.ast.location(start, end)?;
        Ok(self
            .ast
            .operation_argument_statement_of_position_reference_or_literal(
                location, view, looking_at,
            )?)
    }

    /// Parses an operation argument statement in a Value Operation or an
    /// Encoding Operation, whose references take their default FQUN from
    /// `fqun`, through the end of its line.
    ///
    /// ```ebnf
    /// operation_argument_statement_in_operation =
    ///     operation_argument_view, ( local_view_name | literal ), terminator ;
    /// ```
    fn parse_operation_argument_statement_in_operation(
        &mut self,
        fqun: &FqunWithCanonicalText<'py, 'source>,
    ) -> ParseResult<ast::OperationArgumentStatementOfLocalTypedNameReferenceOrLiteral<'py>> {
        let (start, view) = self.parse_operation_argument_view(Self::expected_view_or_literal)?;
        let looking_at: ast::LocalTypedNameReferenceOrLiteral<'py> =
            if self.scanner.next_bytes_are(VIEW) {
                self.parse_view_reference()?.into()
            } else if self.scanner.next_bytes_are(LITERAL) {
                self.parse_literal(fqun)?.into()
            } else {
                // What the view looks at is neither a view nor a literal.
                return Err(self.expected_view_or_literal());
            };
        let end = self.parse_statement_terminator()?;
        let location = self.ast.location(start, end)?;
        Ok(self
            .ast
            .operation_argument_statement_of_local_typed_name_reference_or_literal(
                location, view, looking_at,
            )?)
    }

    /// Parses an operation argument statement in a Logical Operation Execution
    /// Statement through the end of its line. Its view may only look at a
    /// view.
    ///
    /// ```ebnf
    /// logical_operation_argument_statement =
    ///     operation_argument_view, local_view_name, terminator ;
    /// ```
    fn parse_logical_operation_argument_statement(
        &mut self,
        _fqun: &FqunWithCanonicalText<'py, 'source>,
    ) -> ParseResult<ast::OperationArgumentStatementOfLocalTypedNameReference<'py>> {
        let (start, view) =
            self.parse_operation_argument_view(Self::expected_view_in_logical_operation)?;
        // What the view looks at is not a view.
        if !self.scanner.next_bytes_are(VIEW) {
            return Err(self.expected_view_in_logical_operation());
        }
        let looking_at = self.parse_view_reference()?;
        let end = self.parse_statement_terminator()?;
        let location = self.ast.location(start, end)?;
        Ok(self
            .ast
            .operation_argument_statement_of_local_typed_name_reference(
                location, view, looking_at,
            )?)
    }

    /// Parses the start of an operation argument statement through the space
    /// before what its view looks at, and returns the position where the
    /// statement begins with its view. `wrong_source` returns the error for
    /// the line ending, or a non-letter character, where what the view looks
    /// at belongs.
    ///
    /// ```ebnf
    /// operation_argument_view = "with", " ", local_view_name, " looking at ", " " ;
    /// ```
    fn parse_operation_argument_view(
        &mut self,
        wrong_source: fn(&Self) -> ParseError,
    ) -> ParseResult<(Position, ast::LocalTypedNameReference<'py>)> {
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
        let view = self.parse_view_reference()?;
        // There is no ` looking at` after the view.
        if !self.scanner.consume(SPACE_LOOKING_AT) {
            return Err(
                self.missing_connecting_word(SyntaxErrors::invalid_operation_argument_syntax)
            );
        }
        // The line ends, or a non-letter character comes, where what the view
        // looks at belongs.
        if !self.space_before_word()? {
            return Err(wrong_source(self));
        }
        Ok((start, view))
    }

    /// Parses a typed name with the name type `view`.
    ///
    /// ```ebnf
    /// local_view_name = "view", "<", local_name, ">" ;
    /// ```
    pub(crate) fn parse_view_reference(
        &mut self,
    ) -> ParseResult<ast::LocalTypedNameReference<'py>> {
        let start = self.scanner.position;
        // The name type is not `view`.
        if !self.scanner.consume(VIEW) {
            return Err(self.expected_view());
        }
        let name = self.parse_local_name_content()?;
        let location = self.ast.location(start, self.scanner.position)?;
        let (view, _) = self.local_typed_name_reference(location, ast::NameType::View, name)?;
        Ok(view)
    }
}

// The functions that only run on an error path.
impl<'py, 'source> Parser<'py, 'source> {
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
    /// neither `operation` nor `logical_operation`, in an execution statement
    /// in a Value Operation.
    #[cold]
    #[inline(never)]
    fn expected_operation_or_logical_operation(&self) -> ParseError {
        if let Some(error) = self.disallowed_character_after_any(&[OPERATION, LOGICAL_OPERATION]) {
            return error;
        }
        let start = self.scanner.position;
        self.errors
            .expected_operation_or_logical_operation(start, self.scanner.end_of_word())
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
    pub(crate) fn expected_view(&self) -> ParseError {
        if let Some(error) = self.disallowed_character_after(VIEW) {
            return error;
        }
        let start = self.scanner.position;
        self.errors.expected_view(start, self.scanner.end_of_word())
    }

    /// Returns the error for the name type, at the scanner's position, of
    /// what an operation argument's view in an operation definition looks at
    /// that is not `view` or `literal`.
    #[cold]
    #[inline(never)]
    fn expected_view_or_literal(&self) -> ParseError {
        if let Some(error) = self.disallowed_character_after_any(&[VIEW, LITERAL]) {
            return error;
        }
        let start = self.scanner.position;
        self.errors
            .expected_view_or_literal(start, self.scanner.end_of_word())
    }

    /// Returns the error for what an operation argument's view in a Logical
    /// Operation Execution Statement looks at, at the scanner's position, that
    /// is not `view`.
    #[cold]
    #[inline(never)]
    fn expected_view_in_logical_operation(&self) -> ParseError {
        self.expected_view_instead_of_literal(SyntaxErrors::literal_in_logical_operation_execution)
    }

    /// Returns the error for a name type, at the scanner's position, that is
    /// not `view`, where only a view's typed name may be. `literal_error`
    /// returns the error for a literal there.
    #[cold]
    #[inline(never)]
    pub(crate) fn expected_view_instead_of_literal(
        &self,
        literal_error: fn(&SyntaxErrors<'py>, Position, Position) -> ParseError,
    ) -> ParseError {
        let is_literal = self
            .scanner
            .rest_after(LITERAL)
            .is_some_and(|rest| rest.first() == Some(&NAME_CONTENT_START));
        if !is_literal {
            return self.expected_view();
        }
        literal_error(
            &self.errors,
            self.scanner.position,
            self.scanner.end_of_word(),
        )
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
