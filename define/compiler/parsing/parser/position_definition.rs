//! Potential position definitions and their position constraint blocks.

use crate::ast;
use crate::parse_error::{ParseError, ParseResult};
use crate::parser::Parser;
use crate::parser::lines::{INDENTATION_WIDTH, LineInBlock};
use crate::scanner::Position;
use terminals::{
    ACTION, BLOCK_OPEN, ENCODING, IT_HAS_THE, IT_MAY_ONLY_CONTAIN_PARTICLES_WHERE, LINE_FEED,
    NAME_CONTENT_START, OPEN_BRACE, POSITION, SPACE, TERMINATOR, VALUE,
};

const CONSTRAINT_NAME_TYPES: [(&[u8], ast::NameType); 4] = [
    (POSITION, ast::NameType::Position),
    (ACTION, ast::NameType::Action),
    (VALUE, ast::NameType::Value),
    (ENCODING, ast::NameType::Encoding),
];

impl<'py, 'source> Parser<'py, 'source> {
    /// Parses the rest of a position definition after its `position`, given
    /// the positions of the definition's start and of its `position`, and
    /// returns the definition with the position after its last character.
    ///
    /// ```ebnf
    /// position_definition =
    ///     "define the potential", " ", fully_qualified_global_position_name,
    ///     position_definition_end ;
    /// fully_qualified_global_position_name = "position", "<", fully_qualified_global_name, ">" ;
    /// position_definition_end = terminator | potential_position_definition_block ;
    /// ```
    pub(crate) fn parse_position_definition(
        &mut self,
        start: Position,
        typed_name_start: Position,
    ) -> ParseResult<(ast::PositionDefinition<'py>, Position)> {
        let (name_content, fqun) = self.parse_global_name_definition_content()?;
        let typed_name_location = self.ast.location(typed_name_start, self.scanner.position)?;
        let typed_name = self.ast.global_typed_name_in_definition(
            typed_name_location,
            ast::NameType::Position,
            name_content,
        )?;
        let (constraints, end) = if self.scanner.next_bytes_are(BLOCK_OPEN) {
            let (constraints, end) = self.parse_position_definition_block(start, 0, &fqun)?;
            (Some(constraints), end)
        } else {
            // There is no `.` or ` {`.
            let Some(end) = self.parse_terminator()? else {
                return Err(self.missing_terminator_or_brace());
            };
            (None, end)
        };
        let location = self.ast.location(start, end)?;
        let definition = self
            .ast
            .position_definition(location, typed_name, constraints)?;
        Ok((definition, end))
    }

    /// Parses the block of a position definition that begins at `start`,
    /// indented `opener_indentation` spaces, whose references take their
    /// default FQUN from `fqun`, and returns its position constraint block
    /// with the position after its `}`.
    ///
    /// ```ebnf
    /// position_definition_block =
    ///     block_open,
    ///     position_constraint_block,
    ///     block_close ;
    /// ```
    pub(crate) fn parse_position_definition_block(
        &mut self,
        start: Position,
        opener_indentation: usize,
        fqun: &ast::Fqun<'py>,
    ) -> ParseResult<(ast::PositionConstraintBlock<'py>, Position)> {
        let block_open_end = self.parse_block_open()?;
        match self.next_line_in_block(opener_indentation, &[IT_MAY_ONLY_CONTAIN_PARTICLES_WHERE])? {
            LineInBlock::Statement => {}
            // The block is empty.
            LineInBlock::Close => {
                let close = self.scanner.position;
                return Err(self
                    .errors
                    .missing_position_definition_content(close, close));
            }
            // The block ends where its content belongs.
            LineInBlock::Unclosed => {
                return Err(self
                    .errors
                    .missing_position_definition_content(block_open_end, block_open_end));
            }
        };
        let constraints_start = self.scanner.position;
        // The block has something other than a position constraint block.
        if !self.scanner.consume(IT_MAY_ONLY_CONTAIN_PARTICLES_WHERE) {
            return Err(self.invalid_position_definition_block());
        }
        let constraints = self.parse_position_constraint_block(
            constraints_start,
            opener_indentation + INDENTATION_WIDTH,
            fqun,
        )?;
        let end = self.parse_block_close_after_content(
            start,
            block_open_end,
            opener_indentation,
            Self::statement_instead_of_close_brace,
        )?;
        Ok((constraints, end))
    }

    /// Parses the rest of a position constraint block after its
    /// `it may only contain particles where`, given the position of its start
    /// and the indentation of its line.
    ///
    /// ```ebnf
    /// position_constraint_block =
    ///     "it may only contain particles where",
    ///     block_open,
    ///     position_requirement_statement,
    ///     { position_requirement_statement },
    ///     block_close ;
    /// ```
    pub(crate) fn parse_position_constraint_block(
        &mut self,
        start: Position,
        indentation: usize,
        fqun: &ast::Fqun<'py>,
    ) -> ParseResult<ast::PositionConstraintBlock<'py>> {
        let block_open_end = self.parse_block_open()?;
        match self.next_line_in_block(indentation, &[IT_HAS_THE])? {
            LineInBlock::Statement => {}
            // The block is empty.
            LineInBlock::Close => {
                let close = self.scanner.position;
                return Err(self
                    .errors
                    .missing_position_constraint_content(close, close));
            }
            // The block ends where its content belongs.
            LineInBlock::Unclosed => {
                return Err(self
                    .errors
                    .missing_position_constraint_content(block_open_end, block_open_end));
            }
        }
        let requirements = self.ast.start_tuple::<ast::PositionRequirementStatement>();
        loop {
            let requirement = self.parse_position_requirement_statement(fqun)?;
            self.ast.push(&requirements, requirement);
            match self.next_line_in_block(indentation, &[IT_HAS_THE])? {
                LineInBlock::Statement => {}
                LineInBlock::Close => break,
                // The block ends before its `}`.
                LineInBlock::Unclosed => {
                    return Err(self.missing_close_brace(start, block_open_end));
                }
            }
        }
        let end = self.parse_block_close()?;
        let requirements = self.ast.finish_tuple(requirements)?;
        let location = self.ast.location(start, end)?;
        Ok(self.ast.position_constraint_block(location, requirements)?)
    }

    /// Parses a position requirement statement, whose reference's default FQUN
    /// is `fqun`, through the end of its line.
    ///
    /// ```ebnf
    /// position_requirement_statement = "it has the", " ", typed_global_name, terminator ;
    /// ```
    fn parse_position_requirement_statement(
        &mut self,
        fqun: &ast::Fqun<'py>,
    ) -> ParseResult<ast::PositionRequirementStatement<'py>> {
        let start = self.scanner.position;
        // The statement is not a position requirement statement.
        if !self.scanner.consume(IT_HAS_THE) {
            return Err(self.invalid_position_constraint_block());
        }
        // The line ends, or a non-letter character comes, where the typed name
        // belongs.
        if !self.space_before_word()? {
            return Err(self.expected_constraint_name_type());
        }
        let typed_name = self.parse_typed_global_name_reference(
            fqun,
            &CONSTRAINT_NAME_TYPES,
            Self::expected_constraint_name_type,
        )?;
        // There is no `.`.
        let Some(end) = self.parse_terminator()? else {
            return Err(self.missing_terminator());
        };
        let location = self.ast.location(start, end)?;
        Ok(self
            .ast
            .position_requirement_statement(location, typed_name)?)
    }
}

// The functions that only run on an error path.
impl<'py, 'source> Parser<'py, 'source> {
    /// Returns the error for a definition whose `.` or ` {` is missing at the
    /// scanner's position.
    #[cold]
    #[inline(never)]
    pub(crate) fn missing_terminator_or_brace(&self) -> ParseError {
        if let Some(error) = self.disallowed_character_ahead(0) {
            return error;
        }
        let missing = self.scanner.position;
        // The line or the source ends where the `.` or ` {` belongs.
        if self.scanner.is_at_line_end() {
            return self.errors.missing_terminator_or_brace(missing, missing);
        }
        // A `{` follows the name without a space before it.
        if self.scanner.next_byte_is(OPEN_BRACE) {
            return self
                .errors
                .missing_whitespace_before_brace(missing, missing);
        }
        let spaces = self.scanner.next_space_count();
        // More than one space comes before the `{`.
        if spaces > 1 && self.scanner.rest_of_line().bytes.get(spaces) == Some(&OPEN_BRACE) {
            let last_space = Position {
                line: missing.line,
                column: missing.column + spaces - 1,
            };
            return self.errors.extra_whitespace(missing, last_space);
        }
        self.errors.missing_terminator_or_brace(missing, missing)
    }

    /// Returns the error for a statement in a potential position definition
    /// block, at the scanner's position, that does not belong there.
    #[cold]
    #[inline(never)]
    fn invalid_position_definition_block(&self) -> ParseError {
        if let Some(error) = self.disallowed_character_after(IT_MAY_ONLY_CONTAIN_PARTICLES_WHERE) {
            return error;
        }
        let start = self.scanner.position;
        self.errors
            .invalid_position_definition_block(start, self.end_of_line())
    }

    /// Returns the error for a statement at the scanner's position in a
    /// position constraint block that is not a position requirement
    /// statement.
    #[cold]
    #[inline(never)]
    fn invalid_position_constraint_block(&self) -> ParseError {
        if let Some(error) = self.disallowed_character_after(IT_HAS_THE) {
            return error;
        }
        let start = self.scanner.position;
        self.errors
            .invalid_position_constraint_block(start, self.end_of_line())
    }

    /// Returns the error for a name type, at the scanner's position, that a
    /// position requirement statement does not allow.
    #[cold]
    #[inline(never)]
    fn expected_constraint_name_type(&self) -> ParseError {
        let matched = CONSTRAINT_NAME_TYPES
            .iter()
            .map(|&(keyword, _)| self.scanner.matching_prefix_length(keyword))
            .max()
            .unwrap_or(0);
        if let Some(error) = self.disallowed_character_ahead(matched) {
            return error;
        }
        let start = self.scanner.position;
        // The error covers the word where the name type belongs, or the
        // character there if the word is empty.
        let word =
            self.scanner
                .text_before_any(&[NAME_CONTENT_START, SPACE, TERMINATOR, LINE_FEED]);
        let end = if word.bytes.is_empty() {
            start
        } else {
            start.after(word).previous_column()
        };
        self.errors.expected_constraint_name_type(start, end)
    }
}
