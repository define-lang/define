//! Potential position definitions and their Position Quality Assignment Blocks.

use crate::ast;
use crate::parse_error::{ParseError, ParseResult};
use crate::parser::Parser;
use crate::parser::lines::{INDENTATION_WIDTH, LineInBlock};
use crate::parser::names::FqunWithCanonicalText;
use crate::scanner::Position;
use pyo3::prelude::*;
use pyo3::types::PyString;
use terminals::{
    ACTION, BLOCK_OPEN, ENCODING, IT_HAS_THE, IT_MAY_ONLY_CONTAIN_PARTICLES_WHERE, LINE_FEED,
    NAME_CONTENT_START, OPEN_BRACE, POSITION, SPACE, TERMINATOR, VALUE,
};

const ASSIGNABLE_NAME_TYPES: [(&[u8], ast::NameType); 4] = [
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
        let (typed_name, fqun) =
            self.parse_global_typed_name_in_definition(typed_name_start, ast::NameType::Position)?;
        let (quality_assignment_block, end) = if self.scanner.next_bytes_are(BLOCK_OPEN) {
            let (block, end) = self.parse_position_definition_block(start, 0, &fqun)?;
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
                .position_definition(location, typed_name, quality_assignment_block)?;
        Ok((definition, end))
    }

    /// Parses the block of a position definition that begins at `start`,
    /// indented `opener_indentation` spaces, whose references take their
    /// default FQUN from `fqun`, and returns its Position Quality Assignment Block
    /// with the position after its `}`.
    ///
    /// ```ebnf
    /// position_definition_block =
    ///     block_open,
    ///     position_quality_assignment_block,
    ///     block_close ;
    /// ```
    pub(crate) fn parse_position_definition_block(
        &mut self,
        start: Position,
        opener_indentation: usize,
        fqun: &FqunWithCanonicalText<'py, 'source>,
    ) -> ParseResult<(ast::QualityAssignmentBlock<'py>, Position)> {
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
        let block_start = self.scanner.position;
        // The block has something other than a Position Quality Assignment Block.
        if !self.scanner.consume(IT_MAY_ONLY_CONTAIN_PARTICLES_WHERE) {
            return Err(self.invalid_position_definition_block());
        }
        let block = self.parse_quality_assignment_block(
            block_start,
            opener_indentation + INDENTATION_WIDTH,
            fqun,
        )?;
        let end = self.parse_block_close_after_content(
            start,
            block_open_end,
            opener_indentation,
            Self::statement_instead_of_close_brace,
        )?;
        Ok((block, end))
    }

    /// Parses the rest of a Quality Assignment Block after its
    /// `it may only contain particles where`, given the position of its start
    /// and the indentation of its line.
    ///
    /// ```ebnf
    /// position_quality_assignment_block =
    ///     "it may only contain particles where",
    ///     block_open,
    ///     quality_assignment_statement,
    ///     { quality_assignment_statement },
    ///     block_close ;
    /// ```
    pub(crate) fn parse_quality_assignment_block(
        &mut self,
        start: Position,
        indentation: usize,
        fqun: &FqunWithCanonicalText<'py, 'source>,
    ) -> ParseResult<ast::QualityAssignmentBlock<'py>> {
        let block_open_end = self.parse_block_open()?;
        match self.next_line_in_block(indentation, &[IT_HAS_THE])? {
            LineInBlock::Statement => {}
            // The block is empty.
            LineInBlock::Close => {
                let close = self.scanner.position;
                return Err(self
                    .errors
                    .missing_quality_assignment_block_content(close, close));
            }
            // The block ends where its content belongs.
            LineInBlock::Unclosed => {
                return Err(self
                    .errors
                    .missing_quality_assignment_block_content(block_open_end, block_open_end));
            }
        }
        let statements = self.nodes.start::<ast::QualityAssignmentStatement>();
        let assigned_names = self.texts.start();
        loop {
            let (statement, assigned_name) = self.parse_quality_assignment_statement(fqun)?;
            self.nodes.push(&statements, statement);
            self.texts.push(&assigned_names, assigned_name);
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
        let statements = self.nodes.finish_tuple(statements)?;
        let assigned_names = self.texts.finish_set(assigned_names)?;
        let location = self.ast.location(start, end)?;
        Ok(self
            .ast
            .quality_assignment_block(location, statements, assigned_names)?)
    }

    /// Parses a Quality Assignment Statement, whose reference's default FQUN
    /// is `fqun`, through the end of its line, and returns it with the full
    /// typed name that it assigns.
    ///
    /// ```ebnf
    /// quality_assignment_statement = "it has the", " ", typed_global_name, terminator ;
    /// ```
    fn parse_quality_assignment_statement(
        &mut self,
        fqun: &FqunWithCanonicalText<'py, 'source>,
    ) -> ParseResult<(ast::QualityAssignmentStatement<'py>, Bound<'py, PyString>)> {
        let start = self.scanner.position;
        // The statement is not a Quality Assignment Statement.
        if !self.scanner.consume(IT_HAS_THE) {
            return Err(self.invalid_quality_assignment_block());
        }
        // The line ends, or a non-letter character comes, where the typed name
        // belongs.
        if !self.space_before_word()? {
            return Err(self.expected_quality_assignment_name_type());
        }
        let (typed_name, full_typed_name) = self.parse_typed_global_name_reference(
            fqun,
            &ASSIGNABLE_NAME_TYPES,
            Self::expected_quality_assignment_name_type,
        )?;
        let end = self.parse_statement_terminator()?;
        let location = self.ast.location(start, end)?;
        let statement = self
            .ast
            .quality_assignment_statement(location, typed_name)?;
        Ok((statement, full_typed_name))
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
    /// Quality Assignment Block that is not a Quality Assignment Statement.
    #[cold]
    #[inline(never)]
    fn invalid_quality_assignment_block(&self) -> ParseError {
        if let Some(error) = self.disallowed_character_after(IT_HAS_THE) {
            return error;
        }
        let start = self.scanner.position;
        self.errors
            .invalid_quality_assignment_block(start, self.end_of_line())
    }

    /// Returns the error for a name type, at the scanner's position, that a
    /// Quality Assignment Statement does not allow.
    #[cold]
    #[inline(never)]
    fn expected_quality_assignment_name_type(&self) -> ParseError {
        let matched = ASSIGNABLE_NAME_TYPES
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
        self.errors
            .expected_quality_assignment_name_type(start, end)
    }
}
