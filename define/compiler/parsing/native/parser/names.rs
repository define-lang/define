//! Local names, typed name references, and position references.

use crate::lines::TERMINATOR;
use crate::parse_error::{ParseError, ParseResult};
use crate::scanner::{Position, SourceText};
use crate::{ACTION, NAME_CONTENT_START, POSITION, POSITION_OR_ACTION, Parser, ast};
use vector_scan::{COMPONENT_SEPARATOR, LINE_FEED, NAME_CONTENT_END, PATH_SEPARATOR, SPACE};

pub const CHAIN_SEPARATOR: &[u8] = b"::";
/// The bytes that end a word, for errors that cover the word where something
/// else belongs.
const WORD_ENDS: [u8; 4] = [NAME_CONTENT_START, SPACE, TERMINATOR, LINE_FEED];

impl<'py, 'source> Parser<'py, 'source> {
    /// Consumes the one space between a word and the word after it, and
    /// returns whether a word follows it. Returns false, without consuming
    /// anything, when the line ends after the word, with or without spaces,
    /// or when something other than a space or a letter follows the word.
    pub(crate) fn space_before_word(&mut self) -> ParseResult<bool> {
        let spaces = self.scanner.next_space_count();
        if spaces == 1 {
            self.scanner.consume_bytes(1);
            return Ok(true);
        }
        let start = self.scanner.position;
        if spaces == 0 {
            let word = self.scanner.text_before_any(&WORD_ENDS);
            // A word follows without a space between them. Words start with a
            // letter; anything else is not a missing space but a mistake of
            // its own.
            if word.bytes.first().is_some_and(u8::is_ascii_alphabetic) {
                return Err(self
                    .errors
                    .missing_whitespace(start, start.after(word).previous_column()));
            }
            return Ok(false);
        }
        // The spaces end the line.
        if spaces == self.scanner.rest_of_line().bytes.len() {
            return Ok(false);
        }
        let last_space = Position {
            line: start.line,
            column: start.column + spaces - 1,
        };
        Err(self.errors.extra_whitespace(start, last_space))
    }

    /// Returns the position of the last character of the word at the
    /// scanner's position, or the scanner's position if there is no word
    /// there.
    #[cold]
    pub(crate) fn end_of_word(&self) -> Position {
        let start = self.scanner.position;
        let word = self.scanner.text_before_any(&WORD_ENDS);
        if word.bytes.is_empty() {
            start
        } else {
            start.after(word).previous_column()
        }
    }

    /// Parses a position reference, whose global names take their default
    /// FQUN from `fqun`.
    ///
    /// ```ebnf
    /// position_reference = typed_name, { "::", typed_name } ;
    /// ```
    pub(crate) fn parse_position_reference(
        &mut self,
        fqun: &ast::Fqun<'py>,
    ) -> ParseResult<ast::PositionReference<'py>> {
        let start = self.scanner.position;
        let typed_names = self.ast.start_tuple::<ast::TypedNameReference>();
        loop {
            // There is no typed name where the reference or its next part
            // belongs.
            if self.scanner.is_at_line_end() || self.scanner.next_byte_is(TERMINATOR) {
                let missing = self.scanner.position;
                return Err(self.errors.missing_position_reference(missing, missing));
            }
            let typed_name = self.parse_typed_name_reference(fqun)?;
            self.ast.push(&typed_names, typed_name);
            if !self.scanner.consume(CHAIN_SEPARATOR) {
                break;
            }
        }
        let typed_names = self.ast.finish_tuple(typed_names)?;
        let location = self.ast.location(start, self.scanner.position)?;
        Ok(self.ast.position_reference(location, typed_names, true)?)
    }

    /// Parses a typed name in a position reference, which is local or global,
    /// and whose global name takes its default FQUN from `fqun`.
    ///
    /// ```ebnf
    /// typed_name = ( "position" | "action" ), "<", ( local_name | global_name ), ">" ;
    /// ```
    fn parse_typed_name_reference(
        &mut self,
        fqun: &ast::Fqun<'py>,
    ) -> ParseResult<ast::TypedNameReference<'py>> {
        let start = self.scanner.position;
        // The name type is not `position` or `action`.
        let Some(name_type) = self.scanner.consume_any(&POSITION_OR_ACTION) else {
            return Err(self.expected_position_or_action());
        };
        // There is no `<`.
        if !self.scanner.consume_byte(NAME_CONTENT_START) {
            return Err(self.missing_open_angle_bracket());
        }
        let content_start = self.scanner.position;
        let (content, scanned) = self.scanner.consume_name_content();
        let content_end = self.scanner.position;
        let ends_name = self.scanner.next_byte_is(NAME_CONTENT_END);
        if ends_name && scanned.is_global_name {
            let (location, name_fqun, path) = self.global_name_parts(
                content,
                scanned.last_component_separator,
                content_start,
                content_end,
            )?;
            let name_content = self
                .ast
                .reference_global_name_content(location, name_fqun, path)?;
            let location = self.ast.location(start, self.scanner.position)?;
            let typed_name = self.ast.global_typed_name_reference(
                location,
                fqun.clone(),
                name_type,
                name_content,
            )?;
            return Ok(typed_name.into());
        }
        // The name content is neither a local name nor a global name that
        // ends with `>`.
        if !ends_name || !scanned.is_local_name {
            return Err(self.invalid_name_content(content, content_start, content_end));
        }
        let name_content = self.local_name_parts(content, content_start, content_end)?;
        let location = self.ast.location(start, self.scanner.position)?;
        Ok(self
            .ast
            .local_typed_name_reference(location, name_type, name_content)?
            .into())
    }

    /// Parses a typed local name in a reference, and returns it with its
    /// location.
    ///
    /// ```ebnf
    /// typed_local_name = ( "position" | "action" ), "<", local_name, ">" ;
    /// ```
    pub(crate) fn parse_typed_local_name_reference(
        &mut self,
    ) -> ParseResult<(ast::LocalTypedNameReference<'py>, ast::SourceLocation<'py>)> {
        let start = self.scanner.position;
        // The name type is not `position` or `action`.
        let Some(name_type) = self.scanner.consume_any(&POSITION_OR_ACTION) else {
            return Err(self.expected_position_or_action());
        };
        let name_content = self.parse_local_name_content()?;
        let location = self.ast.location(start, self.scanner.position)?;
        let typed_name =
            self.ast
                .local_typed_name_reference(location.clone(), name_type, name_content)?;
        Ok((typed_name, location))
    }

    /// Returns the error for a name type, at the scanner's position, that is
    /// not `position` or `action`.
    #[cold]
    #[inline(never)]
    pub(crate) fn expected_position_or_action(&self) -> ParseError {
        if let Some(error) = self.disallowed_character_after_any(&[POSITION, ACTION]) {
            return error;
        }
        let start = self.scanner.position;
        self.errors
            .expected_position_or_action(start, self.end_of_word())
    }

    /// Returns the error for name `content` in a position reference, from
    /// `start` up to `end`, the scanner's position, that is neither a local
    /// name nor a global name followed by `>`.
    #[cold]
    #[inline(never)]
    fn invalid_name_content(
        &self,
        content: SourceText<'source>,
        start: Position,
        end: Position,
    ) -> ParseError {
        if let Some(error) = self.name_content_error(content, start, end) {
            return error;
        }
        self.errors.invalid_name(
            start,
            end.previous_column(),
            &String::from_utf8_lossy(content.bytes),
        )
    }

    /// Returns the error for name `content` from `start` up to `end`, the
    /// scanner's position, that is empty, has a character that names do not
    /// allow, starts with a space, or has no `>` after its first word, if it
    /// has one of those errors.
    #[cold]
    fn name_content_error(
        &self,
        content: SourceText<'source>,
        start: Position,
        end: Position,
    ) -> Option<ParseError> {
        // There is no name between the `<` and where the `>` belongs.
        if content.bytes.is_empty() {
            return Some(self.errors.empty_name(start, start));
        }
        if let Err(error) = self.disallowed_name_character(content, start) {
            return Some(error);
        }
        match content.bytes.iter().position(|&byte| byte == SPACE) {
            // The name starts with a space.
            Some(0) => Some(self.errors.invalid_name(start, start, " ")),
            // A space ends the name's first word, where its `>` belongs.
            Some(space) => {
                let word = content.slice(..space);
                let missing = start.after(word);
                Some(self.errors.missing_close_angle_bracket(
                    missing,
                    missing,
                    &String::from_utf8_lossy(word.bytes),
                ))
            }
            // The name content runs to the end of the line without a `>`.
            None if !self.scanner.next_byte_is(NAME_CONTENT_END) => {
                Some(self.errors.missing_close_angle_bracket(
                    end,
                    end,
                    &String::from_utf8_lossy(content.bytes),
                ))
            }
            None => None,
        }
    }

    /// Parses the `<`, local name, and `>` that follow the name type of a
    /// local name in a definition or a position presence statement.
    ///
    /// ```ebnf
    /// "<", local_name, ">"
    /// ```
    pub(crate) fn parse_local_name_content(&mut self) -> ParseResult<ast::LocalNameContent<'py>> {
        // There is no `<`.
        if !self.scanner.consume_byte(NAME_CONTENT_START) {
            return Err(self.missing_open_angle_bracket());
        }
        let start = self.scanner.position;
        let (content, scanned) = self.scanner.consume_name_content();
        let end = self.scanner.position;
        // The name content is not a local name that ends with `>`.
        if !scanned.is_local_name || !self.scanner.next_byte_is(NAME_CONTENT_END) {
            return Err(self.invalid_local_name_content(content, scanned, start, end));
        }
        self.local_name_parts(content, start, end)
    }

    /// Parses local name `content`, from `start` up to `end`, where the
    /// scanner is before its `>`.
    fn local_name_parts(
        &mut self,
        content: SourceText<'source>,
        start: Position,
        end: Position,
    ) -> ParseResult<ast::LocalNameContent<'py>> {
        self.disallowed_name_character(content, start)?;
        self.scanner.consume_bytes(1);
        let location = self.ast.location(start, end)?;
        let name = self.ast.name(content)?;
        Ok(self.ast.local_name_content(location, name)?)
    }

    /// Returns the error for name `content`, from `start` up to `end`, the
    /// scanner's position, where a local name followed by `>` belongs.
    #[cold]
    #[inline(never)]
    fn invalid_local_name_content(
        &self,
        content: SourceText<'source>,
        scanned: vector_scan::NameContent,
        start: Position,
        end: Position,
    ) -> ParseError {
        // A space as the first character is not the end of a word.
        if content.bytes.first() == Some(&SPACE) {
            return self.errors.invalid_local_name_character(start, start, " ");
        }
        if let Some(error) = self.name_content_error(content, start, end) {
            return error;
        }
        // The name is a global name.
        if scanned.is_global_name {
            return self
                .errors
                .global_name_where_local_name_expected(start, end.previous_column());
        }
        // Every byte up to the first `:` or `/` is ASCII, since the name has
        // no character that names do not allow before it.
        let Some(index) = content
            .bytes
            .iter()
            .position(|&byte| byte == COMPONENT_SEPARATOR || byte == PATH_SEPARATOR)
        else {
            unreachable!("a name with no space, `:`, or `/` is a local name");
        };
        let position = start.after(content.slice(..index));
        let character = char::from(content.bytes[index]).to_string();
        self.errors
            .invalid_local_name_character(position, position, &character)
    }
}
