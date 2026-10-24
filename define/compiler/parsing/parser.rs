//! The parser: a program, and the dispatch to each kind of global definition.

mod action_definition;
mod encoding_definition;
mod errors;
mod lines;
mod literals;
mod names;
mod operation_definition;
mod operation_execution;
mod position_definition;
mod potential_literal_definition;
mod value_definition;

use crate::ast;
use crate::ast_builder::AstBuilder;
use crate::element_stack::ElementStack;
use crate::node_construction::FilePath;
use crate::parse_error::{ParseError, ParseResult};
use crate::parser::operation_execution::OperationKind;
use crate::parser_diagnostics::ParserDiagnostics;
use crate::scanner::{Position, Scanner};
use crate::syntax_errors::SyntaxErrors;
use pyo3::prelude::*;
use pyo3::types::{PyList, PyString};
use terminals::{
    ACTION, DEFINE_THE, DEFINE_THE_ENCODING, DEFINE_THE_ENCODING_OPERATION, DEFINE_THE_OPERATION,
    DEFINE_THE_POTENTIAL, DEFINE_THE_POTENTIAL_ACTION, DEFINE_THE_POTENTIAL_LITERAL,
    DEFINE_THE_POTENTIAL_POSITION, DEFINE_THE_POTENTIAL_VALUE, ENCODING, ENCODING_OPERATION,
    LITERAL, OPERATION, POSITION, VALUE,
};

/// The words that begin each global definition.
const GLOBAL_DEFINITION_STARTS: [&[u8]; 7] = [
    DEFINE_THE_POTENTIAL_POSITION,
    DEFINE_THE_POTENTIAL_ACTION,
    DEFINE_THE_POTENTIAL_VALUE,
    DEFINE_THE_POTENTIAL_LITERAL,
    DEFINE_THE_ENCODING,
    DEFINE_THE_OPERATION,
    DEFINE_THE_ENCODING_OPERATION,
];
pub(crate) struct Parser<'py, 'source> {
    scanner: Scanner<'source>,
    ast: AstBuilder<'py>,
    /// The nodes of the tuples of nodes being built.
    nodes: ElementStack<'py, PyAny>,
    /// The strings of the tuples and sets of strings being built.
    texts: ElementStack<'py, PyString>,
    /// Where `typed_name_text` spells a typed name, kept to reuse its
    /// allocation.
    typed_name_text_buffer: Vec<u8>,
    errors: SyntaxErrors<'py>,
    diagnostics: ParserDiagnostics<'py>,
    /// Whether a line with the wrong indentation gets a diagnostic.
    checks_indentation: bool,
}

impl<'py, 'source> Parser<'py, 'source> {
    pub(crate) fn new(
        py: Python<'py>,
        source: &'source [u8],
        file_path: Option<FilePath<'py>>,
        checks_indentation: bool,
    ) -> PyResult<Self> {
        Ok(Self {
            scanner: Scanner::new(source),
            ast: AstBuilder::new(py, file_path.clone())?,
            nodes: ElementStack::new(py),
            texts: ElementStack::new(py),
            typed_name_text_buffer: Vec::new(),
            errors: SyntaxErrors::new(py, file_path.clone()),
            diagnostics: ParserDiagnostics::new(py, file_path),
            checks_indentation,
        })
    }

    /// The diagnostics that the parse found, in the order it found them.
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
        let definitions = self.nodes.start::<ast::GlobalDefinition>();
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
            self.nodes.push(&definitions, definition);
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
            self.diagnostics
                .missing_newline_at_end_of_file_diagnostic(end_of_source, end_of_source)?;
        }
        let definitions = self.nodes.finish_tuple(definitions)?;
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
        if let Some(typed_name_start) = self
            .scanner
            .consume_definition_start(DEFINE_THE_POTENTIAL, POSITION)
        {
            let (definition, end) = self.parse_position_definition(start, typed_name_start)?;
            return Ok((definition.into(), end));
        }
        if let Some(typed_name_start) = self
            .scanner
            .consume_definition_start(DEFINE_THE_POTENTIAL, ACTION)
        {
            let (definition, end) = self.parse_action_definition(start, typed_name_start)?;
            return Ok((definition.into(), end));
        }
        if let Some(typed_name_start) = self
            .scanner
            .consume_definition_start(DEFINE_THE_POTENTIAL, VALUE)
        {
            let (definition, end) = self.parse_value_definition(start, typed_name_start)?;
            return Ok((definition.into(), end));
        }
        if let Some(typed_name_start) = self
            .scanner
            .consume_definition_start(DEFINE_THE_POTENTIAL, LITERAL)
        {
            let (definition, end) =
                self.parse_potential_literal_definition(start, typed_name_start)?;
            return Ok((definition.into(), end));
        }
        if let Some(typed_name_start) = self.scanner.consume_definition_start(DEFINE_THE, OPERATION)
        {
            return self.parse_operation_definition(OperationKind::Value, start, typed_name_start);
        }
        // An encoding definition's `define the encoding` also begins an encoding
        // operation definition, so the encoding operation definition is checked
        // first.
        if let Some(typed_name_start) = self
            .scanner
            .consume_definition_start(DEFINE_THE, ENCODING_OPERATION)
        {
            return self.parse_operation_definition(
                OperationKind::Encoding,
                start,
                typed_name_start,
            );
        }
        if let Some(typed_name_start) = self.scanner.consume_definition_start(DEFINE_THE, ENCODING)
        {
            let (definition, end) = self.parse_encoding_definition(start, typed_name_start)?;
            return Ok((definition.into(), end));
        }
        // The text does not begin a global definition.
        Err(self.expected_global_definition())
    }

    /// Parses the name content and terminator of a definition that is only a
    /// typed name with `name_type`, which begins at `typed_name_start`, and
    /// returns the typed name with the position after the `.`.
    ///
    /// ```ebnf
    /// "<", fully_qualified_global_name, ">", terminator
    /// ```
    fn parse_definition_name_and_terminator(
        &mut self,
        typed_name_start: Position,
        name_type: ast::NameType,
    ) -> ParseResult<(ast::GlobalTypedNameInDefinition<'py>, Position)> {
        let (name_content, name_text, _) = self.parse_global_name_definition_content()?;
        let location = self.ast.location(typed_name_start, self.scanner.position)?;
        let typed_name =
            self.global_typed_name_in_definition(location, name_type, name_content, name_text)?;
        // There is no `.`.
        let Some(end) = self.parse_terminator()? else {
            return Err(self.missing_terminator());
        };
        Ok((typed_name, end))
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
