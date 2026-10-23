//! Encoding definitions.

use crate::ast;
use crate::parse_error::ParseResult;
use crate::parser::Parser;
use crate::scanner::Position;

impl<'py, 'source> Parser<'py, 'source> {
    /// Parses the rest of an encoding definition after its `encoding`, given
    /// the positions of the definition's start and of its `encoding`, and
    /// returns the definition with the position after its `.`.
    ///
    /// ```ebnf
    /// encoding_definition = "define the", " ", fully_qualified_encoding_name, terminator ;
    /// ```
    pub(crate) fn parse_encoding_definition(
        &mut self,
        start: Position,
        typed_name_start: Position,
    ) -> ParseResult<(ast::EncodingDefinition<'py>, Position)> {
        let (typed_name, end) =
            self.parse_definition_name_and_terminator(typed_name_start, ast::NameType::Encoding)?;
        let location = self.ast.location(start, end)?;
        Ok((self.ast.encoding_definition(location, typed_name)?, end))
    }
}
