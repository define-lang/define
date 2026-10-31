//! Value definitions and their Logical Operation Support Statements.

use crate::ast;
use crate::parse_error::{ParseError, ParseResult};
use crate::parser::Parser;
use crate::parser::lines::{INDENTATION_WIDTH, LineInBlock};
use crate::parser::names::FqunWithCanonicalText;
use crate::scanner::Position;
use terminals::{IT_MAY_BE_READ, IT_MAY_BE_WRITTEN, IT_SUPPORTS_THE, LOGICAL_OPERATION};

/// The one name type that a Logical Operation Support Statement allows.
const LOGICAL_OPERATION_NAME_TYPE: [(&[u8], ast::NameType); 1] =
    [(LOGICAL_OPERATION, ast::NameType::LogicalOperation)];
/// The words that begin each statement a Logical Operation Support Block may
/// have.
const LOGICAL_OPERATION_SUPPORT_BLOCK_STATEMENT_STARTS: [&[u8]; 2] =
    [IT_MAY_BE_READ, IT_MAY_BE_WRITTEN];

impl<'py, 'source> Parser<'py, 'source> {
    /// Parses the rest of a value definition after its `value`, given the
    /// positions of the definition's start and of its `value`, and returns the
    /// definition with the position after its `}`.
    ///
    /// ```ebnf
    /// value_definition = "define the potential", " ", fully_qualified_value_name, value_definition_block ;
    /// value_definition_block =
    ///     block_open,
    ///     logical_operation_support_statement,
    ///     { logical_operation_support_statement },
    ///     block_close ;
    /// ```
    pub(crate) fn parse_value_definition(
        &mut self,
        start: Position,
        typed_name_start: Position,
    ) -> ParseResult<(ast::ValueDefinition<'py>, Position)> {
        let (typed_name, fqun) =
            self.parse_global_typed_name_in_definition(typed_name_start, ast::NameType::Value)?;
        let block_open_end = self.parse_block_open()?;
        match self.next_line_in_block(0, &[IT_SUPPORTS_THE])? {
            LineInBlock::Statement => {}
            // The block is empty.
            LineInBlock::Close => {
                let close = self.scanner.position;
                return Err(self
                    .errors
                    .missing_logical_operation_support_statement(close, close));
            }
            // The block ends where its first Logical Operation Support
            // Statement belongs.
            LineInBlock::Unclosed => {
                return Err(self
                    .errors
                    .missing_logical_operation_support_statement(block_open_end, block_open_end));
            }
        }
        let statements = self.nodes.start::<ast::LogicalOperationSupportStatement>();
        loop {
            let statement = self.parse_logical_operation_support_statement(&fqun)?;
            self.nodes.push(&statements, statement);
            match self.next_line_in_block(0, &[IT_SUPPORTS_THE])? {
                LineInBlock::Statement => {}
                LineInBlock::Close => break,
                // The block ends before its `}`.
                LineInBlock::Unclosed => {
                    return Err(self.missing_close_brace(start, block_open_end));
                }
            }
        }
        let statements = self.nodes.finish_tuple(statements)?;
        let end = self.parse_block_close()?;
        let location = self.ast.location(start, end)?;
        let definition = self
            .ast
            .value_definition(location, typed_name, statements)?;
        Ok((definition, end))
    }

    /// Parses a Logical Operation Support Statement, whose reference takes its
    /// default FQUN from `fqun`, through the end of its `}` line.
    ///
    /// ```ebnf
    /// logical_operation_support_statement =
    ///     "it supports the", " ", logical_operation_name, logical_operation_support_block ;
    /// logical_operation_support_block =
    ///     block_open,
    ///     (
    ///         ( "it may be read", terminator, [ "it may be written", terminator ] )
    ///         | ( "it may be written", terminator )
    ///     ),
    ///     block_close ;
    /// ```
    fn parse_logical_operation_support_statement(
        &mut self,
        fqun: &FqunWithCanonicalText<'py, 'source>,
    ) -> ParseResult<ast::LogicalOperationSupportStatement<'py>> {
        let start = self.scanner.position;
        // The statement is not a Logical Operation Support Statement.
        if !self.scanner.consume(IT_SUPPORTS_THE) {
            return Err(self.invalid_value_definition_statement());
        }
        // The line ends, or a non-letter character comes, where the typed name
        // belongs.
        if !self.space_before_word()? {
            return Err(self.expected_logical_operation_name_type());
        }
        let (logical_operation, _) = self.parse_typed_global_name_reference(
            fqun,
            &LOGICAL_OPERATION_NAME_TYPE,
            Self::expected_logical_operation_name_type,
        )?;
        let block_open_end = self.parse_block_open()?;
        let mut line = self.next_line_in_block(
            INDENTATION_WIDTH,
            &LOGICAL_OPERATION_SUPPORT_BLOCK_STATEMENT_STARTS,
        )?;
        let may_be_read =
            matches!(line, LineInBlock::Statement) && self.scanner.consume(IT_MAY_BE_READ);
        if may_be_read {
            self.parse_statement_terminator()?;
            line = self.next_line_in_block(
                INDENTATION_WIDTH,
                &LOGICAL_OPERATION_SUPPORT_BLOCK_STATEMENT_STARTS,
            )?;
        }
        let may_be_written =
            matches!(line, LineInBlock::Statement) && self.scanner.consume(IT_MAY_BE_WRITTEN);
        if may_be_written {
            self.parse_statement_terminator()?;
            line = self.next_line_in_block(
                INDENTATION_WIDTH,
                &LOGICAL_OPERATION_SUPPORT_BLOCK_STATEMENT_STARTS,
            )?;
        }
        let has_statement = may_be_read || may_be_written;
        match line {
            LineInBlock::Close if has_statement => {}
            // A statement comes where only the block's `}` belongs, or the
            // block's first statement is neither `it may be read.` nor
            // `it may be written.`.
            LineInBlock::Statement => {
                return Err(self.invalid_logical_operation_support_block_statement());
            }
            // The block ends before its `}`.
            LineInBlock::Unclosed if has_statement => {
                return Err(self.missing_close_brace(start, block_open_end));
            }
            // The block is empty.
            LineInBlock::Close => {
                let close = self.scanner.position;
                return Err(self
                    .errors
                    .invalid_logical_operation_support_block(close, close));
            }
            // The block ends where its first statement belongs.
            LineInBlock::Unclosed => {
                return Err(self
                    .errors
                    .invalid_logical_operation_support_block(block_open_end, block_open_end));
            }
        }
        let end = self.parse_block_close()?;
        let location = self.ast.location(start, end)?;
        Ok(self.ast.logical_operation_support_statement(
            location,
            logical_operation,
            may_be_read,
            may_be_written,
        )?)
    }
}

// The functions that only run on an error path.
impl<'py, 'source> Parser<'py, 'source> {
    /// Returns the error for a statement at the scanner's position in a Value
    /// Definition Block that is not a Logical Operation Support Statement.
    #[cold]
    #[inline(never)]
    fn invalid_value_definition_statement(&self) -> ParseError {
        if let Some(error) = self.disallowed_character_after(IT_SUPPORTS_THE) {
            return error;
        }
        // The line begins like a Logical Operation Support Statement, but with
        // extra or missing spaces between two of its words.
        if let Some(error) = self.misspaced_words_in_any(&[IT_SUPPORTS_THE]) {
            return error;
        }
        let start = self.scanner.position;
        self.errors
            .invalid_value_definition_block(start, self.end_of_line())
    }

    /// Returns the error for a name type, at the scanner's position, that is
    /// not `logical_operation`, in a Logical Operation Support Statement.
    #[cold]
    #[inline(never)]
    fn expected_logical_operation_name_type(&self) -> ParseError {
        if let Some(error) = self.disallowed_character_after(LOGICAL_OPERATION) {
            return error;
        }
        let start = self.scanner.position;
        self.errors
            .invalid_value_definition_block(start, self.scanner.end_of_word())
    }

    /// Returns the error for a statement at the scanner's position in a
    /// Logical Operation Support Block that does not belong there.
    #[cold]
    #[inline(never)]
    fn invalid_logical_operation_support_block_statement(&self) -> ParseError {
        if let Some(error) =
            self.disallowed_character_after_any(&LOGICAL_OPERATION_SUPPORT_BLOCK_STATEMENT_STARTS)
        {
            return error;
        }
        // The line begins like a statement of the block, but with extra or
        // missing spaces between two of its words.
        if let Some(error) =
            self.misspaced_words_in_any(&LOGICAL_OPERATION_SUPPORT_BLOCK_STATEMENT_STARTS)
        {
            return error;
        }
        let start = self.scanner.position;
        self.errors
            .invalid_logical_operation_support_block(start, self.end_of_line())
    }
}
