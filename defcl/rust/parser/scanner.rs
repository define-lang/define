//! Moving through the source and tracking positions in it.

use source_characters::{DisallowedReason, Neighbors, TextKind, disallowed_reason};
use source_rendering::{Position, SourceLocation};

const LINE_FEED: u8 = b'\n';

/// Why `character` is not allowed outside strings and comments, if it is an
/// invisible character.
pub fn invisible_syntax_reason(character: char) -> Option<DisallowedReason> {
    // No invisible character is allowed there, not even a joiner or variation
    // selector between visible characters, which is the rule for string
    // content with nothing next to the character.
    disallowed_reason(character, TextKind::LiteralContent, Neighbors::NONE)
}

/// Whether `byte` continues a UTF-8 character instead of starting one.
const fn is_continuation_byte(byte: u8) -> bool {
    byte & 0b1100_0000 == 0b1000_0000
}

#[derive(Clone, Copy)]
pub struct Scanner<'source> {
    source: &'source str,
    /// The byte offset of the first byte that has not been consumed.
    offset: usize,
    /// The position of the first character that has not been consumed.
    position: Position,
    /// The position of the last character consumed, or the first position if
    /// nothing has been consumed.
    last_consumed: Position,
}

impl<'source> Scanner<'source> {
    pub const fn new(source: &'source str) -> Self {
        let start = Position { line: 1, column: 1 };
        Self {
            source,
            offset: 0,
            position: start,
            last_consumed: start,
        }
    }

    pub const fn position(&self) -> Position {
        self.position
    }

    pub const fn last_consumed(&self) -> Position {
        self.last_consumed
    }

    pub const fn is_at_end(&self) -> bool {
        self.offset == self.source.len()
    }

    /// The next byte, which is the first byte of the next character.
    pub fn peek(&self) -> Option<u8> {
        self.source.as_bytes().get(self.offset).copied()
    }

    /// The character that starts at the next byte.
    pub fn peek_character(&self) -> Option<char> {
        self.source[self.offset..].chars().next()
    }

    /// Consumes one byte, which must not be past the end of the source.
    pub const fn advance(&mut self) {
        let byte = self.source.as_bytes()[self.offset];
        self.offset += 1;
        if is_continuation_byte(byte) {
            return;
        }
        self.last_consumed = self.position;
        if byte == LINE_FEED {
            self.position = Position {
                line: self.position.line + 1,
                column: 1,
            };
        } else {
            self.position = self.position.next_column();
        }
    }

    /// Consumes everything up to the next line feed or the end of the source,
    /// and returns it.
    pub fn consume_to_line_end(&mut self) -> &'source str {
        let rest = &self.source[self.offset..];
        let length = rest.find('\n').unwrap_or(rest.len());
        let text = &rest[..length];
        // A column counts characters, so it skips the bytes that continue
        // one. Counting every byte without stopping early lets the compiler
        // count many at once.
        let characters = text.bytes().fold(0, |count, byte| {
            count + usize::from(!is_continuation_byte(byte))
        });
        if characters > 0 {
            self.last_consumed = self.position.columns_later(characters - 1);
            self.position = self.position.columns_later(characters);
        }
        self.offset += length;
        text
    }

    /// Consumes `character`, which must be the next character.
    pub fn advance_character(&mut self, character: char) {
        for _ in 0..character.len_utf8() {
            self.advance();
        }
    }

    /// Consumes whitespace, comments and invisible characters, and returns
    /// whether there were any.
    ///
    /// ```ebnf
    /// COMMENT    = "#", { char - newline }, [ newline ] ;
    /// WHITESPACE = " " | newline ;
    /// ```
    #[inline(always)]
    pub fn skip_whitespace(&mut self) -> bool {
        let start = self.offset;
        loop {
            match self.peek() {
                Some(b' ' | b'\n') => self.advance(),
                Some(b'#') => self.skip_comment(),
                _ => {
                    let Some((character, _)) = self.peek_invisible_character() else {
                        return self.offset != start;
                    };
                    self.advance_character(character);
                }
            }
        }
    }

    /// Consumes whitespace, comments and invisible characters as
    /// `skip_whitespace` does, and returns the location of the comments among
    /// them, from the `#` of the first to the end of the last, if there are
    /// any.
    #[inline(always)]
    pub fn skip_whitespace_locating_comments(&mut self) -> Option<SourceLocation> {
        let mut comments: Option<SourceLocation> = None;
        loop {
            match self.peek() {
                Some(b' ' | b'\n') => self.advance(),
                Some(b'#') => {
                    let start = self.position;
                    self.skip_comment();
                    comments = Some(SourceLocation {
                        start: comments.map_or(start, |comments| comments.start),
                        end: self.last_consumed,
                    });
                }
                _ => {
                    let Some((character, _)) = self.peek_invisible_character() else {
                        return comments;
                    };
                    self.advance_character(character);
                }
            }
        }
    }

    /// Consumes a comment up to its line feed.
    fn skip_comment(&mut self) {
        let _: &str = self.consume_to_line_end();
    }

    /// The invisible character at the scanner's position outside strings and
    /// comments, other than a line feed, and why it is not allowed, if there
    /// is one. The parse skips such a character as if it were not there.
    #[inline(always)]
    pub fn peek_invisible_character(&self) -> Option<(char, DisallowedReason)> {
        let byte = self.peek()?;
        // Printable ASCII is never invisible, which keeps the decoding off the
        // path of nearly every byte.
        if matches!(byte, b' '..=b'~' | b'\n') {
            return None;
        }
        self.decode_invisible_character()
    }

    /// `peek_invisible_character` for a character that is not printable
    /// ASCII.
    #[cold]
    #[inline(never)]
    fn decode_invisible_character(&self) -> Option<(char, DisallowedReason)> {
        let character = self.peek_character()?;
        let reason = invisible_syntax_reason(character)?;
        Some((character, reason))
    }

    /// Consumes `expected` if it is the next byte.
    pub fn consume_byte(&mut self, expected: u8) -> bool {
        if self.peek() != Some(expected) {
            return false;
        }
        self.advance();
        true
    }

    /// Consumes the bytes that `is_included` accepts, which must be ASCII
    /// other than a line feed, up to the first byte that it does not accept,
    /// and returns them. `is_included` must accept the next byte.
    pub fn consume_while(&mut self, is_included: impl Fn(u8) -> bool) -> &'source str {
        let start = self.offset;
        let length = self.source.as_bytes()[start..]
            .iter()
            .take_while(|&&byte| is_included(byte))
            .count();
        self.offset += length;
        self.last_consumed = self.position.columns_later(length - 1);
        self.position = self.position.columns_later(length);
        &self.source[start..self.offset]
    }

    /// Consumes the spaces at the scanner's position, and returns how many
    /// there were.
    pub fn consume_spaces(&mut self) -> usize {
        let count = self.source.as_bytes()[self.offset..]
            .iter()
            .take_while(|&&byte| byte == b' ')
            .count();
        if count > 0 {
            self.offset += count;
            self.last_consumed = self.position.columns_later(count - 1);
            self.position = self.position.columns_later(count);
        }
        count
    }

    /// Consumes up to `limit` bytes that `is_included` accepts, which must be
    /// ASCII other than a line feed, and returns how many it consumed.
    pub fn consume_up_to(&mut self, limit: usize, is_included: impl Fn(u8) -> bool) -> usize {
        let mut count = 0;
        while count < limit && self.peek().is_some_and(&is_included) {
            self.advance();
            count += 1;
        }
        count
    }

    /// The source from the byte offset `start` up to the next byte.
    pub fn text_from(&self, start: usize) -> &'source str {
        &self.source[start..self.offset]
    }

    pub const fn offset(&self) -> usize {
        self.offset
    }
}
