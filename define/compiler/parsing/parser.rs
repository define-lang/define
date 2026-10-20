mod ast_builder;
mod lines;
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
use lines::{BLOCK_OPEN, LineInBlock, Lines, OPEN_BRACE};
use parse_error::{ParseError, ParseResult};
use parser_diagnostics::ParserDiagnostics;
use pyo3::prelude::*;
use pyo3::types::{PyList, PyString};
use scanner::{Position, Scanner, SourceText};
use syntax_errors::SyntaxErrors;
use vector_scan::{COMPONENT_SEPARATOR, LINE_FEED, NAME_CONTENT_END};

const DEFINE_THE_POTENTIAL: &[u8] = b"define the potential ";
const POSITION: &[u8] = b"position";
const DEFINE_THE_POTENTIAL_POSITION: &[u8] = b"define the potential position";
const NAME_CONTENT_START: u8 = b'<';
const IT_MAY_ONLY_CONTAIN_PARTICLES_WHERE: &[u8] = b"it may only contain particles where";
const IT_HAS_THE: &[u8] = b"it has the ";
const IT_ALSO_ASSIGNS_THE: &[u8] = b"it also assigns the ";
const CONSTRAINT_NAME_TYPES: [(&[u8], ast::NameType); 4] = [
    (b"position", ast::NameType::Position),
    (b"action", ast::NameType::Action),
    (b"value", ast::NameType::Value),
    (b"encoding", ast::NameType::Encoding),
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
            let Some(indentation) = self.lines().start_line(0)? else {
                continue;
            };
            if indentation > 0 {
                return Err(ParseError::not_yet_supported(
                    self.scanner.position,
                    "indentation outside a block",
                ));
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
        // The text does not begin a position definition, the only global
        // definition the parser supports so far.
        Err(self.errors.expected_global_definition(start, start))
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
        // TODO: Remove quality implication statements from potential position
        // definitions in the grammar and the AST. The parser will not support
        // them, so it leaves this tuple empty.
        let quality_implications = self.ast.empty_tuple();
        let (constraints, end) = if self.scanner.next_bytes_are(BLOCK_OPEN) {
            let (constraints, end) =
                self.parse_potential_position_definition_block(start, &fqun)?;
            (Some(constraints), end)
        } else {
            // There is no `.` or ` {`.
            let Some(end) = self.lines().parse_terminator()? else {
                return Err(self.missing_terminator_or_brace());
            };
            (None, end)
        };
        let location = self.ast.location(start, end)?;
        let definition = self.ast.position_definition(
            location,
            typed_name,
            quality_implications,
            constraints,
        )?;
        Ok((definition, end))
    }

    /// Returns the error for a definition whose `.` or ` {` is missing at the
    /// scanner's position.
    #[cold]
    #[inline(never)]
    fn missing_terminator_or_brace(&self) -> ParseError {
        let missing = self.scanner.position;
        // The line ends where the `.` or ` {` belongs.
        if self.scanner.next_byte_is(LINE_FEED) {
            return self.errors.missing_terminator_or_brace(missing, missing);
        }
        // A `{` follows the name without a space before it.
        if self.scanner.next_byte_is(OPEN_BRACE) {
            return self
                .errors
                .missing_whitespace_before_brace(missing, missing);
        }
        ParseError::not_yet_supported(missing, "anything but a terminator or ` {` here")
    }

    /// Parses the block of a potential position definition at the top level
    /// that begins at `start`, whose references take their default FQUN from
    /// `fqun`, and returns its position constraint block with the position
    /// after its `}`.
    ///
    /// ```ebnf
    /// potential_position_definition_block =
    ///     block_open,
    ///     { quality_implication_statement },
    ///     position_constraint_block,
    ///     block_close ;
    /// ```
    fn parse_potential_position_definition_block(
        &mut self,
        start: Position,
        fqun: &ast::Fqun<'py>,
    ) -> ParseResult<(ast::PositionConstraintBlock<'py>, Position)> {
        let block_open_end = self.lines().parse_block_open()?;
        let indentation = match self.lines().next_line_in_block(0)? {
            LineInBlock::Statement { indentation } => indentation,
            // The block is empty.
            LineInBlock::Close => {
                let close = self.scanner.position;
                return Err(self
                    .errors
                    .missing_potential_position_definition_content(close, close));
            }
            // The source ends where the block's content belongs.
            LineInBlock::EndOfSource => {
                return Err(self.errors.missing_potential_position_definition_content(
                    block_open_end,
                    block_open_end,
                ));
            }
        };
        let constraints_start = self.scanner.position;
        // The block has something other than a position constraint block.
        if !self.scanner.consume(IT_MAY_ONLY_CONTAIN_PARTICLES_WHERE) {
            return Err(self.invalid_potential_position_definition_block());
        }
        let constraints =
            self.parse_position_constraint_block(constraints_start, indentation, fqun)?;
        match self.lines().next_line_in_block(0)? {
            LineInBlock::Close => {}
            LineInBlock::Statement { .. } => {
                return Err(ParseError::not_yet_supported(
                    self.scanner.position,
                    "anything but `}` here",
                ));
            }
            // The source ends before the block's `}`.
            LineInBlock::EndOfSource => {
                return Err(self.missing_close_brace(start, block_open_end));
            }
        }
        let end = self.lines().parse_block_close()?;
        Ok((constraints, end))
    }

    /// Returns the error for a block that the source ends in, which a line from
    /// `start` up to `block_open_end`, the position after its `{`, opens.
    #[cold]
    #[inline(never)]
    fn missing_close_brace(&self, start: Position, block_open_end: Position) -> ParseError {
        let open_brace = Position {
            line: block_open_end.line,
            column: block_open_end.column - 1,
        };
        self.errors.missing_close_brace(start, open_brace)
    }

    /// Returns the error for a statement in a potential position definition
    /// block, at the scanner's position, that does not belong there.
    #[cold]
    #[inline(never)]
    fn invalid_potential_position_definition_block(&self) -> ParseError {
        let start = self.scanner.position;
        if self.scanner.next_bytes_are(IT_ALSO_ASSIGNS_THE) {
            return ParseError::not_yet_supported(start, "quality implication statements");
        }
        let statement = self.scanner.rest_of_line();
        let end = Position {
            line: start.line,
            column: start.after(statement).column - 1,
        };
        self.errors
            .invalid_potential_position_definition_block(start, end)
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
        match self.lines().next_line_in_block(indentation)? {
            LineInBlock::Statement { .. } => {}
            // The block is empty.
            LineInBlock::Close => {
                let close = self.scanner.position;
                return Err(self
                    .errors
                    .missing_position_constraint_content(close, close));
            }
            // The source ends where the block's content belongs.
            LineInBlock::EndOfSource => {
                return Err(self
                    .errors
                    .missing_position_constraint_content(block_open_end, block_open_end));
            }
        }
        let requirements = self.ast.start_tuple::<ast::PositionRequirementStatement>();
        loop {
            let requirement = self.parse_position_requirement_statement(fqun)?;
            self.ast.push(&requirements, requirement);
            match self.lines().next_line_in_block(indentation)? {
                LineInBlock::Statement { .. } => {}
                LineInBlock::Close => break,
                // The source ends before the block's `}`.
                LineInBlock::EndOfSource => {
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
        if !self.scanner.consume(IT_HAS_THE) {
            return Err(ParseError::not_yet_supported(
                start,
                "anything but a position requirement statement here",
            ));
        }
        let typed_name = self.parse_typed_global_name_reference(fqun)?;
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
    /// `fqun`.
    ///
    /// ```ebnf
    /// typed_global_name = name_type, "<", global_name, ">" ;
    /// ```
    fn parse_typed_global_name_reference(
        &mut self,
        fqun: &ast::Fqun<'py>,
    ) -> ParseResult<ast::GlobalTypedNameReference<'py>> {
        let start = self.scanner.position;
        let Some(&(_, name_type)) = CONSTRAINT_NAME_TYPES
            .iter()
            .find(|&&(keyword, _)| self.scanner.consume(keyword))
        else {
            return Err(ParseError::not_yet_supported(start, "this name type"));
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
        let (location, fqun, path) = self.parse_global_name_content()?;
        let Some(fqun) = fqun else {
            return Err(ParseError::not_yet_supported(
                self.scanner.position,
                "global names without a FQUN in definitions",
            ));
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
        if !self.scanner.consume_byte(NAME_CONTENT_START) {
            return Err(ParseError::not_yet_supported(
                self.scanner.position,
                "anything but `<` here",
            ));
        }
        let start = self.scanner.position;
        let (content, scanned) = self.scanner.consume_name_content();
        let end = self.scanner.position;
        if !content.is_known_ascii {
            return Err(ParseError::not_yet_supported(start, "non-ASCII names"));
        }
        if !scanned.is_global_name || !self.scanner.consume_byte(NAME_CONTENT_END) {
            return Err(ParseError::not_yet_supported(start, "this global name"));
        }
        let (fqun, path_start, path_text) = match scanned.last_component_separator {
            None => (None, start, content),
            Some(0) => {
                return Err(ParseError::not_yet_supported(
                    start,
                    "global names that start with `:`",
                ));
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
                    return Err(ParseError::not_yet_supported(
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

#[pymethods]
impl PythonParseResult {
    #[new]
    const fn new(
        program: Option<Py<PyAny>>,
        diagnostics: Py<PyList>,
        exception: Option<Py<PyAny>>,
    ) -> Self {
        Self {
            program,
            diagnostics,
            exception,
        }
    }
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
        Err(error) => return Err(error.into()),
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
