mod ast_builder;
// rustfmt runs on the source tree, which has ast.rs only after
// setup_local_dev copies it there.
#[rustfmt::skip]
mod ast;
// Generated like ast.rs, so rustfmt skips it for the same reason.
#[rustfmt::skip]
mod parser_exceptions;

use ast_builder::{AstBuilder, Node};
use pyo3::exceptions::PyNotImplementedError;
use pyo3::prelude::*;
use pyo3::types::PyString;
use std::slice::SliceIndex;
use vector_scan::{COMPONENT_SEPARATOR, LINE_FEED, NAME_CONTENT_END};

const DEFINE_THE_POTENTIAL: &[u8] = b"define the potential ";
const POSITION: &[u8] = b"position";
const NAME_CONTENT_START: u8 = b'<';
const TERMINATOR: u8 = b'.';

/// Text from the source, which is UTF-8 if the source is valid, but
/// usually is just ASCII.
#[derive(Clone, Copy)]
struct SourceText<'source> {
    bytes: &'source [u8],
    /// False when the text may contain non-ASCII bytes.
    is_known_ascii: bool,
}

impl<'source> SourceText<'source> {
    fn character_count(self) -> usize {
        if self.is_known_ascii {
            self.bytes.len()
        } else {
            vector_scan::character_count(self.bytes)
        }
    }

    /// Returns the text in the byte `range`, which must start and end on
    /// character boundaries.
    fn slice(self, range: impl SliceIndex<[u8], Output = [u8]>) -> Self {
        Self {
            bytes: &self.bytes[range],
            is_known_ascii: self.is_known_ascii,
        }
    }

    /// Splits the text at each occurrence of the ASCII `separator`.
    fn split(self, separator: u8) -> impl Iterator<Item = Self> {
        self.bytes
            .split(move |&byte| byte == separator)
            .map(move |bytes| Self {
                bytes,
                is_known_ascii: self.is_known_ascii,
            })
    }
}

/// A point in the source, as a 1-based line and a 1-based column counted in
/// characters.
#[derive(Clone, Copy)]
struct Position {
    line: usize,
    column: usize,
}

impl Position {
    /// Returns the position after `text`, which must not contain a line feed.
    fn after(self, text: SourceText) -> Self {
        Self {
            line: self.line,
            column: self.column + text.character_count(),
        }
    }

    // Keywords and punctuation are ASCII by construction, so they need no
    // `SourceText` (otherwise we would have to construct one pointlessly).
    /// Returns the position after the ASCII `text`, which must not contain a
    /// line feed.
    const fn after_ascii(self, text: &[u8]) -> Self {
        Self {
            line: self.line,
            column: self.column + text.len(),
        }
    }
}

struct Scanner<'source> {
    /// The source that has not been consumed yet.
    rest: &'source [u8],
    position: Position,
}

impl<'source> Scanner<'source> {
    const fn new(source: &'source [u8]) -> Self {
        Self {
            rest: source,
            position: Position { line: 1, column: 1 },
        }
    }

    const fn is_at_end(&self) -> bool {
        self.rest.is_empty()
    }

    const fn is_at_line_feed(&self) -> bool {
        matches!(self.rest.first(), Some(&LINE_FEED))
    }

    /// Consumes `expected` if the remaining text starts with it. `expected`
    /// must be ASCII without a line feed.
    fn consume(&mut self, expected: &[u8]) -> bool {
        let Some(rest) = self.rest.strip_prefix(expected) else {
            return false;
        };
        self.rest = rest;
        self.position = self.position.after_ascii(expected);
        true
    }

    /// Consumes `expected` if it is the next byte. `expected` must be ASCII and
    /// not a line feed.
    fn consume_byte(&mut self, expected: u8) -> bool {
        let Some((&byte, rest)) = self.rest.split_first() else {
            return false;
        };
        if byte != expected {
            return false;
        }
        self.rest = rest;
        self.position.column += 1;
        true
    }

    fn consume_line_feed(&mut self) -> bool {
        let Some(rest) = self.rest.strip_prefix(&[LINE_FEED]) else {
            return false;
        };
        self.rest = rest;
        self.position = Position {
            line: self.position.line + 1,
            column: 1,
        };
        true
    }

    /// Consumes the name content before the first `>` or line feed, or all of
    /// the remaining text if it contains neither, and returns it with what the
    /// scan found in it.
    fn consume_name_content(&mut self) -> (SourceText<'source>, vector_scan::NameContent) {
        let scanned = vector_scan::name_content(self.rest);
        let (bytes, rest) = self.rest.split_at(scanned.length);
        let text = SourceText {
            bytes,
            is_known_ascii: scanned.is_ascii,
        };
        self.rest = rest;
        self.position.column += scanned.character_count;
        (text, scanned)
    }
}

enum ParseError {
    /// Source that the parser does not handle yet.
    NotYetSupported {
        position: Position,
        description: &'static str,
    },
    /// A syntax error in the source, as an exception from `parser_exceptions`.
    Syntax(PyErr),
    /// An exception that Python raised while the parser built the AST.
    Python(PyErr),
}

impl From<PyErr> for ParseError {
    fn from(error: PyErr) -> Self {
        Self::Python(error)
    }
}

impl From<ParseError> for PyErr {
    fn from(error: ParseError) -> Self {
        match error {
            ParseError::NotYetSupported {
                position: Position { line, column },
                description,
            } => PyNotImplementedError::new_err(format!(
                "line {line}, column {column}: the parser does not support {description} yet"
            )),
            ParseError::Syntax(error) | ParseError::Python(error) => error,
        }
    }
}

type ParseResult<T> = Result<T, ParseError>;

struct Parser<'py, 'source> {
    scanner: Scanner<'source>,
    ast: AstBuilder<'py, 'source>,
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
        let Some(start) = start else {
            let location = self.ast.location(end, end)?;
            return Err(ParseError::Syntax(
                parser_exceptions::expected_global_definition(location, ""),
            ));
        };
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
        if self.scanner.consume(DEFINE_THE_POTENTIAL) {
            let typed_name_start = self.scanner.position;
            if self.scanner.consume(POSITION) {
                let (definition, end) = self.parse_position_definition(start, typed_name_start)?;
                return Ok((definition.into(), end));
            }
        }
        Err(Self::not_yet_supported(
            start,
            "definitions other than position definitions",
        ))
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

    /// Parses a terminator and returns the position after its `.`.
    ///
    /// ```ebnf
    /// terminator = ".", ( newline | " ", { " " }, comment ) ;
    /// ```
    fn parse_terminator(&mut self) -> ParseResult<Position> {
        if !self.scanner.consume_byte(TERMINATOR) {
            let position = self.scanner.position;
            if self.scanner.is_at_line_feed() {
                let location = self.ast.location(position, position)?;
                return Err(ParseError::Syntax(
                    parser_exceptions::missing_terminator_or_brace(location, "\n"),
                ));
            }
            return Err(Self::not_yet_supported(
                position,
                "anything but a terminator here",
            ));
        }
        let end = self.scanner.position;
        if !self.scanner.consume_line_feed() {
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
        let path_start = Position {
            column: fqun_end.column + 1,
            ..fqun_end
        };
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
                component_start = Position {
                    column: end.column + 1,
                    ..end
                };
                Some(self.ast.multiverse(location, name)?)
            }
            None => None,
        };
        let authority = match authority {
            Some(name) => {
                let (location, name, end) = self.fqun_component(name, component_start)?;
                component_start = Position {
                    column: end.column + 1,
                    ..end
                };
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
    let program = Parser {
        scanner: Scanner::new(source),
        ast: AstBuilder::new(py, file_path)?,
    }
    .parse_program()?;
    Ok(program.into_object())
}

#[pymodule(gil_used = false)]
fn native_parser(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(parse, module)?)
}
