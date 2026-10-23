//! The structure of lines: indentation, comments, line ends, terminators, the
//! spaces between words, and the lines that open and close blocks. Nothing
//! here builds any of the AST.

use crate::characters::{self, TextKind};
use crate::parse_error::{ParseError, ParseResult};
use crate::parser::Parser;
use crate::scanner::{Position, WORD_ENDS};
use pyo3::PyResult;
use terminals::BLOCK_OPEN;
use terminals::{CLOSE_BRACE, COMMENT_START, OPEN_BRACE, SPACE, TERMINATOR};
use vector_scan::LineEnd;

/// How much deeper than the statement that opens a block each line in the
/// block is indented.
pub(crate) const INDENTATION_WIDTH: usize = 4;

/// What comes next in a block, after any blank and comment lines.
pub(crate) enum LineInBlock {
    /// The block's `}`.
    Close,
    /// A statement.
    Statement,
    /// The source ends, or a line indented less than the block's lines that
    /// begins none of the block's statements comes, where a line of the block
    /// belongs.
    Unclosed,
}

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

    /// Parses the ` {` that opens a block, through the end of its line, and
    /// returns the position after the `{`.
    ///
    /// ```ebnf
    /// block_open = " ", "{", newline ;
    /// ```
    #[inline]
    pub(crate) fn parse_block_open(&mut self) -> ParseResult<Position> {
        // There is no ` {`.
        if !self.scanner.consume(BLOCK_OPEN) {
            return Err(self.missing_block_open());
        }
        let end = self.scanner.position;
        // Something other than a line feed or a comment follows the `{`.
        if !self.end_line_after_brace(end.previous_column(), end)? {
            return Err(self.text_after_block_open());
        }
        Ok(end)
    }

    /// Parses the `}` that closes a block, which `next_line_in_block` found
    /// next, through the end of its line, and returns the position after the
    /// `}`.
    ///
    /// ```ebnf
    /// block_close = "}", newline ;
    /// ```
    #[inline]
    pub(crate) fn parse_block_close(&mut self) -> ParseResult<Position> {
        self.scanner.consume_bytes(1);
        let end = self.scanner.position;
        // Something other than a line feed or a comment follows the `}`.
        if !self.end_line_after_brace(end.previous_column(), end)? {
            return Err(self.text_after_block_close(end));
        }
        Ok(end)
    }

    /// Parses the rest of a block, whose content has been parsed, through the
    /// end of its `}` line, where a line from `start` up to `block_open_end`,
    /// the position after its `{`, indented `opener_indentation` spaces, opens
    /// the block. Returns the position after the `}`.
    /// `statement_instead_of_close` returns the error for a statement where
    /// the `}` belongs.
    ///
    /// ```ebnf
    /// block_close
    /// ```
    #[inline]
    pub(crate) fn parse_block_close_after_content(
        &mut self,
        start: Position,
        block_open_end: Position,
        opener_indentation: usize,
        statement_instead_of_close: fn(&Self) -> ParseError,
    ) -> ParseResult<Position> {
        match self.next_line_in_block(opener_indentation, &[])? {
            LineInBlock::Close => {}
            // A statement is where the block's `}` belongs.
            LineInBlock::Statement => return Err(statement_instead_of_close(self)),
            // The block ends before its `}`.
            LineInBlock::Unclosed => {
                return Err(self.missing_close_brace(start, block_open_end));
            }
        }
        self.parse_block_close()
    }

    /// Consumes any blank and comment lines, then the indentation of the next
    /// line in the block opened by a statement indented `opener_indentation`
    /// spaces, whose statements begin with one of `statement_starts` where the
    /// next line is one of them, and returns what comes next. Adds a diagnostic
    /// for each line that is not indented as deep as the block requires.
    #[inline]
    pub(crate) fn next_line_in_block(
        &mut self,
        opener_indentation: usize,
        statement_starts: &[&[u8]],
    ) -> ParseResult<LineInBlock> {
        let contents_indentation = opener_indentation + INDENTATION_WIDTH;
        loop {
            if self.scanner.is_at_end() {
                return Ok(LineInBlock::Unclosed);
            }
            let line_start = self.scanner.position;
            let Some(indentation) = self.start_line(contents_indentation)? else {
                continue;
            };
            if self.scanner.next_byte_is(CLOSE_BRACE) {
                self.check_indentation(line_start, opener_indentation, indentation)?;
                return Ok(LineInBlock::Close);
            }
            // A line of an outer block follows the block's lines without the
            // block's `}` between them.
            if indentation < contents_indentation && !self.begins_statement(statement_starts) {
                return Ok(LineInBlock::Unclosed);
            }
            self.check_indentation(line_start, contents_indentation, indentation)?;
            return Ok(LineInBlock::Statement);
        }
    }

    /// Adds a diagnostic if the line at `line_start` is indented `actual`
    /// spaces instead of `expected`.
    #[inline(always)]
    pub(crate) fn check_indentation(
        &mut self,
        line_start: Position,
        expected: usize,
        actual: usize,
    ) -> PyResult<()> {
        if actual != expected {
            self.incorrect_indentation(line_start, expected, actual)?;
        }
        Ok(())
    }

    /// Parses a terminator through the end of its line, and returns the
    /// position after its `.`, or `None` if there is no `.`.
    ///
    /// ```ebnf
    /// terminator = ".", ( newline | " ", { " " }, comment ) ;
    /// ```
    // Only the `.` and the line feed that almost always follows it are inlined
    // into callers; everything else is in functions they share.
    #[inline(always)]
    pub(crate) fn parse_terminator(&mut self) -> ParseResult<Option<Position>> {
        let terminator = self.scanner.position;
        if !self.scanner.consume_byte(TERMINATOR) {
            return Ok(None);
        }
        let end = self.scanner.position;
        if !self.scanner.consume_line_feed() && !self.scanner.is_at_end() {
            self.end_terminator_line_not_at_line_feed(terminator, end)?;
        }
        Ok(Some(end))
    }

    /// Parses the rest of the line after the `.` of the terminator at
    /// `terminator`, where `end` is the position after the `.` and no line feed
    /// follows it.
    #[inline(never)]
    fn end_terminator_line_not_at_line_feed(
        &mut self,
        terminator: Position,
        end: Position,
    ) -> ParseResult<()> {
        // A comment follows the `.` without a space between them.
        if self.scanner.next_byte_is(COMMENT_START) {
            return Err(self.errors.missing_space_before_comment(terminator, end));
        }
        // Something other than a comment follows the `.`.
        if !self.end_line_not_at_line_feed()? {
            if let Some(error) = self.disallowed_character_ahead(self.scanner.next_space_count()) {
                return Err(error);
            }
            return Err(self.errors.missing_newline_after_terminator(end, end));
        }
        Ok(())
    }

    /// Consumes the line if it is blank or a comment, adding a diagnostic for
    /// a comment that is not indented `expected_comment_indentation` spaces,
    /// and returns `None`. Otherwise consumes the line's indentation and
    /// returns its width.
    // Every line starts with this scan, so it is inlined into each caller.
    #[inline(always)]
    pub(crate) fn start_line(
        &mut self,
        expected_comment_indentation: usize,
    ) -> ParseResult<Option<usize>> {
        let line_start = self.scanner.position;
        match self.scanner.scan_line_end() {
            LineEnd::EndOrAsciiComment { length: 0, .. } => {
                self.scanner.consume_line_feed();
            }
            LineEnd::EndOrAsciiComment {
                length,
                leading_space_count,
            } => {
                self.consume_end_or_ascii_comment(length);
                self.check_indentation(
                    line_start,
                    expected_comment_indentation,
                    leading_space_count,
                )?;
            }
            LineEnd::Text {
                leading_space_count,
            } => {
                self.scanner.consume_bytes(leading_space_count);
                return Ok(Some(leading_space_count));
            }
            // The only unusual line that does not end in an error is a comment.
            LineEnd::Unusual {
                leading_space_count,
                length,
            } => {
                self.end_unusual_line(leading_space_count, length)?;
                self.check_indentation(
                    line_start,
                    expected_comment_indentation,
                    leading_space_count,
                )?;
            }
        }
        Ok(None)
    }

    /// Consumes the rest of the line after the brace at `brace`, where `end` is
    /// the position after it, including its line feed, if it is empty or a
    /// comment, and returns whether it did. At the end of the source, the line
    /// has no line feed.
    ///
    /// ```ebnf
    /// newline | " ", { " " }, comment
    /// ```
    // Most braces end their line, which needs no vector scan, so the vector
    // scan is the only part not inlined into callers.
    #[inline(always)]
    fn end_line_after_brace(&mut self, brace: Position, end: Position) -> ParseResult<bool> {
        if self.scanner.consume_line_feed() || self.scanner.is_at_end() {
            return Ok(true);
        }
        // A comment follows the brace without a space between them.
        if self.scanner.next_byte_is(COMMENT_START) {
            return Err(self
                .errors
                .missing_space_before_comment_after_brace(brace, end));
        }
        self.end_line_not_at_line_feed()
    }

    /// Consumes the rest of the line, including its line feed, if it is empty
    /// or a comment, and returns whether it did. A line feed does not come
    /// next.
    #[inline(never)]
    fn end_line_not_at_line_feed(&mut self) -> ParseResult<bool> {
        match self.scanner.scan_line_end() {
            LineEnd::EndOrAsciiComment { length, .. } => {
                self.consume_end_or_ascii_comment(length);
                Ok(true)
            }
            LineEnd::Text { .. } => Ok(false),
            LineEnd::Unusual {
                leading_space_count,
                length,
            } => {
                self.end_unusual_line(leading_space_count, length)?;
                Ok(true)
            }
        }
    }

    #[inline]
    fn consume_end_or_ascii_comment(&mut self, length: usize) {
        self.scanner.consume_bytes(length);
        self.scanner.consume_line_feed();
    }

    /// Consumes the rest of a line, `length` bytes and then its line feed,
    /// that `vector_scan::line_end` finds unusual after `leading_space_count`
    /// spaces.
    // A comment that is not printable ASCII comes here, which is common in
    // code written in languages other than English, so this is not cold.
    #[inline(never)]
    fn end_unusual_line(&mut self, leading_space_count: usize, length: usize) -> ParseResult<()> {
        let start = self.scanner.position;
        self.scanner.consume_bytes(leading_space_count);
        // The line ends with spaces.
        if !self.scanner.next_byte_is(COMMENT_START) {
            return Err(self.errors.trailing_whitespace_error(start, start, " "));
        }
        let comment_start = self.scanner.position;
        let comment = self.scanner.consume_text(length - leading_space_count);
        // The comment has a character that comments do not allow.
        if let Some(error) = characters::first_disallowed_character(
            &self.errors,
            comment_start,
            comment.bytes,
            TextKind::Comment,
        ) {
            return Err(error);
        }
        // The `#` is not a space, so `rposition` always finds a byte.
        let content_length = comment
            .bytes
            .iter()
            .rposition(|&byte| byte != SPACE)
            .map_or(0, |index| index + 1);
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
}

// The functions that only run on an error path.
impl<'py, 'source> Parser<'py, 'source> {
    /// Returns the error for a block whose ` {` is missing at the scanner's
    /// position.
    #[cold]
    #[inline(never)]
    fn missing_block_open(&self) -> ParseError {
        if let Some(error) =
            self.disallowed_character_ahead(self.scanner.matching_prefix_length(BLOCK_OPEN))
        {
            return error;
        }
        let missing = self.scanner.position;
        let spaces = self.scanner.next_space_count();
        // More than one space comes before the `{`.
        if spaces > 1 && self.scanner.rest_of_line().bytes.get(spaces) == Some(&OPEN_BRACE) {
            let last_space = Position {
                line: missing.line,
                column: missing.column + spaces - 1,
            };
            return self.errors.extra_whitespace(missing, last_space);
        }
        // The `{` has no space before it.
        if self.scanner.next_byte_is(OPEN_BRACE) {
            return self
                .errors
                .missing_whitespace_before_brace(missing, missing);
        }
        self.errors.missing_open_brace(missing, missing)
    }

    /// Returns the error for text after the `{` that opens a block, which the
    /// scanner is at.
    #[cold]
    #[inline(never)]
    fn text_after_block_open(&self) -> ParseError {
        if let Some(error) = self.disallowed_character_ahead(self.scanner.next_space_count()) {
            return error;
        }
        let text = self.scanner.position;
        // The block closes on the line that opens it.
        if self.scanner.next_byte_is(CLOSE_BRACE) {
            return self.errors.empty_block(text, text);
        }
        self.errors.missing_newline_after_open_brace(text, text)
    }

    /// Returns the error for text after the `}` that closes a block, where
    /// `end`, the position after the `}`, is the scanner's position.
    #[cold]
    #[inline(never)]
    fn text_after_block_close(&self, end: Position) -> ParseError {
        if let Some(error) = self.disallowed_character_ahead(self.scanner.next_space_count()) {
            return error;
        }
        self.errors.missing_newline_after_close_brace(end, end)
    }

    /// Returns whether the text at the scanner's position begins a statement
    /// that begins with one of `statement_starts`.
    #[cold]
    #[inline(never)]
    fn begins_statement(&self, statement_starts: &[&[u8]]) -> bool {
        statement_starts
            .iter()
            .any(|start| self.scanner.next_bytes_are(start))
    }

    #[cold]
    #[inline(never)]
    fn incorrect_indentation(
        &mut self,
        line_start: Position,
        expected: usize,
        actual: usize,
    ) -> PyResult<()> {
        // The location covers the indentation, or the first character if there
        // is none.
        let end = Position {
            line: line_start.line,
            column: actual.max(1),
        };
        self.diagnostics
            .incorrect_indentation_diagnostic(line_start, end, expected, actual)
    }

    /// Returns the error for a statement whose terminator is missing at the
    /// scanner's position.
    #[cold]
    #[inline(never)]
    pub(crate) fn missing_terminator(&self) -> ParseError {
        if let Some(error) = self.disallowed_character_ahead(0) {
            return error;
        }
        let missing = self.scanner.position;
        self.errors.missing_terminator(missing, missing)
    }
}
