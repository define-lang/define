//! Value Operation and Encoding Operation definitions, their interface views,
//! and their operation statements blocks.

use crate::ast;
use crate::node_construction::NodeTuple;
use crate::parse_error::{ParseError, ParseResult};
use crate::parser::Parser;
use crate::parser::lines::{INDENTATION_WIDTH, LineInBlock};
use crate::parser::names::FqunWithCanonicalText;
use crate::parser::operation_execution::OperationKind;
use crate::scanner::Position;
use terminals::{
    DEFINE_THE, DEFINE_THE_VIEW, EXECUTE_THE, IT_DOES, IT_IS_READ, IT_IS_WRITTEN,
    IT_MAY_ONLY_CONTAIN_PARTICLES_WHERE, VIEW,
};

/// How far the lines of an operation definition block, which is always at
/// the top level, are indented.
const OPERATION_DEFINITION_BLOCK_INDENTATION: usize = INDENTATION_WIDTH;
/// The words that begin each statement an operation definition block may
/// have.
const OPERATION_DEFINITION_STATEMENT_STARTS: [&[u8]; 2] = [DEFINE_THE_VIEW, IT_DOES];
/// The words that begin each View Direction Statement.
const VIEW_DIRECTION_STATEMENT_STARTS: [&[u8]; 2] = [IT_IS_READ, IT_IS_WRITTEN];
/// The words that begin each statement a view definition block may have.
const VIEW_DEFINITION_STATEMENT_STARTS: [&[u8]; 3] = [
    IT_IS_READ,
    IT_IS_WRITTEN,
    IT_MAY_ONLY_CONTAIN_PARTICLES_WHERE,
];

impl<'py, 'source> Parser<'py, 'source> {
    /// Parses the rest of the definition of an operation of `kind` after its
    /// name type, given the positions of the definition's start and of its
    /// name type, and returns the definition with the position after its `}`.
    ///
    /// ```ebnf
    /// operation_definition = "define the", " ", fully_qualified_operation_name, operation_definition_block ;
    /// operation_definition_block =
    ///     block_open,
    ///     { view_definition },
    ///     operation_statements_block,
    ///     block_close ;
    /// ```
    pub(crate) fn parse_operation_definition(
        &mut self,
        kind: OperationKind,
        start: Position,
        typed_name_start: Position,
    ) -> ParseResult<(ast::GlobalDefinition<'py>, Position)> {
        let (name_content, name_text, fqun) = self.parse_global_name_definition_content()?;
        let typed_name_location = self.ast.location(typed_name_start, self.scanner.position)?;
        let name_type = match kind {
            OperationKind::Value => ast::NameType::Operation,
            OperationKind::Encoding => ast::NameType::EncodingOperation,
        };
        let typed_name = self.global_typed_name_in_definition(
            typed_name_location,
            name_type,
            name_content,
            name_text,
        )?;
        let block_open_end = self.parse_block_open()?;
        let (views, line, content_end) = self.parse_interface_views(block_open_end, &fqun)?;
        let statements = self.parse_operation_statements_block(kind, line, content_end, &fqun)?;
        let end = self.parse_block_close_after_content(
            start,
            block_open_end,
            0,
            Self::statement_instead_of_close_brace,
        )?;
        let location = self.ast.location(start, end)?;
        let definition = match kind {
            OperationKind::Value => self
                .ast
                .value_operation_definition(location, typed_name, views, statements)?
                .into(),
            OperationKind::Encoding => self
                .ast
                .encoding_operation_definition(location, typed_name, views, statements)?
                .into(),
        };
        Ok((definition, end))
    }

    /// Parses the view definitions at the start of an operation definition
    /// block, after its `{` at `block_open_end`, whose references take their
    /// default FQUN from `fqun`. Returns them with the line in the block after
    /// them and where the block's content ends before that line.
    ///
    /// ```ebnf
    /// { view_definition }
    /// ```
    fn parse_interface_views(
        &mut self,
        block_open_end: Position,
        fqun: &FqunWithCanonicalText<'py, 'source>,
    ) -> ParseResult<(
        NodeTuple<'py, ast::ViewDefinition<'py>>,
        LineInBlock,
        Position,
    )> {
        let views = self.ast.start_tuple::<ast::ViewDefinition>();
        let mut content_end = block_open_end;
        loop {
            let line = self.next_line_in_block(0, &OPERATION_DEFINITION_STATEMENT_STARTS)?;
            if !matches!(line, LineInBlock::Statement) {
                return Ok((self.ast.finish_tuple(views)?, line, content_end));
            }
            let start = self.scanner.position;
            let Some(typed_name_start) = self.scanner.consume_definition_start(DEFINE_THE, VIEW)
            else {
                return Ok((self.ast.finish_tuple(views)?, line, content_end));
            };
            let (view, end) = self.parse_view_definition(start, typed_name_start, fqun)?;
            self.ast.push(&views, view);
            content_end = end;
        }
    }

    /// Parses the rest of a view definition after its `view`, given the
    /// positions of the definition's start and of its `view`, whose references
    /// take their default FQUN from `fqun`, and returns it with the position
    /// after its `}`.
    ///
    /// ```ebnf
    /// view_definition = "define the", " ", local_view_name, view_definition_block ;
    /// view_definition_block =
    ///     block_open,
    ///     view_direction_statements,
    ///     view_constraint_block,
    ///     block_close ;
    /// ```
    fn parse_view_definition(
        &mut self,
        start: Position,
        typed_name_start: Position,
        fqun: &FqunWithCanonicalText<'py, 'source>,
    ) -> ParseResult<(ast::ViewDefinition<'py>, Position)> {
        let name = self.parse_local_name_content()?;
        let typed_name_location = self.ast.location(typed_name_start, self.scanner.position)?;
        let (typed_name, _) =
            self.local_typed_name_reference(typed_name_location, ast::NameType::View, name)?;
        let block_open_end = self.parse_block_open()?;
        let (is_input, is_output, line, content_end) =
            self.parse_view_direction_statements(block_open_end)?;
        match line {
            LineInBlock::Statement => {}
            // The block closes before its position constraint block.
            LineInBlock::Close => {
                let close = self.scanner.position;
                return Err(self.errors.missing_view_constraint_block(close, close));
            }
            // The block ends before its position constraint block.
            LineInBlock::Unclosed => {
                return Err(self
                    .errors
                    .missing_view_constraint_block(content_end, content_end));
            }
        }
        let constraints_start = self.scanner.position;
        // The statement after the view direction statements is not a position
        // constraint block.
        if !self.scanner.consume(IT_MAY_ONLY_CONTAIN_PARTICLES_WHERE) {
            return Err(self.invalid_view_definition_statement());
        }
        let constraints = self.parse_position_constraint_block(
            constraints_start,
            OPERATION_DEFINITION_BLOCK_INDENTATION + INDENTATION_WIDTH,
            fqun,
        )?;
        let end = self.parse_block_close_after_content(
            start,
            block_open_end,
            OPERATION_DEFINITION_BLOCK_INDENTATION,
            Self::statement_instead_of_view_close,
        )?;
        let location = self.ast.location(start, end)?;
        let definition =
            self.ast
                .view_definition(location, typed_name, is_input, is_output, constraints)?;
        Ok((definition, end))
    }

    /// Parses the View Direction Statements at the start of a view definition
    /// block, after its `{` at `block_open_end`. Returns whether the view is
    /// read and whether it is written, with the line in the block after them
    /// and where the block's content ends before that line.
    ///
    /// ```ebnf
    /// view_direction_statements =
    ///     ( "it is read", terminator, [ "it is written", terminator ] )
    ///     | ( "it is written", terminator ) ;
    /// ```
    fn parse_view_direction_statements(
        &mut self,
        block_open_end: Position,
    ) -> ParseResult<(bool, bool, LineInBlock, Position)> {
        let mut line = self.next_line_in_block(
            OPERATION_DEFINITION_BLOCK_INDENTATION,
            &VIEW_DEFINITION_STATEMENT_STARTS,
        )?;
        let mut content_end = block_open_end;
        let is_input = matches!(line, LineInBlock::Statement) && self.scanner.consume(IT_IS_READ);
        if is_input {
            content_end = self.parse_statement_terminator()?;
            line = self.next_line_in_block(
                OPERATION_DEFINITION_BLOCK_INDENTATION,
                &VIEW_DEFINITION_STATEMENT_STARTS,
            )?;
        }
        let is_output =
            matches!(line, LineInBlock::Statement) && self.scanner.consume(IT_IS_WRITTEN);
        if is_output {
            content_end = self.parse_statement_terminator()?;
            line = self.next_line_in_block(
                OPERATION_DEFINITION_BLOCK_INDENTATION,
                &VIEW_DEFINITION_STATEMENT_STARTS,
            )?;
        }
        // The view has no View Direction Statements.
        if !is_input && !is_output {
            return Err(self.missing_view_direction_statement(&line, block_open_end));
        }
        Ok((is_input, is_output, line, content_end))
    }

    /// Parses the operation statements block of an operation of `kind` at
    /// `line` in its operation definition block, whose content ends at
    /// `content_end` before it, and whose references take their default FQUN
    /// from `fqun`, and returns its statements.
    ///
    /// ```ebnf
    /// operation_statements_block = "it does", block_open, operation_statements_contents, block_close ;
    /// operation_statements_contents = operation_statement, { operation_statement } ;
    /// ```
    fn parse_operation_statements_block(
        &mut self,
        kind: OperationKind,
        line: LineInBlock,
        content_end: Position,
        fqun: &FqunWithCanonicalText<'py, 'source>,
    ) -> ParseResult<NodeTuple<'py, ast::OperationStatement<'py>>> {
        match line {
            LineInBlock::Statement if self.scanner.next_bytes_are(IT_DOES) => {}
            LineInBlock::Statement => return Err(self.invalid_operation_definition_statement()),
            // The block closes before its operation statements block.
            LineInBlock::Close => {
                let close = self.scanner.position;
                return Err(self.errors.missing_operation_statements_block(close, close));
            }
            // The block ends before its operation statements block.
            LineInBlock::Unclosed => {
                return Err(self
                    .errors
                    .missing_operation_statements_block(content_end, content_end));
            }
        }
        let start = self.scanner.position;
        self.scanner.consume(IT_DOES);
        let block_open_end = self.parse_block_open()?;
        match self.next_line_in_block(OPERATION_DEFINITION_BLOCK_INDENTATION, &[EXECUTE_THE])? {
            LineInBlock::Statement => {}
            // The block is empty.
            LineInBlock::Close => {
                let close = self.scanner.position;
                return Err(self.missing_operation_statements_content(kind, close));
            }
            // The block ends where its first statement belongs.
            LineInBlock::Unclosed => {
                return Err(self.missing_operation_statements_content(kind, block_open_end));
            }
        }
        let statements = self.ast.start_tuple::<ast::OperationStatement>();
        loop {
            let statement = self.parse_operation_statement(
                kind,
                OPERATION_DEFINITION_BLOCK_INDENTATION + INDENTATION_WIDTH,
                fqun,
            )?;
            self.ast.push(&statements, statement);
            match self.next_line_in_block(OPERATION_DEFINITION_BLOCK_INDENTATION, &[EXECUTE_THE])? {
                LineInBlock::Statement => {}
                LineInBlock::Close => break,
                // The block ends before its `}`.
                LineInBlock::Unclosed => {
                    return Err(self.missing_close_brace(start, block_open_end));
                }
            }
        }
        self.parse_block_close()?;
        Ok(self.ast.finish_tuple(statements)?)
    }

    /// Parses a statement in the operation statements block of an operation
    /// of `kind`, indented `indentation` spaces, whose references take their
    /// default FQUN from `fqun`, through the end of its last line.
    ///
    /// ```ebnf
    /// operation_statement = operation_execution_statement | encoding_operation_execution_statement ;
    /// encoding_operation_statement = operation_execution_statement | computer_operation_execution_statement ;
    /// encoding_operation_execution_statement = "execute the encoding operation", terminator ;
    /// computer_operation_execution_statement = "execute the computer operation", terminator ;
    /// ```
    fn parse_operation_statement(
        &mut self,
        kind: OperationKind,
        indentation: usize,
        fqun: &FqunWithCanonicalText<'py, 'source>,
    ) -> ParseResult<ast::OperationStatement<'py>> {
        let start = self.scanner.position;
        if self
            .scanner
            .consume(kind.implementation_execution_statement())
        {
            let end = self.parse_statement_terminator()?;
            let location = self.ast.location(start, end)?;
            return Ok(match kind {
                OperationKind::Value => self
                    .ast
                    .encoding_operation_execution_statement(location)?
                    .into(),
                OperationKind::Encoding => self
                    .ast
                    .computer_operation_execution_statement(location)?
                    .into(),
            });
        }
        // The statement is neither an operation execution statement nor the
        // statement that executes the operation's implementation.
        if !self.scanner.next_bytes_are(EXECUTE_THE) {
            return Err(self.invalid_operation_statement(kind));
        }
        Ok(self
            .parse_operation_execution_statement(kind, indentation, fqun)?
            .into())
    }
}

// The functions that only run on an error path.
impl<'py, 'source> Parser<'py, 'source> {
    /// Returns the error for a view definition block whose first line, `line`,
    /// is not a View Direction Statement, where the block's `{` ends at
    /// `block_open_end`.
    #[cold]
    #[inline(never)]
    fn missing_view_direction_statement(
        &self,
        line: &LineInBlock,
        block_open_end: Position,
    ) -> ParseError {
        let start = self.scanner.position;
        match line {
            // The block closes where its first statement belongs.
            LineInBlock::Close => self.errors.missing_view_direction_statement(start, start),
            // The block ends where its first statement belongs.
            LineInBlock::Unclosed => self
                .errors
                .missing_view_direction_statement(block_open_end, block_open_end),
            LineInBlock::Statement => {
                if let Some(error) =
                    self.disallowed_character_after_any(&VIEW_DEFINITION_STATEMENT_STARTS)
                {
                    return error;
                }
                // The line begins like a statement of the block, but with extra
                // or missing spaces between two of its words.
                if let Some(error) = self.misspaced_words_in_any(&VIEW_DEFINITION_STATEMENT_STARTS)
                {
                    return error;
                }
                self.errors
                    .missing_view_direction_statement(start, self.end_of_line())
            }
        }
    }

    /// Returns the error for a statement at the scanner's position, after a
    /// view definition block's View Direction Statements, that is not a
    /// position constraint block.
    #[cold]
    #[inline(never)]
    fn invalid_view_definition_statement(&self) -> ParseError {
        if let Some(error) = self.disallowed_character_after_any(&VIEW_DEFINITION_STATEMENT_STARTS)
        {
            return error;
        }
        if let Some(error) = self.misplaced_view_direction_statement() {
            return error;
        }
        // The line begins like a position constraint block, but with extra or
        // missing spaces between two of its words.
        if let Some(error) = self.misspaced_words_in_any(&[IT_MAY_ONLY_CONTAIN_PARTICLES_WHERE]) {
            return error;
        }
        let start = self.scanner.position;
        self.errors
            .missing_view_constraint_block(start, self.end_of_line())
    }

    /// Returns the error for a statement at the scanner's position, after a
    /// view definition's position constraint block, where the view
    /// definition's `}` belongs.
    #[cold]
    #[inline(never)]
    fn statement_instead_of_view_close(&self) -> ParseError {
        if let Some(error) = self.misplaced_view_direction_statement() {
            return error;
        }
        self.statement_instead_of_close_brace()
    }

    /// Returns the error for a View Direction Statement at the scanner's
    /// position, which is somewhere other than where View Direction Statements
    /// belong, if one is there.
    #[cold]
    fn misplaced_view_direction_statement(&self) -> Option<ParseError> {
        if !VIEW_DIRECTION_STATEMENT_STARTS
            .iter()
            .any(|statement| self.scanner.next_bytes_are(statement))
        {
            return None;
        }
        let start = self.scanner.position;
        Some(
            self.errors
                .invalid_view_direction_statement_order(start, self.end_of_line()),
        )
    }

    /// Returns the error for a statement at the scanner's position in an
    /// operation definition block that does not belong there.
    #[cold]
    #[inline(never)]
    fn invalid_operation_definition_statement(&self) -> ParseError {
        if let Some(error) =
            self.disallowed_character_after_any(&OPERATION_DEFINITION_STATEMENT_STARTS)
        {
            return error;
        }
        // The line begins like a statement of the block, but with extra or
        // missing spaces between two of its words.
        if let Some(error) = self.misspaced_words_in_any(&OPERATION_DEFINITION_STATEMENT_STARTS) {
            return error;
        }
        let start = self.scanner.position;
        self.errors
            .invalid_operation_definition_block(start, self.end_of_line())
    }

    /// Returns the error for a statement at the scanner's position in the
    /// operation statements block of an operation of `kind` that does not
    /// belong there.
    #[cold]
    #[inline(never)]
    fn invalid_operation_statement(&self, kind: OperationKind) -> ParseError {
        let statement_starts = [EXECUTE_THE, kind.implementation_execution_statement()];
        if let Some(error) = self.disallowed_character_after_any(&statement_starts) {
            return error;
        }
        // The line begins like a statement of the block, but with extra or
        // missing spaces between two of its words.
        if let Some(error) = self.misspaced_words_in_any(&statement_starts) {
            return error;
        }
        let start = self.scanner.position;
        let end = self.end_of_line();
        match kind {
            OperationKind::Value => self.errors.invalid_operation_statements_block(start, end),
            OperationKind::Encoding => self
                .errors
                .invalid_encoding_operation_statements_block(start, end),
        }
    }

    /// Returns the error for the operation statements block of an operation of
    /// `kind` whose first statement is missing at `missing`.
    #[cold]
    #[inline(never)]
    fn missing_operation_statements_content(
        &self,
        kind: OperationKind,
        missing: Position,
    ) -> ParseError {
        match kind {
            OperationKind::Value => self
                .errors
                .missing_operation_statements_content(missing, missing),
            OperationKind::Encoding => self
                .errors
                .missing_encoding_operation_statements_content(missing, missing),
        }
    }
}
