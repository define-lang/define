#[path = "parser/action_definition.rs"]
mod action_definition;
mod ast_builder;
mod characters;
mod lines;
#[path = "parser/names.rs"]
mod names;
mod parse_error;
mod scanner;
// rustfmt runs on the source tree, which has ast.rs only after
// setup_local_dev copies it there.
#[rustfmt::skip]
mod ast;
// Generated like ast.rs, so rustfmt skips them for the same reason.
#[rustfmt::skip]
mod parser_diagnostics;
#[rustfmt::skip]
mod syntax_errors;

use ast_builder::{AstBuilder, FilePath, Node};
use characters::TextKind;
use lines::{BLOCK_OPEN, INDENTATION_WIDTH, LineInBlock, Lines, OPEN_BRACE, TERMINATOR};
use parse_error::{ParseError, ParseResult};
use parser_diagnostics::ParserDiagnostics;
use pyo3::exceptions::PyNotImplementedError;
use pyo3::prelude::*;
use pyo3::types::{PyList, PyString};
use scanner::{Position, Scanner, SourceText};
use syntax_errors::SyntaxErrors;
use vector_scan::{COMPONENT_SEPARATOR, LINE_FEED, NAME_CONTENT_END, SPACE};

const DEFINE_THE_POTENTIAL: &[u8] = b"define the potential ";
const POSITION: &[u8] = b"position";
const ACTION: &[u8] = b"action";
const DEFINE_THE_POTENTIAL_POSITION: &[u8] = b"define the potential position";
const DEFINE_THE_POTENTIAL_ACTION: &[u8] = b"define the potential action";
/// The words that begin each global definition the parser supports.
const GLOBAL_DEFINITION_STARTS: [&[u8]; 2] =
    [DEFINE_THE_POTENTIAL_POSITION, DEFINE_THE_POTENTIAL_ACTION];
const NAME_CONTENT_START: u8 = b'<';
const IT_MAY_ONLY_CONTAIN_PARTICLES_WHERE: &[u8] = b"it may only contain particles where";
const IT_HAS_THE: &[u8] = b"it has the";
const CONSTRAINT_NAME_TYPES: [(&[u8], ast::NameType); 4] = [
    (POSITION, ast::NameType::Position),
    (ACTION, ast::NameType::Action),
    (b"value", ast::NameType::Value),
    (b"encoding", ast::NameType::Encoding),
];
const POSITION_OR_ACTION: [(&[u8], ast::NameType); 2] = [
    (POSITION, ast::NameType::Position),
    (ACTION, ast::NameType::Action),
];

struct Parser<'py, 'source> {
    scanner: Scanner<'source>,
    ast: AstBuilder<'py, 'source>,
    errors: SyntaxErrors<'py>,
    diagnostics: ParserDiagnostics<'py>,
}

impl<'py, 'source> Parser<'py, 'source> {
    fn lines(&mut self) -> Lines<'_, 'py, 'source> {
        Lines::new(&mut self.scanner, &self.errors, &mut self.diagnostics)
    }

    /// Parses a program: one or more global definitions, with any number of
    /// blank lines and comments before, between, and after them.
    ///
    /// ```ebnf
    /// program = { line_end }, global_definition, { { line_end }, global_definition }, { line_end } ;
    /// line_end = newline | comment ;
    /// ```
    fn parse_program(&mut self) -> ParseResult<ast::Program<'py>> {
        let definitions = self.ast.start_tuple::<ast::GlobalDefinition>();
        let mut start = None;
        let mut end = self.scanner.position;
        loop {
            if self.scanner.is_at_end() {
                break;
            }
            let line_start = self.scanner.position;
            let Some(indentation) = self.lines().start_line(0)? else {
                continue;
            };
            self.lines().check_indentation(line_start, 0, indentation)?;
            start.get_or_insert(self.scanner.position);
            let (definition, definition_end) = self.parse_definition()?;
            self.ast.push(&definitions, definition);
            end = definition_end;
        }
        // The program has no definitions.
        let Some(start) = start else {
            return Err(self.errors.expected_global_definition(end, end));
        };
        // The source does not end with a line feed. Only a line feed moves the
        // scanner back to column 1, and the source is not empty.
        if self.scanner.position.column != 1 {
            let end_of_source = self.scanner.position;
            return Err(self
                .errors
                .missing_newline_at_eof(end_of_source, end_of_source));
        }
        let definitions = self.ast.finish_tuple(definitions)?;
        let location = self.ast.location(start, end)?;
        Ok(self.ast.program(location, definitions)?)
    }

    /// Parses a global definition, and returns it with the position after its
    /// last character.
    ///
    /// ```ebnf
    /// global_definition =
    ///     quality_definition
    ///     | encoding_definition
    ///     | potential_literal_definition
    ///     | operation_definition
    ///     | encoding_operation_definition ;
    /// ```
    fn parse_definition(&mut self) -> ParseResult<(ast::GlobalDefinition<'py>, Position)> {
        let start = self.scanner.position;
        if self.scanner.next_bytes_are(DEFINE_THE_POTENTIAL_POSITION) {
            self.scanner.consume(DEFINE_THE_POTENTIAL);
            let typed_name_start = self.scanner.position;
            self.scanner.consume(POSITION);
            let (definition, end) = self.parse_position_definition(start, typed_name_start)?;
            return Ok((definition.into(), end));
        }
        if self.scanner.next_bytes_are(DEFINE_THE_POTENTIAL_ACTION) {
            self.scanner.consume(DEFINE_THE_POTENTIAL);
            let typed_name_start = self.scanner.position;
            self.scanner.consume(ACTION);
            let (definition, end) = self.parse_action_definition(start, typed_name_start)?;
            return Ok((definition.into(), end));
        }
        // The text does not begin a global definition the parser supports.
        Err(self.expected_global_definition())
    }

    /// Returns the error for a line at the scanner's position that does not
    /// begin a global definition.
    #[cold]
    #[inline(never)]
    fn expected_global_definition(&self) -> ParseError {
        if let Some(error) = self.disallowed_character_after_any(&GLOBAL_DEFINITION_STARTS) {
            return error;
        }
        // The line begins like a global definition, but with extra or missing
        // spaces between two of its words.
        if let Some(error) = self.misspaced_words_in_any(&GLOBAL_DEFINITION_STARTS) {
            return error;
        }
        let start = self.scanner.position;
        self.errors
            .expected_global_definition(start, self.end_of_line())
    }

    /// Returns the error for the spaces where `line`, the rest of the line at
    /// the scanner's position, which does not start with `words`, ASCII words
    /// separated by single spaces, stops matching them, if it has extra spaces
    /// before a word there or is missing the space before one.
    #[cold]
    fn misspaced_words(&self, line: &[u8], words: &[u8]) -> Option<ParseError> {
        let matching = line
            .iter()
            .zip(words)
            .take_while(|(byte, expected)| byte == expected)
            .count();
        // Every byte the line matches is ASCII, so each is one column.
        let start = self.scanner.position;
        if words.get(matching) == Some(&SPACE) {
            let next_word = words[matching + 1..]
                .split(|&byte| byte == SPACE)
                .next()
                .unwrap_or_default();
            // The next word follows the one before it without the space
            // between them. A different word that starts like the one before
            // it is not followed by the next word.
            if !line[matching..].starts_with(next_word) {
                return None;
            }
            let word_start = Position {
                line: start.line,
                column: start.column + matching,
            };
            let word_end = word_start.after_ascii(next_word).previous_column();
            return Some(self.errors.missing_whitespace(word_start, word_end));
        }
        if matching == 0 || words[matching - 1] != SPACE {
            return None;
        }
        let first = matching - 1;
        let spaces = line[first..]
            .iter()
            .take_while(|&&byte| byte == SPACE)
            .count();
        // Spaces that end the line are where an unfinished line stops, and
        // one space is the separator before a different word.
        if spaces == 1 || first + spaces == line.len() {
            return None;
        }
        let spaces_start = Position {
            line: start.line,
            column: start.column + first,
        };
        let spaces_end = Position {
            line: start.line,
            column: start.column + first + spaces - 1,
        };
        Some(self.errors.extra_whitespace(spaces_start, spaces_end))
    }

    /// Returns the error for the spaces where the line at the scanner's
    /// position stops matching the first of `phrases` that it has extra spaces
    /// in or is missing a space in.
    #[cold]
    fn misspaced_words_in_any(&self, phrases: &[&[u8]]) -> Option<ParseError> {
        let line = self.scanner.rest_of_line().bytes;
        phrases
            .iter()
            .find_map(|phrase| self.misspaced_words(line, phrase))
    }

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
    fn parse_position_definition(
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
            let Some(end) = self.lines().parse_terminator()? else {
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

    /// Returns the error for a definition whose `.` or ` {` is missing at the
    /// scanner's position.
    #[cold]
    #[inline(never)]
    fn missing_terminator_or_brace(&self) -> ParseError {
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
    fn parse_position_definition_block(
        &mut self,
        start: Position,
        opener_indentation: usize,
        fqun: &ast::Fqun<'py>,
    ) -> ParseResult<(ast::PositionConstraintBlock<'py>, Position)> {
        let block_open_end = self.lines().parse_block_open()?;
        match self
            .lines()
            .next_line_in_block(opener_indentation, &[IT_MAY_ONLY_CONTAIN_PARTICLES_WHERE])?
        {
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
        match self.lines().next_line_in_block(opener_indentation, &[])? {
            LineInBlock::Close => {}
            // A statement is where the block's `}` belongs.
            LineInBlock::Statement => {
                return Err(self.statement_instead_of_close_brace());
            }
            // The block ends before its `}`.
            LineInBlock::Unclosed => {
                return Err(self.missing_close_brace(start, block_open_end));
            }
        }
        let end = self.lines().parse_block_close()?;
        Ok((constraints, end))
    }

    /// Returns the error for a block that ends without its `}`, which a line
    /// from `start` up to `block_open_end`, the position after its `{`, opens.
    #[cold]
    #[inline(never)]
    fn missing_close_brace(&self, start: Position, block_open_end: Position) -> ParseError {
        self.errors
            .missing_close_brace(start, block_open_end.previous_column())
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

    /// Returns the error for a statement at the scanner's position where a
    /// block's `}` belongs.
    #[cold]
    #[inline(never)]
    fn statement_instead_of_close_brace(&self) -> ParseError {
        if let Some(error) = self.disallowed_character_ahead(0) {
            return error;
        }
        let start = self.scanner.position;
        self.errors.missing_close_brace(start, self.end_of_line())
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

    /// Returns the error for the character `offset` bytes, which are ASCII,
    /// past the scanner's position, where the syntax there went wrong, if no
    /// syntax may have it.
    #[cold]
    #[inline(never)]
    fn disallowed_character_ahead(&self, offset: usize) -> Option<ParseError> {
        characters::disallowed_character_ahead(&self.errors, &self.scanner, offset)
    }

    /// Returns the error for the character where the line at the scanner's
    /// position stops matching `expected`, if no syntax may have it.
    #[cold]
    fn disallowed_character_after(&self, expected: &[u8]) -> Option<ParseError> {
        self.disallowed_character_ahead(self.scanner.matching_prefix_length(expected))
    }

    /// Returns the error for the character where the line at the scanner's
    /// position stops matching the one of `phrases` that it matches the most
    /// of, if no syntax may have it.
    #[cold]
    fn disallowed_character_after_any(&self, phrases: &[&[u8]]) -> Option<ParseError> {
        let matched = phrases
            .iter()
            .map(|phrase| self.scanner.matching_prefix_length(phrase))
            .max()
            .unwrap_or(0);
        self.disallowed_character_ahead(matched)
    }

    /// Returns the position of the last character on the line before its line
    /// feed, which must not be empty from the scanner's position.
    #[cold]
    fn end_of_line(&self) -> Position {
        self.scanner
            .position
            .after(self.scanner.rest_of_line())
            .previous_column()
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
    fn parse_position_constraint_block(
        &mut self,
        start: Position,
        indentation: usize,
        fqun: &ast::Fqun<'py>,
    ) -> ParseResult<ast::PositionConstraintBlock<'py>> {
        let block_open_end = self.lines().parse_block_open()?;
        match self
            .lines()
            .next_line_in_block(indentation, &[IT_HAS_THE])?
        {
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
            match self
                .lines()
                .next_line_in_block(indentation, &[IT_HAS_THE])?
            {
                LineInBlock::Statement => {}
                LineInBlock::Close => break,
                // The block ends before its `}`.
                LineInBlock::Unclosed => {
                    return Err(self.missing_close_brace(start, block_open_end));
                }
            }
        }
        let end = self.lines().parse_block_close()?;
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
        // The line ends where the typed name belongs.
        if !self.space_before_word()? {
            return Err(self.expected_constraint_name_type());
        }
        let typed_name = self.parse_typed_global_name_reference(
            fqun,
            &CONSTRAINT_NAME_TYPES,
            Self::expected_constraint_name_type,
        )?;
        // There is no `.`.
        let Some(end) = self.lines().parse_terminator()? else {
            return Err(self.lines().missing_terminator());
        };
        let location = self.ast.location(start, end)?;
        Ok(self
            .ast
            .position_requirement_statement(location, typed_name)?)
    }

    /// Parses a typed global name in a reference, whose default FQUN is
    /// `fqun`, with one of the `name_types`, where `wrong_name_type` returns
    /// the error for any other name type.
    ///
    /// ```ebnf
    /// typed_global_name = name_type, "<", global_name, ">" ;
    /// ```
    fn parse_typed_global_name_reference(
        &mut self,
        fqun: &ast::Fqun<'py>,
        name_types: &[(&[u8], ast::NameType)],
        wrong_name_type: fn(&Self) -> ParseError,
    ) -> ParseResult<ast::GlobalTypedNameReference<'py>> {
        let start = self.scanner.position;
        // The name type is not one this reference allows.
        let Some(name_type) = self.scanner.consume_any(name_types) else {
            return Err(wrong_name_type(self));
        };
        let (location, name_fqun, path) = self.parse_global_name_content()?;
        let name_content = self
            .ast
            .reference_global_name_content(location, name_fqun, path)?;
        let location = self.ast.location(start, self.scanner.position)?;
        Ok(self
            .ast
            .global_typed_name_reference(location, fqun.clone(), name_type, name_content)?)
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

    /// Parses the `<`, fully qualified global name, and `>` that follow the name
    /// type of a global name in a definition, and returns the name content with
    /// its FQUN.
    ///
    /// ```ebnf
    /// "<", fully_qualified_global_name, ">"
    /// fully_qualified_global_name = fqun, global_name_path ;
    /// ```
    fn parse_global_name_definition_content(
        &mut self,
    ) -> ParseResult<(ast::DefinitionGlobalNameContent<'py>, ast::Fqun<'py>)> {
        let content_start = self.scanner.position.next_column();
        let (location, fqun, path) = self.parse_global_name_content()?;
        // The name has no FQUN.
        let Some(fqun) = fqun else {
            // The scanner is after the `>`.
            let content_end = self.scanner.position.previous_column().previous_column();
            return Err(self
                .errors
                .definition_global_name_content_requires_fqun(content_start, content_end));
        };
        let name_content = self
            .ast
            .definition_global_name_content(location, fqun.clone(), path)?;
        Ok((name_content, fqun))
    }

    /// Parses the `<`, global name, and `>` that follow the name type of a
    /// global name, and returns the location of the name content, its FQUN if
    /// it has one, and its path.
    ///
    /// ```ebnf
    /// "<", global_name, ">"
    /// global_name = [ fqun ], global_name_path ;
    /// ```
    fn parse_global_name_content(
        &mut self,
    ) -> ParseResult<(
        ast::SourceLocation<'py>,
        Option<ast::Fqun<'py>>,
        ast::GlobalPathName<'py>,
    )> {
        // There is no `<`.
        if !self.scanner.consume_byte(NAME_CONTENT_START) {
            return Err(self.missing_open_angle_bracket());
        }
        let start = self.scanner.position;
        let (content, scanned) = self.scanner.consume_global_name_content();
        let end = self.scanner.position;
        // The name content is not a global name that ends with `>`.
        if !scanned.is_global_name || !self.scanner.next_byte_is(NAME_CONTENT_END) {
            return Err(self.invalid_global_name_content(content, start, end));
        }
        self.global_name_parts(content, scanned.last_component_separator, start, end)
    }

    /// Returns the error for a character in name `content`, which begins at
    /// `start`, that names do not allow, if it has one.
    fn disallowed_name_character(
        &self,
        content: SourceText<'source>,
        start: Position,
    ) -> ParseResult<()> {
        // The name content has a character that names do not allow.
        if !content.is_known_ascii
            && let Some(error) = characters::first_disallowed_character(
                &self.errors,
                start,
                content.bytes,
                TextKind::Name,
            )
        {
            return Err(error);
        }
        Ok(())
    }

    /// Parses global name `content`, which runs from `start` up to `end`, where
    /// the scanner is before its `>`, and whose last `:` before its path is at
    /// `last_component_separator`, and returns the location of the name
    /// content, its FQUN if it has one, and its path.
    fn global_name_parts(
        &mut self,
        content: SourceText<'source>,
        last_component_separator: Option<usize>,
        start: Position,
        end: Position,
    ) -> ParseResult<(
        ast::SourceLocation<'py>,
        Option<ast::Fqun<'py>>,
        ast::GlobalPathName<'py>,
    )> {
        self.disallowed_name_character(content, start)?;
        self.scanner.consume_bytes(1);
        let (fqun, path_start, path_text) = match last_component_separator {
            None => (None, start, content),
            // The name has a `:` but nothing before it.
            Some(0) => {
                return Err(self
                    .errors
                    .invalid_global_name(start, end.previous_column()));
            }
            Some(separator) => {
                let (fqun, fqun_end) = self.parse_fqun(content.slice(..separator), start)?;
                (
                    Some(fqun),
                    fqun_end.next_column(),
                    content.slice(separator + 1..),
                )
            }
        };
        let path_location = self.ast.location(path_start, end)?;
        let path_name = self.ast.name(path_text)?;
        let path = self.ast.global_path_name(path_location, path_name)?;
        let location = self.ast.location(start, end)?;
        Ok((location, fqun, path))
    }

    /// Returns the error for a name whose `<` is missing at the scanner's
    /// position.
    #[cold]
    #[inline(never)]
    fn missing_open_angle_bracket(&self) -> ParseError {
        if let Some(error) = self.disallowed_character_ahead(0) {
            return error;
        }
        let missing = self.scanner.position;
        let line = self.scanner.rest_of_line().bytes;
        let spaces = line.iter().take_while(|&&byte| byte == SPACE).count();
        // Spaces come between the name type and the `<`.
        if spaces > 0 && line.get(spaces) == Some(&NAME_CONTENT_START) {
            let last_space = Position {
                line: missing.line,
                column: missing.column + spaces - 1,
            };
            return self
                .errors
                .space_before_open_angle_bracket(missing, last_space);
        }
        self.errors.missing_open_angle_bracket(missing, missing)
    }

    /// Returns the error for name `content` from `start` up to `end`, the
    /// scanner's position, that is not a global name followed by `>`.
    #[cold]
    #[inline(never)]
    fn invalid_global_name_content(
        &self,
        content: SourceText<'source>,
        start: Position,
        end: Position,
    ) -> ParseError {
        // There is no name between the `<` and where the `>` belongs.
        if content.bytes.is_empty() {
            return self.errors.empty_name(start, start);
        }
        if let Some(error) = characters::first_disallowed_character(
            &self.errors,
            start,
            content.bytes,
            TextKind::Name,
        ) {
            return error;
        }
        // The name content runs to the end of the line without a `>`.
        if !self.scanner.next_byte_is(NAME_CONTENT_END) {
            return self.errors.missing_close_angle_bracket(
                end,
                end,
                &String::from_utf8_lossy(content.bytes),
            );
        }
        self.errors
            .invalid_global_name(start, end.previous_column())
    }

    /// Parses the FQUN `text`, without its final `:`, that begins at `start`,
    /// and returns it with the position after it.
    ///
    /// ```ebnf
    /// fqun =
    ///     ( multiverse, ":", authority, ":", universe, ":"
    ///     | authority, ":", universe, ":"
    ///     | "standard:") ;
    /// ```
    fn parse_fqun(
        &mut self,
        text: SourceText<'source>,
        start: Position,
    ) -> ParseResult<(ast::Fqun<'py>, Position)> {
        let mut names = text.split(COMPONENT_SEPARATOR);
        let (multiverse, authority, universe) =
            match (names.next(), names.next(), names.next(), names.next()) {
                (Some(universe), None, None, None) => (None, None, universe),
                (Some(authority), Some(universe), None, None) => (None, Some(authority), universe),
                (Some(multiverse), Some(authority), Some(universe), None) => {
                    (Some(multiverse), Some(authority), universe)
                }
                // The FQUN has more than three components.
                _ => {
                    let end = start.after(text).previous_column();
                    return Err(self.errors.global_name_invalid_fqun_format(start, end));
                }
            };
        let mut component_start = start;
        let multiverse = match multiverse {
            Some(name) => {
                let (location, name, end) = self.fqun_component(name, component_start)?;
                component_start = end.next_column();
                Some(self.ast.multiverse(location, name)?)
            }
            None => None,
        };
        let authority = match authority {
            Some(name) => {
                let (location, name, end) = self.fqun_component(name, component_start)?;
                component_start = end.next_column();
                Some(self.ast.authority(location, name)?)
            }
            None => None,
        };
        let (location, name, end) = self.fqun_component(universe, component_start)?;
        let universe = self.ast.universe(location, name)?;
        let location = self.ast.location(start, end)?;
        Ok((
            self.ast.fqun(location, multiverse, authority, universe)?,
            end,
        ))
    }

    /// Returns the location and name of the FQUN component `name` that begins
    /// at `start`, and the position after it.
    fn fqun_component(
        &mut self,
        name: SourceText<'source>,
        start: Position,
    ) -> PyResult<(ast::SourceLocation<'py>, Bound<'py, PyString>, Position)> {
        let end = start.after(name);
        let location = self.ast.location(start, end)?;
        Ok((location, self.ast.name(name)?, end))
    }
}

/// The result of parsing Define source code.
#[pyclass(
    frozen,
    get_all,
    name = "ParseResult",
    module = "define.compiler.parsing.native_parser"
)]
struct PythonParseResult {
    /// The `ast.Program`, unless the parse ended in `exception`.
    program: Option<Py<PyAny>>,
    /// The diagnostics that the parse found, in source order.
    diagnostics: Py<PyList>,
    /// The `parser_exceptions.DefineSyntaxError` that ended the parse, if any.
    exception: Option<Py<PyAny>>,
}

/// Parses UTF-8 Define source code into an `ast.Program`.
#[pyfunction]
fn parse<'py>(
    py: Python<'py>,
    source: &[u8],
    file_path: Option<Bound<'py, PyAny>>,
) -> PyResult<PythonParseResult> {
    let file_path = file_path.map(FilePath::new);
    let mut parser = Parser {
        scanner: Scanner::new(source),
        ast: AstBuilder::new(py, file_path.clone())?,
        errors: SyntaxErrors::new(py, file_path.clone()),
        diagnostics: ParserDiagnostics::new(py, file_path),
    };
    let (program, exception) = match parser.parse_program() {
        Ok(program) => (Some(program.into_object().unbind()), None),
        Err(ParseError::Syntax(error)) => (None, Some(error.into_value(py).into_any())),
        Err(ParseError::NotYetSupported {
            position: Position { line, column },
            description,
        }) => {
            return Err(PyNotImplementedError::new_err(format!(
                "line {line}, column {column}: the parser does not support {description} yet"
            )));
        }
        Err(ParseError::Python(error)) => return Err(error),
    };
    Ok(PythonParseResult {
        program,
        diagnostics: parser.diagnostics.into_list()?.unbind(),
        exception,
    })
}

#[pymodule(gil_used = false)]
fn native_parser(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<PythonParseResult>()?;
    module.add_function(wrap_pyfunction!(parse, module)?)
}
