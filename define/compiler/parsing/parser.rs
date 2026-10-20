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
use vector_scan::{COMMENT_START, COMPONENT_SEPARATOR, LINE_FEED, LineEnd, NAME_CONTENT_END};

const DEFINE_THE_POTENTIAL: &[u8] = b"define the potential ";
const POSITION: &[u8] = b"position";
const DEFINE_THE_POTENTIAL_POSITION: &[u8] = b"define the potential position";
const NAME_CONTENT_START: u8 = b'<';
const TERMINATOR: u8 = b'.';

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
            if !self.start_line()? {
                continue;
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

    /// Parses a terminator through the end of its line, and returns the
    /// position after its `.`.
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
        // Something other than a line feed or a comment follows the `.`.
        if !self.end_line()? {
            return Err(self.errors.missing_newline_after_terminator(end, end));
        }
        Ok(end)
    }

    /// Consumes the line if it is blank or a comment, and returns whether a
    /// statement starts on it.
    fn start_line(&mut self) -> ParseResult<bool> {
        match self.scanner.scan_line_end() {
            LineEnd::Ordinary { length } => {
                self.consume_ordinary_line_end(length);
                Ok(false)
            }
            LineEnd::Text {
                leading_space_count: 0,
            } => Ok(true),
            LineEnd::Text { .. } => Err(Self::not_yet_supported(
                self.scanner.position,
                "indentation",
            )),
            LineEnd::Unusual {
                leading_space_count,
            } => {
                self.end_unusual_line(leading_space_count)?;
                Ok(false)
            }
        }
    }

    /// Consumes the rest of the line, including its line feed, if it is empty
    /// or a comment, and returns whether it did. At the end of the source, the
    /// line has no line feed.
    ///
    /// ```ebnf
    /// newline | comment
    /// ```
    fn end_line(&mut self) -> ParseResult<bool> {
        // Most statements end with a line feed right after them, which needs no
        // vector scan.
        if self.scanner.consume_line_feed() || self.scanner.is_at_end() {
            return Ok(true);
        }
        match self.scanner.scan_line_end() {
            LineEnd::Ordinary { length } => {
                self.consume_ordinary_line_end(length);
                Ok(true)
            }
            LineEnd::Text { .. } => Ok(false),
            LineEnd::Unusual {
                leading_space_count,
            } => {
                self.end_unusual_line(leading_space_count)?;
                Ok(true)
            }
        }
    }

    fn consume_ordinary_line_end(&mut self, length: usize) {
        self.scanner.consume_bytes(length);
        self.scanner.consume_line_feed();
    }

    /// Consumes the rest of a line, including its line feed, that
    /// `vector_scan::line_end` finds unusual after `leading_space_count`
    /// spaces.
    #[cold]
    #[inline(never)]
    fn end_unusual_line(&mut self, leading_space_count: usize) -> ParseResult<()> {
        let start = self.scanner.position;
        self.scanner.consume_bytes(leading_space_count);
        // The line ends with spaces.
        if !self.scanner.next_byte_is(COMMENT_START) {
            return Err(self.errors.trailing_whitespace_error(start, start, " "));
        }
        let comment_start = self.scanner.position;
        let comment = self.scanner.consume_rest_of_line();
        let Ok(characters) = str::from_utf8(comment.bytes) else {
            return Err(Self::not_yet_supported(
                comment_start,
                "invalid UTF-8 in comments",
            ));
        };
        // TODO: Check comments for invisible characters here, instead of in
        // the Python check that runs before this parser. Every comment that is
        // not printable ASCII comes here, so this loop sees every character
        // that could be invisible.
        if characters.chars().any(char::is_control) {
            return Err(Self::not_yet_supported(
                comment_start,
                "control characters in comments",
            ));
        }
        let content_length = characters.trim_end_matches(' ').len();
        // The comment ends with spaces.
        if content_length < comment.bytes.len() {
            let trailing_whitespace = comment_start.after(comment.slice(..content_length));
            return Err(self.errors.trailing_whitespace_error(
                trailing_whitespace,
                trailing_whitespace,
                " ",
            ));
        }
        self.scanner.consume_line_feed();
        Ok(())
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
