mod ast_builder;
mod parse_error;
mod scanner;
// rustfmt runs on the source tree, which has ast.rs only after
// setup_local_dev copies it there.
#[rustfmt::skip]
mod ast;
// Generated like ast.rs, so rustfmt skips it for the same reason.
#[rustfmt::skip]
mod syntax_errors;

use ast_builder::{AstBuilder, FilePath, Node};
use parse_error::{ParseError, ParseResult};
use pyo3::prelude::*;
use pyo3::types::PyString;
use scanner::{Position, Scanner, SourceText};
use syntax_errors::SyntaxErrors;
use vector_scan::{COMPONENT_SEPARATOR, LINE_FEED, NAME_CONTENT_END, SPACE};

const DEFINE_THE_POTENTIAL: &[u8] = b"define the potential ";
const POSITION: &[u8] = b"position";
const DEFINE_THE_POTENTIAL_POSITION: &[u8] = b"define the potential position";
const NAME_CONTENT_START: u8 = b'<';
const TERMINATOR: u8 = b'.';
const COMMENT_START: u8 = b'#';

struct Parser<'py, 'source> {
    scanner: Scanner<'source>,
    ast: AstBuilder<'py, 'source>,
    errors: SyntaxErrors<'py>,
}

impl<'py, 'source> Parser<'py, 'source> {
    const fn not_yet_supported(position: Position, description: &'static str) -> ParseError {
        ParseError::NotYetSupported {
            position,
            description,
        }
    }

    /// Parses a program: one or more global definitions, with any number of
    /// blank lines before, between, and after them.
    ///
    /// ```ebnf
    /// program = { newline }, global_definition, { { newline }, global_definition }, { newline } ;
    /// ```
    fn parse_program(&mut self) -> ParseResult<ast::Program<'py>> {
        let definitions = self.ast.start_tuple::<ast::GlobalDefinition>();
        let mut start = None;
        let mut end = self.scanner.position;
        loop {
            while self.scanner.consume_line_feed() {}
            if self.scanner.is_at_end() {
                break;
            }
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
    /// terminator's `.`.
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
        // Spaces can begin a comment.
        if self.scanner.next_byte_is(COMMENT_START) || self.scanner.next_byte_is(SPACE) {
            return Err(Self::not_yet_supported(start, "comments"));
        }
        if self.scanner.next_bytes_are(DEFINE_THE_POTENTIAL_POSITION) {
            self.scanner.consume(DEFINE_THE_POTENTIAL);
            let typed_name_start = self.scanner.position;
            self.scanner.consume(POSITION);
            let (definition, end) = self.parse_position_definition(start, typed_name_start)?;
            return Ok((definition.into(), end));
        }
        // The text does not begin a position definition, the only global
        // definition the parser supports so far.
        Err(self.errors.expected_global_definition(start, start))
    }

    /// Parses the rest of a position definition after its `position`, given
    /// the positions of the definition's start and of its `position`, and
    /// returns the definition with the position after its terminator's `.`.
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
        let name_content = self.parse_global_name_definition_content()?;
        let typed_name_location = self.ast.location(typed_name_start, self.scanner.position)?;
        let typed_name = self.ast.global_typed_name_in_definition(
            typed_name_location,
            ast::NameType::Position,
            name_content,
        )?;
        let end = self.parse_terminator()?;
        let location = self.ast.location(start, end)?;
        let quality_implications = self.ast.empty_tuple();
        let definition =
            self.ast
                .position_definition(location, typed_name, quality_implications, None)?;
        Ok((definition, end))
    }

    /// Parses a terminator up to the line feed that ends it, which is left for
    /// the caller, and returns the position after its `.`.
    ///
    /// ```ebnf
    /// terminator = ".", ( newline | " ", { " " }, comment ) ;
    /// ```
    fn parse_terminator(&mut self) -> ParseResult<Position> {
        let terminator = self.scanner.position;
        // There is no `.`.
        if !self.scanner.consume_byte(TERMINATOR) {
            // The line ends where the `.` belongs.
            if self.scanner.next_byte_is(LINE_FEED) {
                return Err(self
                    .errors
                    .missing_terminator_or_brace(terminator, terminator));
            }
            return Err(Self::not_yet_supported(
                terminator,
                "anything but a terminator here",
            ));
        }
        let end = self.scanner.position;
        // A comment follows the `.` without a space between them.
        if self.scanner.next_byte_is(COMMENT_START) {
            return Err(self.errors.missing_space_before_comment(terminator, end));
        }
        // Something other than a line feed or a space follows the `.`. At the end
        // of the source, parse_program reports the missing line feed instead.
        if !self.scanner.is_at_end()
            && !self.scanner.next_byte_is(LINE_FEED)
            && !self.scanner.next_byte_is(SPACE)
        {
            return Err(self.errors.missing_newline_after_terminator(end, end));
        }
        if self.scanner.next_byte_is(SPACE) {
            return Err(Self::not_yet_supported(
                self.scanner.position,
                "anything but a line feed after a terminator's `.`",
            ));
        }
        Ok(end)
    }

    /// Parses the `<`, fully qualified global name, and `>` that follow the name
    /// type of a global name in a definition.
    ///
    /// ```ebnf
    /// "<", fully_qualified_global_name, ">"
    /// fully_qualified_global_name = fqun, global_name_path ;
    /// ```
    fn parse_global_name_definition_content(
        &mut self,
    ) -> ParseResult<ast::DefinitionGlobalNameContent<'py>> {
        if !self.scanner.consume_byte(NAME_CONTENT_START) {
            return Err(Self::not_yet_supported(
                self.scanner.position,
                "anything but `<` here",
            ));
        }
        let start = self.scanner.position;
        let (content, scanned) = self.scanner.consume_name_content();
        let end = self.scanner.position;
        if !content.is_known_ascii {
            return Err(Self::not_yet_supported(start, "non-ASCII names"));
        }
        if !scanned.is_global_name || !self.scanner.consume_byte(NAME_CONTENT_END) {
            return Err(Self::not_yet_supported(start, "this global name"));
        }
        let Some(separator) = scanned.last_component_separator.filter(|&index| index > 0) else {
            return Err(Self::not_yet_supported(
                start,
                "global names without a FQUN in definitions",
            ));
        };
        let (fqun, fqun_end) = self.parse_fqun(content.slice(..separator), start)?;
        let path_start = fqun_end.next_column();
        let path_location = self.ast.location(path_start, end)?;
        let path_name = self.ast.name(content.slice(separator + 1..))?;
        let path = self.ast.global_path_name(path_location, path_name)?;
        let location = self.ast.location(start, end)?;
        Ok(self
            .ast
            .definition_global_name_content(location, fqun, path)?)
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
                _ => {
                    return Err(Self::not_yet_supported(
                        start,
                        "FQUNs with more than three components",
                    ));
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

/// Parses UTF-8 Define source code into an `ast.Program`.
#[pyfunction]
fn parse<'py>(
    py: Python<'py>,
    source: &[u8],
    file_path: Option<Bound<'py, PyAny>>,
) -> PyResult<Bound<'py, PyAny>> {
    let file_path = file_path.map(FilePath::new);
    let program = Parser {
        scanner: Scanner::new(source),
        ast: AstBuilder::new(py, file_path.clone())?,
        errors: SyntaxErrors::new(py, file_path),
    }
    .parse_program()?;
    Ok(program.into_object())
}

#[pymodule(gil_used = false)]
fn native_parser(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(parse, module)?)
}
