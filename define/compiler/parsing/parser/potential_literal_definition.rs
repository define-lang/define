//! Potential literal definitions and their encoding constraints.

use crate::ast;
use crate::parse_error::{ParseError, ParseResult};
use crate::parser::Parser;
use crate::parser::lines::LineInBlock;
use crate::scanner::Position;
use terminals::{ENCODING, IT_HAS_THE};

/// The one name type that an encoding constraint allows.
const ENCODING_NAME_TYPE: [(&[u8], ast::NameType); 1] = [(ENCODING, ast::NameType::Encoding)];

impl<'py, 'source> Parser<'py, 'source> {
    /// Parses the rest of a potential literal definition after its `literal`,
    /// given the positions of the definition's start and of its `literal`, and
    /// returns the definition with the position after its `}`.
    ///
    /// ```ebnf
    /// potential_literal_definition =
    ///     "define the potential",
    ///     " ",
    ///     fully_qualified_potential_literal_name,
    ///     potential_literal_definition_block ;
    /// potential_literal_definition_block =
    ///     block_open,
    ///     encoding_constraint,
    ///     block_close ;
    /// ```
    pub(crate) fn parse_potential_literal_definition(
        &mut self,
        start: Position,
        typed_name_start: Position,
    ) -> ParseResult<(ast::PotentialLiteralDefinition<'py>, Position)> {
        let (name_content, fqun) = self.parse_global_name_definition_content()?;
        let typed_name_location = self.ast.location(typed_name_start, self.scanner.position)?;
        let typed_name = self.ast.global_typed_name_in_definition(
            typed_name_location,
            ast::NameType::Literal,
            name_content,
        )?;
        let block_open_end = self.parse_block_open()?;
        match self.next_line_in_block(0, &[IT_HAS_THE])? {
            LineInBlock::Statement => {}
            // The block is empty.
            LineInBlock::Close => {
                let close = self.scanner.position;
                return Err(self
                    .errors
                    .invalid_potential_literal_definition_block(close, close));
            }
            // The block ends where its encoding constraint belongs.
            LineInBlock::Unclosed => {
                return Err(self
                    .errors
                    .invalid_potential_literal_definition_block(block_open_end, block_open_end));
            }
        }
        let encoding = self.parse_encoding_constraint(&fqun)?;
        let end = self.parse_block_close_after_content(
            start,
            block_open_end,
            0,
            Self::statement_instead_of_close_brace,
        )?;
        let location = self.ast.location(start, end)?;
        let definition = self
            .ast
            .potential_literal_definition(location, typed_name, encoding)?;
        Ok((definition, end))
    }

    /// Parses an encoding constraint, whose reference takes its default FQUN
    /// from `fqun`, through the end of its line, and returns its encoding.
    ///
    /// ```ebnf
    /// encoding_constraint = "it has the", " ", "encoding", "<", global_name, ">", terminator ;
    /// ```
    fn parse_encoding_constraint(
        &mut self,
        fqun: &ast::Fqun<'py>,
    ) -> ParseResult<ast::GlobalTypedNameReference<'py>> {
        // The statement is not an encoding constraint.
        if !self.scanner.consume(IT_HAS_THE) {
            return Err(self.invalid_potential_literal_definition_statement());
        }
        // The line ends, or a non-letter character comes, where the typed name
        // belongs.
        if !self.space_before_word()? {
            return Err(self.expected_encoding_name_type());
        }
        let encoding = self.parse_typed_global_name_reference(
            fqun,
            &ENCODING_NAME_TYPE,
            Self::expected_encoding_name_type,
        )?;
        // There is no `.`.
        if self.parse_terminator()?.is_none() {
            return Err(self.missing_terminator());
        }
        Ok(encoding)
    }
}

// The functions that only run on an error path.
impl<'py, 'source> Parser<'py, 'source> {
    /// Returns the error for a statement at the scanner's position in a
    /// potential literal definition block that is not an encoding constraint.
    #[cold]
    #[inline(never)]
    fn invalid_potential_literal_definition_statement(&self) -> ParseError {
        if let Some(error) = self.disallowed_character_after(IT_HAS_THE) {
            return error;
        }
        // The line begins like an encoding constraint, but with extra or
        // missing spaces between two of its words.
        if let Some(error) = self.misspaced_words_in_any(&[IT_HAS_THE]) {
            return error;
        }
        let start = self.scanner.position;
        self.errors
            .invalid_potential_literal_definition_block(start, self.end_of_line())
    }

    /// Returns the error for a name type, at the scanner's position, that is
    /// not `encoding`, in an encoding constraint.
    #[cold]
    #[inline(never)]
    fn expected_encoding_name_type(&self) -> ParseError {
        if let Some(error) = self.disallowed_character_after(ENCODING) {
            return error;
        }
        let start = self.scanner.position;
        self.errors
            .invalid_potential_literal_definition_block(start, self.scanner.end_of_word())
    }
}
