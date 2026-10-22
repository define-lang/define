//! The parser: a program, and the dispatch to each kind of global definition.

mod action_definition;
mod errors;
mod lines;
mod names;
mod position_definition;

use crate::ast;
use crate::ast_builder::{AstBuilder, FilePath};
use crate::parse_error::{ParseError, ParseResult};
use crate::parser_diagnostics::ParserDiagnostics;
use crate::scanner::{Position, Scanner};
use crate::syntax_errors::SyntaxErrors;
use pyo3::prelude::*;
use pyo3::types::PyList;
use terminals::{
    ACTION, DEFINE_THE_POTENTIAL, DEFINE_THE_POTENTIAL_ACTION, DEFINE_THE_POTENTIAL_POSITION,
    POSITION,
};

/// The words that begin each global definition the parser supports.
const GLOBAL_DEFINITION_STARTS: [&[u8]; 2] =
    [DEFINE_THE_POTENTIAL_POSITION, DEFINE_THE_POTENTIAL_ACTION];
pub(crate) struct Parser<'py, 'source> {
    scanner: Scanner<'source>,
    ast: AstBuilder<'py, 'source>,
    errors: SyntaxErrors<'py>,
    diagnostics: ParserDiagnostics<'py>,
}

impl<'py, 'source> Parser<'py, 'source> {
    pub(crate) fn new(
        py: Python<'py>,
        source: &'source [u8],
        file_path: Option<FilePath<'py>>,
    ) -> PyResult<Self> {
        Ok(Self {
            scanner: Scanner::new(source),
            ast: AstBuilder::new(py, file_path.clone())?,
            errors: SyntaxErrors::new(py, file_path.clone()),
            diagnostics: ParserDiagnostics::new(py, file_path),
        })
    }

    /// The diagnostics that the parse found, in source order.
    pub(crate) fn into_diagnostics(self) -> PyResult<Bound<'py, PyList>> {
        self.diagnostics.into_list()
    }

    /// Parses a program: one or more global definitions, with any number of
    /// blank lines and comments before, between, and after them.
    ///
    /// ```ebnf
    /// program = { line_end }, global_definition, { { line_end }, global_definition }, { line_end } ;
    /// line_end = newline | comment ;
    /// ```
    pub(crate) fn parse_program(&mut self) -> ParseResult<ast::Program<'py>> {
        let definitions = self.ast.start_tuple::<ast::GlobalDefinition>();
        let mut start = None;
        let mut end = self.scanner.position;
        loop {
            if self.scanner.is_at_end() {
                break;
            }
            let line_start = self.scanner.position;
            let Some(indentation) = self.start_line(0)? else {
                continue;
            };
            self.check_indentation(line_start, 0, indentation)?;
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
}

// The functions that only run on an error path.
impl<'py, 'source> Parser<'py, 'source> {
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
}
