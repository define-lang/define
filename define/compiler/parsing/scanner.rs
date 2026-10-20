//! Moving through the source and tracking positions in it.

use std::slice::SliceIndex;
use vector_scan::LINE_FEED;

/// Text from the source, which is UTF-8 if the source is valid, but
/// usually is just ASCII.
#[derive(Clone, Copy)]
pub struct SourceText<'source> {
    pub bytes: &'source [u8],
    /// False when the text may contain non-ASCII bytes.
    pub is_known_ascii: bool,
}

impl<'source> SourceText<'source> {
    pub fn character_count(self) -> usize {
        if self.is_known_ascii {
            self.bytes.len()
        } else {
            vector_scan::character_count(self.bytes)
        }
    }

    /// Returns the text in the byte `range`, which must start and end on
    /// character boundaries.
    pub fn slice(self, range: impl SliceIndex<[u8], Output = [u8]>) -> Self {
        Self {
            bytes: &self.bytes[range],
            is_known_ascii: self.is_known_ascii,
        }
    }

    /// Splits the text at each occurrence of the ASCII `separator`.
    pub fn split(self, separator: u8) -> impl Iterator<Item = Self> {
        self.bytes
            .split(move |&byte| byte == separator)
            .map(move |bytes| Self {
                bytes,
                is_known_ascii: self.is_known_ascii,
            })
    }
}

/// A point in the source, as a 1-based line and a 1-based column counted in
/// characters.
#[derive(Clone, Copy)]
pub struct Position {
    pub line: usize,
    pub column: usize,
}

impl Position {
    /// Returns the position after `text`, which must not contain a line feed.
    pub fn after(self, text: SourceText) -> Self {
        Self {
            line: self.line,
            column: self.column + text.character_count(),
        }
    }

    // Keywords and punctuation are ASCII by construction, so they need no
    // `SourceText` (otherwise we would have to construct one pointlessly).
    /// Returns the position after the ASCII `text`, which must not contain a
    /// line feed.
    pub const fn after_ascii(self, text: &[u8]) -> Self {
        Self {
            line: self.line,
            column: self.column + text.len(),
        }
    }

    /// Returns the position one column later on the same line.
    pub const fn next_column(self) -> Self {
        Self {
            line: self.line,
            column: self.column + 1,
        }
    }
}

pub struct Scanner<'source> {
    /// The source that has not been consumed yet.
    rest: &'source [u8],
    pub position: Position,
}

impl<'source> Scanner<'source> {
    pub const fn new(source: &'source [u8]) -> Self {
        Self {
            rest: source,
            position: Position { line: 1, column: 1 },
        }
    }

    pub const fn is_at_end(&self) -> bool {
        self.rest.is_empty()
    }

    pub fn next_bytes_are(&self, expected: &[u8]) -> bool {
        self.rest.starts_with(expected)
    }

    /// Whether the next byte is `expected`.
    pub const fn next_byte_is(&self, expected: u8) -> bool {
        matches!(self.rest.first(), Some(&byte) if byte == expected)
    }

    /// Consumes `expected` if the remaining text starts with it. `expected`
    /// must be ASCII without a line feed.
    pub fn consume(&mut self, expected: &[u8]) -> bool {
        let Some(rest) = self.rest.strip_prefix(expected) else {
            return false;
        };
        self.rest = rest;
        self.position = self.position.after_ascii(expected);
        true
    }

    /// Consumes `expected` if it is the next byte. `expected` must be ASCII and
    /// not a line feed.
    pub fn consume_byte(&mut self, expected: u8) -> bool {
        let Some((&byte, rest)) = self.rest.split_first() else {
            return false;
        };
        if byte != expected {
            return false;
        }
        self.rest = rest;
        self.position.column += 1;
        true
    }

    pub fn consume_line_feed(&mut self) -> bool {
        let Some(rest) = self.rest.strip_prefix(&[LINE_FEED]) else {
            return false;
        };
        self.rest = rest;
        self.position = Position {
            line: self.position.line + 1,
            column: 1,
        };
        true
    }

    /// Consumes the name content before the first `>` or line feed, or all of
    /// the remaining text if it contains neither, and returns it with what the
    /// scan found in it.
    pub fn consume_name_content(&mut self) -> (SourceText<'source>, vector_scan::NameContent) {
        let scanned = vector_scan::name_content(self.rest);
        let (bytes, rest) = self.rest.split_at(scanned.length);
        let text = SourceText {
            bytes,
            is_known_ascii: scanned.is_ascii,
        };
        self.rest = rest;
        self.position.column += scanned.character_count;
        (text, scanned)
    }
}
