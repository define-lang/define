//! Value definitions.

use crate::ast;
use crate::parse_error::ParseResult;
use crate::parser::Parser;
use crate::scanner::Position;

impl<'py, 'source> Parser<'py, 'source> {
    /// Parses the rest of a value definition after its `value`, given the
    /// positions of the definition's start and of its `value`, and returns the
    /// definition with the position after its `.`.
    ///
    /// ```ebnf
    /// value_definition = "define the potential", " ", fully_qualified_value_name, terminator ;
    /// ```
    pub(crate) fn parse_value_definition(
        &mut self,
        start: Position,
        typed_name_start: Position,
    ) -> ParseResult<(ast::ValueDefinition<'py>, Position)> {
        let (typed_name, end) =
            self.parse_definition_name_and_terminator(typed_name_start, ast::NameType::Value)?;
        let location = self.ast.location(start, end)?;
        Ok((self.ast.value_definition(location, typed_name)?, end))
    }
}
