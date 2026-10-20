//! The structure of lines: indentation, comments, line ends, terminators, and
//! the lines that open and close blocks.

use crate::parse_error::{ParseError, ParseResult};
use crate::parser_diagnostics::ParserDiagnostics;
use crate::scanner::{Position, Scanner};
use crate::syntax_errors::SyntaxErrors;
use vector_scan::{COMMENT_START, LINE_FEED, LineEnd, SPACE};

pub const OPEN_BRACE: u8 = b'{';
const CLOSE_BRACE: u8 = b'}';
/// What the grammar's `block_open` starts with.
pub const BLOCK_OPEN: &[u8] = &[SPACE, OPEN_BRACE];
pub const TERMINATOR: u8 = b'.';
/// How much deeper than the statement that opens a block each line in the
/// block is indented.
const INDENTATION_WIDTH: usize = 4;

pub struct Lines<'parser, 'py, 'source> {
    scanner: &'parser mut Scanner<'source>,
    errors: &'parser SyntaxErrors<'py>,
    diagnostics: &'parser mut ParserDiagnostics<'py>,
}

/// What comes next in a block, after any blank and comment lines.
pub enum LineInBlock {
    /// The block's `}`.
    Close,
    /// A statement, after `indentation` spaces.
    Statement { indentation: usize },
    /// The end of the source, before the block's `}`.
    EndOfSource,
}

impl<'parser, 'py, 'source> Lines<'parser, 'py, 'source> {
    pub const fn new(
        scanner: &'parser mut Scanner<'source>,
        errors: &'parser SyntaxErrors<'py>,
        diagnostics: &'parser mut ParserDiagnostics<'py>,
    ) -> Self {
        Self {
            scanner,
            errors,
            diagnostics,
        }
    }

    /// Parses the ` {` that opens a block, through the end of its line, and
    /// returns the position after the `{`.
    ///
    /// ```ebnf
    /// block_open = " ", "{", newline ;
    /// ```
    #[inline]
    pub fn parse_block_open(&mut self) -> ParseResult<Position> {
        // There is no ` {`.
        if !self.scanner.consume(BLOCK_OPEN) {
            return Err(self.missing_block_open());
        }
        let end = self.scanner.position;
        // Something other than a line feed or a comment follows the `{`.
        if !self.end_line()? {
            return Err(self.text_after_block_open());
        }
        Ok(end)
    }

    /// Returns the error for a block whose ` {` is missing at the scanner's
    /// position.
    #[cold]
    #[inline(never)]
    fn missing_block_open(&self) -> ParseError {
        let missing = self.scanner.position;
        // The line ends where the ` {` belongs.
        if self.scanner.next_byte_is(LINE_FEED) {
            return self.errors.missing_open_brace(missing, missing);
        }
        ParseError::not_yet_supported(missing, "anything but ` {` here")
    }

    /// Returns the error for text after the `{` that opens a block, which the
    /// scanner is at.
    #[cold]
    #[inline(never)]
    fn text_after_block_open(&self) -> ParseError {
        let text = self.scanner.position;
        // The block closes on the line that opens it.
        if self.scanner.next_byte_is(CLOSE_BRACE) {
            return self.errors.empty_block(text, text);
        }
        ParseError::not_yet_supported(text, "anything but a line end after `{`")
    }

    /// Parses the `}` that closes a block, which `next_line_in_block` found
    /// next, through the end of its line, and returns the position after the
    /// `}`.
    ///
    /// ```ebnf
    /// block_close = "}", newline ;
    /// ```
    #[inline]
    pub fn parse_block_close(&mut self) -> ParseResult<Position> {
        self.scanner.consume_bytes(1);
        let end = self.scanner.position;
        // Something other than a line feed or a comment follows the `}`.
        if !self.end_line()? {
            return Err(self.errors.missing_newline_after_close_brace(end, end));
        }
        Ok(end)
    }

    /// Consumes any blank and comment lines, then the indentation of the next
    /// line in the block opened by a statement indented `opener_indentation`
    /// spaces, and returns what comes next. Adds a diagnostic for each line
    /// that is not indented as deep as the block requires.
    #[inline]
    pub fn next_line_in_block(&mut self, opener_indentation: usize) -> ParseResult<LineInBlock> {
        let contents_indentation = opener_indentation + INDENTATION_WIDTH;
        loop {
            if self.scanner.is_at_end() {
                return Ok(LineInBlock::EndOfSource);
            }
            let line_start = self.scanner.position;
            let Some(indentation) = self.start_line(contents_indentation)? else {
                continue;
            };
            if self.scanner.next_byte_is(CLOSE_BRACE) {
                self.check_indentation(line_start, opener_indentation, indentation)?;
                return Ok(LineInBlock::Close);
            }
            self.check_indentation(line_start, contents_indentation, indentation)?;
            return Ok(LineInBlock::Statement { indentation });
        }
    }

    /// Adds a diagnostic if the line at `line_start` is indented `actual`
    /// spaces instead of `expected`.
    #[inline(always)]
    fn check_indentation(
        &mut self,
        line_start: Position,
        expected: usize,
        actual: usize,
    ) -> ParseResult<()> {
        if actual != expected {
            self.incorrect_indentation(line_start, expected, actual)?;
        }
        Ok(())
    }

    #[cold]
    #[inline(never)]
    fn incorrect_indentation(
        &mut self,
        line_start: Position,
        expected: usize,
        actual: usize,
    ) -> ParseResult<()> {
        // The location covers the indentation, or the first character if there
        // is none.
        let end = Position {
            line: line_start.line,
            column: actual.max(1),
        };
        Ok(self
            .diagnostics
            .incorrect_indentation_diagnostic(line_start, end, expected, actual)?)
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
    pub fn parse_terminator(&mut self) -> ParseResult<Option<Position>> {
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

    /// Returns the error for a statement whose terminator is missing at the
    /// scanner's position.
    #[cold]
    #[inline(never)]
    pub fn missing_terminator(&self) -> ParseError {
        let missing = self.scanner.position;
        // The line ends where the `.` belongs.
        if self.scanner.next_byte_is(LINE_FEED) {
            return self.errors.missing_terminator(missing, missing);
        }
        ParseError::not_yet_supported(missing, "anything but a terminator here")
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
    pub fn start_line(
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
            } => {
                self.end_unusual_line(leading_space_count)?;
                self.check_indentation(
                    line_start,
                    expected_comment_indentation,
                    leading_space_count,
                )?;
            }
        }
        Ok(None)
    }

    /// Consumes the rest of the line, including its line feed, if it is empty
    /// or a comment, and returns whether it did. At the end of the source, the
    /// line has no line feed.
    ///
    /// ```ebnf
    /// newline | comment
    /// ```
    // Most statements end with a line feed right after them, which needs no
    // vector scan, so only that check is inlined into callers.
    #[inline(always)]
    pub fn end_line(&mut self) -> ParseResult<bool> {
        if self.scanner.consume_line_feed() || self.scanner.is_at_end() {
            return Ok(true);
        }
        self.end_line_not_at_line_feed()
    }

    /// Does what `end_line` does, where a line feed does not come next.
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
            } => {
                self.end_unusual_line(leading_space_count)?;
                Ok(true)
            }
        }
    }

    #[inline]
    fn consume_end_or_ascii_comment(&mut self, length: usize) {
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
            return Err(ParseError::not_yet_supported(
                comment_start,
                "invalid UTF-8 in comments",
            ));
        };
        // TODO: Check comments for invisible characters here, instead of in
        // the Python check that runs before this parser. Every comment that is
        // not printable ASCII comes here, so this loop sees every character
        // that could be invisible.
        if characters.chars().any(char::is_control) {
            return Err(ParseError::not_yet_supported(
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
}
