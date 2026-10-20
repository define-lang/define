//! The structure of lines: indentation, comments, line ends, terminators, and
//! the lines that open and close blocks.

use crate::parse_error::{ParseError, ParseResult};
use crate::scanner::{Position, Scanner};
use crate::syntax_errors::SyntaxErrors;
use vector_scan::{COMMENT_START, LINE_FEED, LineEnd};

pub const BLOCK_OPEN: &[u8] = b" {";
const BLOCK_CLOSE: u8 = b'}';
const TERMINATOR: u8 = b'.';

pub struct Lines<'parser, 'py, 'source> {
    scanner: &'parser mut Scanner<'source>,
    errors: &'parser SyntaxErrors<'py>,
}

impl<'parser, 'py, 'source> Lines<'parser, 'py, 'source> {
    pub const fn new(
        scanner: &'parser mut Scanner<'source>,
        errors: &'parser SyntaxErrors<'py>,
    ) -> Self {
        Self { scanner, errors }
    }

    /// Parses the ` {` that opens a block, through the end of its line.
    ///
    /// ```ebnf
    /// block_open = " ", "{", newline ;
    /// ```
    #[inline]
    pub fn parse_block_open(&mut self) -> ParseResult<()> {
        let start = self.scanner.position;
        if !self.scanner.consume(BLOCK_OPEN) || !self.end_line()? {
            return Err(ParseError::not_yet_supported(
                start,
                "anything but ` {` here",
            ));
        }
        Ok(())
    }

    /// Parses the `}` that closes a block, after its indentation, through the
    /// end of its line, and returns the position after the `}`.
    ///
    /// ```ebnf
    /// block_close = "}", newline ;
    /// ```
    #[inline]
    pub fn parse_block_close(&mut self) -> ParseResult<Position> {
        let start = self.scanner.position;
        if !self.scanner.consume_byte(BLOCK_CLOSE) {
            return Err(ParseError::not_yet_supported(
                start,
                "anything but `}` here",
            ));
        }
        let end = self.scanner.position;
        if !self.end_line()? {
            return Err(ParseError::not_yet_supported(end, "anything after `}`"));
        }
        Ok(end)
    }

    /// Consumes any blank and comment lines, then the indentation of the next
    /// line in a block, and returns the indentation's width.
    #[inline]
    pub fn next_line_in_block(&mut self) -> ParseResult<usize> {
        loop {
            if self.scanner.is_at_end() {
                return Err(ParseError::not_yet_supported(
                    self.scanner.position,
                    "a block without its `}`",
                ));
            }
            if let Some(indentation) = self.start_line()? {
                return Ok(indentation);
            }
        }
    }

    /// Parses a terminator through the end of its line, and returns the
    /// position after its `.`.
    ///
    /// ```ebnf
    /// terminator = ".", ( newline | " ", { " " }, comment ) ;
    /// ```
    // Only the `.` and the line feed that almost always follows it are inlined
    // into callers; everything else is in functions they share.
    #[inline(always)]
    pub fn parse_terminator(&mut self) -> ParseResult<Position> {
        let terminator = self.scanner.position;
        // There is no `.`.
        if !self.scanner.consume_byte(TERMINATOR) {
            return Err(self.missing_terminator(terminator));
        }
        let end = self.scanner.position;
        if !self.scanner.consume_line_feed() && !self.scanner.is_at_end() {
            self.end_terminator_line_not_at_line_feed(terminator, end)?;
        }
        Ok(end)
    }

    /// Returns the error for a terminator missing at `terminator`.
    #[cold]
    #[inline(never)]
    fn missing_terminator(&self, terminator: Position) -> ParseError {
        // The line ends where the `.` belongs.
        if self.scanner.next_byte_is(LINE_FEED) {
            return self
                .errors
                .missing_terminator_or_brace(terminator, terminator);
        }
        ParseError::not_yet_supported(terminator, "anything but a terminator here")
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

    /// Consumes the line if it is blank or a comment, and returns `None`.
    /// Otherwise consumes the line's indentation and returns its width.
    // Every line starts with this scan, so it is inlined into each caller.
    #[inline(always)]
    pub fn start_line(&mut self) -> ParseResult<Option<usize>> {
        match self.scanner.scan_line_end() {
            LineEnd::Ordinary { length } => {
                self.consume_ordinary_line_end(length);
                Ok(None)
            }
            LineEnd::Text {
                leading_space_count,
            } => {
                self.scanner.consume_bytes(leading_space_count);
                Ok(Some(leading_space_count))
            }
            LineEnd::Unusual {
                leading_space_count,
            } => {
                self.end_unusual_line(leading_space_count)?;
                Ok(None)
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

    #[inline]
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
