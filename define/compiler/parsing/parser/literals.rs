//! Literals.

use crate::ast;
use crate::characters::{self, TextKind};
use crate::parse_error::{ParseError, ParseResult};
use crate::parser::Parser;
use crate::parser::names::FqunWithCanonicalText;
use crate::scanner::{Position, SourceText};
use pyo3::prelude::*;
use pyo3::types::PyString;
use terminals::{ESCAPE, ESCAPED_LINE_FEED, LITERAL, LITERAL_CONTENT_DELIMITER};

impl<'py, 'source> Parser<'py, 'source> {
    /// Parses a literal, whose global name takes its default FQUN from `fqun`.
    ///
    /// ```ebnf
    /// literal = "literal", "<", global_name, ">", '"', literal_content, '"' ;
    /// ```
    pub(crate) fn parse_literal(
        &mut self,
        fqun: &FqunWithCanonicalText<'py, 'source>,
    ) -> ParseResult<ast::Literal<'py>> {
        let start = self.scanner.position;
        self.scanner.consume(LITERAL);
        let name = self.parse_global_name_content()?;
        let typed_name_location = self.ast.location(start, self.scanner.position)?;
        let (potential_literal, _) = self.global_typed_name_reference(
            typed_name_location,
            fqun,
            ast::NameType::Literal,
            name,
        )?;
        // There is no `"` before the literal content.
        if !self.scanner.consume_byte(LITERAL_CONTENT_DELIMITER) {
            return Err(self.missing_literal_content_start());
        }
        let content = self.parse_literal_content()?;
        let location = self.ast.location(start, self.scanner.position)?;
        Ok(self.ast.literal(location, potential_literal, content)?)
    }

    /// Parses literal content and the `"` after it, and returns the content
    /// with its escapes replaced by what they stand for.
    ///
    /// ```ebnf
    /// literal_content, '"'
    /// ```
    fn parse_literal_content(&mut self) -> ParseResult<Bound<'py, PyString>> {
        let start = self.scanner.position;
        let content = self.scanner.consume_literal_content();
        if content.has_escape {
            return self.parse_escaped_literal_content(start, content.written);
        }
        // The line or the source ends where the `"` after the content belongs.
        if !self.scanner.consume_byte(LITERAL_CONTENT_DELIMITER) {
            return Err(self.missing_literal_content_end());
        }
        self.disallowed_literal_character(content.written, start)?;
        Ok(self.ast.string(content.written.bytes)?)
    }

    /// Parses the `"` after literal content, as it is `written` with its
    /// escapes, which begins at `start`, and returns the content with its
    /// escapes replaced by what they stand for.
    ///
    /// ```ebnf
    /// '"'
    /// ```
    // Escapes are rare, so this is the only part of a literal that builds its
    // content in a buffer.
    #[inline(never)]
    fn parse_escaped_literal_content(
        &mut self,
        start: Position,
        written: SourceText<'source>,
    ) -> ParseResult<Bound<'py, PyString>> {
        let content = self.literal_content_without_escapes(start, written)?;
        // The line or the source ends where the `"` after the content belongs.
        if !self.scanner.consume_byte(LITERAL_CONTENT_DELIMITER) {
            return Err(self.missing_literal_content_end());
        }
        // The content is checked as it is written, escapes and all, so that the
        // characters on either side of each character are the ones written.
        self.disallowed_literal_character(written, start)?;
        Ok(self.ast.string(&content)?)
    }

    /// Returns literal content, as it is `written` with its escapes, which
    /// begins at `start`, with its escapes replaced by what they stand for.
    fn literal_content_without_escapes(
        &self,
        start: Position,
        written: SourceText<'source>,
    ) -> ParseResult<Vec<u8>> {
        let mut content = Vec::with_capacity(written.bytes.len());
        let mut offset = 0;
        while let Some(index) = written.bytes[offset..]
            .iter()
            .position(|&byte| byte == ESCAPE)
        {
            let escape = offset + index;
            content.extend_from_slice(&written.bytes[offset..escape]);
            let escaped_offset = escape + 1;
            let escaped = match written.bytes.get(escaped_offset) {
                Some(&byte @ (LITERAL_CONTENT_DELIMITER | ESCAPE)) => byte,
                Some(&ESCAPED_LINE_FEED) => b'\n',
                _ => return Err(self.invalid_literal_escape(start, written, escaped_offset)),
            };
            content.push(escaped);
            offset = escaped_offset + 1;
        }
        content.extend_from_slice(&written.bytes[offset..]);
        Ok(content)
    }

    /// Returns the error for a character in literal `content`, which begins at
    /// `start`, that literal content does not allow, if it has one.
    fn disallowed_literal_character(
        &self,
        content: SourceText<'source>,
        start: Position,
    ) -> ParseResult<()> {
        // TODO: Make these characters diagnostics, as they are in comments,
        // if structural validation is merged into the parser. Until then, a
        // literal's content must be what the spec allows for it to be part of
        // a valid AST.
        // The literal content has a character that literal content does not
        // allow.
        if !content.is_known_ascii
            && let Some(error) = characters::first_disallowed_character(
                &self.errors,
                start,
                content.bytes,
                TextKind::LiteralContent,
            )
        {
            return Err(error);
        }
        Ok(())
    }
}

// The functions that only run on an error path.
impl<'py, 'source> Parser<'py, 'source> {
    /// Returns the error for a literal whose `"` before its content is missing
    /// at the scanner's position.
    #[cold]
    #[inline(never)]
    fn missing_literal_content_start(&self) -> ParseError {
        if let Some(error) = self.disallowed_character_ahead(0) {
            return error;
        }
        let missing = self.scanner.position;
        self.errors.missing_literal_content_start(missing, missing)
    }

    /// Returns the error for literal content whose `"` after it is missing at
    /// the scanner's position, where the line or the source ends.
    #[cold]
    #[inline(never)]
    fn missing_literal_content_end(&self) -> ParseError {
        let missing = self.scanner.position;
        self.errors.missing_literal_content_end(missing, missing)
    }

    /// Returns the error for the character `escaped_offset` bytes into literal
    /// content, as it is `written` with its escapes, which begins at `start`,
    /// that is after a `\` but does not begin an escape.
    #[cold]
    #[inline(never)]
    fn invalid_literal_escape(
        &self,
        start: Position,
        written: SourceText<'source>,
        escaped_offset: usize,
    ) -> ParseError {
        let position = start.after(written.slice(..escaped_offset));
        let escaped = &written.bytes[escaped_offset..];
        if let Some(error) = characters::disallowed_first_character(&self.errors, position, escaped)
        {
            return error;
        }
        let Some(character) = escaped
            .utf8_chunks()
            .next()
            .and_then(|chunk| chunk.valid().chars().next())
        else {
            // The line or the source ends right after the `\`, where the `"`
            // after the content belongs.
            return self.errors.missing_literal_content_end(position, position);
        };
        self.errors
            .invalid_literal_escape(position, position, character.encode_utf8(&mut [0; 4]))
    }
}
