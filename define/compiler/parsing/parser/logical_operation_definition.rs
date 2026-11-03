//! Logical operation definitions and their Logical Operation View Definitions.

use crate::ast;
use crate::parse_error::{ParseError, ParseResult};
use crate::parser::Parser;
use crate::parser::lines::LineInBlock;
use crate::parser::operation_definition::VIEW_DIRECTION_STATEMENT_STARTS;
use crate::scanner::Position;
use terminals::{DEFINE_THE, DEFINE_THE_VIEW, VIEW};

impl<'py, 'source> Parser<'py, 'source> {
    /// Parses the rest of a logical operation definition after its
    /// `logical_operation`, given the positions of the definition's start and
    /// of its `logical_operation`, and returns the definition with the
    /// position after its `}`.
    ///
    /// ```ebnf
    /// logical_operation_definition =
    ///     "define the", " ",
    ///     fully_qualified_logical_operation_name,
    ///     logical_operation_definition_block ;
    /// logical_operation_definition_block =
    ///     block_open,
    ///     logical_operation_view_definition,
    ///     { logical_operation_view_definition },
    ///     block_close ;
    /// ```
    pub(crate) fn parse_logical_operation_definition(
        &mut self,
        start: Position,
        typed_name_start: Position,
    ) -> ParseResult<(ast::LogicalOperationDefinition<'py>, Position)> {
        let (typed_name, _) = self.parse_global_typed_name_in_definition(
            typed_name_start,
            ast::NameType::LogicalOperation,
        )?;
        let block_open_end = self.parse_block_open()?;
        match self.next_line_in_block(0, &[DEFINE_THE_VIEW])? {
            LineInBlock::Statement => {}
            // The block is empty.
            LineInBlock::Close => {
                let close = self.scanner.position;
                return Err(self
                    .errors
                    .missing_logical_operation_view_definition(close, close));
            }
            // The block ends where its first view definition belongs.
            LineInBlock::Unclosed => {
                return Err(self
                    .errors
                    .missing_logical_operation_view_definition(block_open_end, block_open_end));
            }
        }
        let views = self.nodes.start::<ast::LogicalOperationViewDefinition>();
        loop {
            let view_start = self.scanner.position;
            // The statement is not a view definition.
            let Some(view_typed_name_start) =
                self.scanner.consume_definition_start(DEFINE_THE, VIEW)
            else {
                return Err(self.invalid_logical_operation_definition_statement());
            };
            let view =
                self.parse_logical_operation_view_definition(view_start, view_typed_name_start)?;
            self.nodes.push(&views, view);
            match self.next_line_in_block(0, &[DEFINE_THE_VIEW])? {
                LineInBlock::Statement => {}
                LineInBlock::Close => break,
                // The block ends before its `}`.
                LineInBlock::Unclosed => {
                    return Err(self.missing_close_brace(start, block_open_end));
                }
            }
        }
        let views = self.nodes.finish_tuple(views)?;
        let end = self.parse_block_close()?;
        let location = self.ast.location(start, end)?;
        let definition = self
            .ast
            .logical_operation_definition(location, typed_name, views)?;
        Ok((definition, end))
    }

    /// Parses the rest of a Logical Operation View Definition after its
    /// `view`, given the positions of the definition's start and of its
    /// `view`, through the end of its `}` line.
    ///
    /// ```ebnf
    /// logical_operation_view_definition =
    ///     "define the", " ", local_view_name, block_open, view_direction_statements, block_close ;
    /// ```
    fn parse_logical_operation_view_definition(
        &mut self,
        start: Position,
        typed_name_start: Position,
    ) -> ParseResult<ast::LogicalOperationViewDefinition<'py>> {
        let name = self.parse_local_name_content()?;
        let typed_name_location = self.ast.location(typed_name_start, self.scanner.position)?;
        let (typed_name, _) =
            self.local_typed_name_reference(typed_name_location, ast::NameType::View, name)?;
        let block_open_end = self.parse_block_open()?;
        let (is_input, is_output, line, _) =
            self.parse_view_direction_statements(block_open_end, &VIEW_DIRECTION_STATEMENT_STARTS)?;
        match line {
            LineInBlock::Close => {}
            // A statement other than a View Direction Statement follows them.
            LineInBlock::Statement => {
                return Err(self.invalid_logical_operation_view_definition_statement());
            }
            // The block ends before its `}`.
            LineInBlock::Unclosed => {
                return Err(self.missing_close_brace(start, block_open_end));
            }
        }
        let end = self.parse_block_close()?;
        let location = self.ast.location(start, end)?;
        Ok(self
            .ast
            .logical_operation_view_definition(location, typed_name, is_input, is_output)?)
    }
}

// The functions that only run on an error path.
impl<'py, 'source> Parser<'py, 'source> {
    /// Returns the error for a statement at the scanner's position in a
    /// Logical Operation Definition Block that is not a view definition.
    #[cold]
    #[inline(never)]
    fn invalid_logical_operation_definition_statement(&self) -> ParseError {
        if let Some(error) = self.disallowed_character_after(DEFINE_THE_VIEW) {
            return error;
        }
        // The line begins like a view definition, but with extra or missing
        // spaces between two of its words.
        if let Some(error) = self.misspaced_words_in_any(&[DEFINE_THE_VIEW]) {
            return error;
        }
        let start = self.scanner.position;
        self.errors
            .invalid_logical_operation_definition_block(start, self.end_of_line())
    }

    /// Returns the error for a statement at the scanner's position, after the
    /// View Direction Statements of a Logical Operation View Definition, where
    /// its `}` belongs.
    #[cold]
    #[inline(never)]
    fn invalid_logical_operation_view_definition_statement(&self) -> ParseError {
        if let Some(error) = self.disallowed_character_after_any(&VIEW_DIRECTION_STATEMENT_STARTS) {
            return error;
        }
        if let Some(error) = self.misplaced_view_direction_statement() {
            return error;
        }
        // The line begins like a View Direction Statement, but with extra or
        // missing spaces between two of its words.
        if let Some(error) = self.misspaced_words_in_any(&VIEW_DIRECTION_STATEMENT_STARTS) {
            return error;
        }
        let start = self.scanner.position;
        self.errors
            .invalid_logical_operation_view_definition_block(start, self.end_of_line())
    }
}
