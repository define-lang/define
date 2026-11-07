//! Moving through the source and tracking positions in it.

use source_rendering::Position;

const LINE_FEED: u8 = b'\n';

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
            self.position.column += 1;
        }
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
        self.last_consumed = Position {
            line: self.position.line,
            column: self.position.column + length - 1,
        };
        self.position.column += length;
        &self.source[start..self.offset]
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
