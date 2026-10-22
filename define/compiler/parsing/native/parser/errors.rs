//! The error helpers that the error paths of every construct share.

use crate::characters;
use crate::parse_error::ParseError;
use crate::parser::Parser;
use crate::scanner::Position;
use terminals::SPACE;

// The functions that only run on an error path.
impl<'py, 'source> Parser<'py, 'source> {
    /// Returns the error for the spaces where `line`, the rest of the line at
    /// the scanner's position, which does not start with `words`, ASCII words
    /// separated by single spaces, stops matching them, if it has extra spaces
    /// before a word there or is missing the space before one.
    #[cold]
    fn misspaced_words(&self, line: &[u8], words: &[u8]) -> Option<ParseError> {
        let matching = line
            .iter()
            .zip(words)
            .take_while(|(byte, expected)| byte == expected)
            .count();
        // Every byte the line matches is ASCII, so each is one column.
        let start = self.scanner.position;
        if words.get(matching) == Some(&SPACE) {
            let next_word = words[matching + 1..]
                .split(|&byte| byte == SPACE)
                .next()
                .unwrap_or_default();
            // The next word follows the one before it without the space
            // between them. A different word that starts like the one before
            // it is not followed by the next word.
            if !line[matching..].starts_with(next_word) {
                return None;
            }
            let word_start = Position {
                line: start.line,
                column: start.column + matching,
            };
            let word_end = word_start.after_ascii(next_word).previous_column();
            return Some(self.errors.missing_whitespace(word_start, word_end));
        }
        if matching == 0 || words[matching - 1] != SPACE {
            return None;
        }
        let first = matching - 1;
        let spaces = line[first..]
            .iter()
            .take_while(|&&byte| byte == SPACE)
            .count();
        // Spaces that end the line are where an unfinished line stops, and
        // one space is the separator before a different word.
        if spaces == 1 || first + spaces == line.len() {
            return None;
        }
        let spaces_start = Position {
            line: start.line,
            column: start.column + first,
        };
        let spaces_end = Position {
            line: start.line,
            column: start.column + first + spaces - 1,
        };
        Some(self.errors.extra_whitespace(spaces_start, spaces_end))
    }

    /// Returns the error for the spaces where the line at the scanner's
    /// position stops matching the first of `phrases` that it has extra spaces
    /// in or is missing a space in.
    #[cold]
    pub(crate) fn misspaced_words_in_any(&self, phrases: &[&[u8]]) -> Option<ParseError> {
        let line = self.scanner.rest_of_line().bytes;
        phrases
            .iter()
            .find_map(|phrase| self.misspaced_words(line, phrase))
    }

    /// Returns the error for a block that ends without its `}`, which a line
    /// from `start` up to `block_open_end`, the position after its `{`, opens.
    #[cold]
    #[inline(never)]
    pub(crate) fn missing_close_brace(
        &self,
        start: Position,
        block_open_end: Position,
    ) -> ParseError {
        self.errors
            .missing_close_brace(start, block_open_end.previous_column())
    }

    /// Returns the error for a statement at the scanner's position where a
    /// block's `}` belongs.
    #[cold]
    #[inline(never)]
    pub(crate) fn statement_instead_of_close_brace(&self) -> ParseError {
        if let Some(error) = self.disallowed_character_ahead(0) {
            return error;
        }
        let start = self.scanner.position;
        self.errors.missing_close_brace(start, self.end_of_line())
    }

    /// Returns the error for the character `offset` bytes, which are ASCII,
    /// past the scanner's position, where the syntax there went wrong, if no
    /// syntax may have it.
    #[cold]
    #[inline(never)]
    pub(crate) fn disallowed_character_ahead(&self, offset: usize) -> Option<ParseError> {
        characters::disallowed_character_ahead(&self.errors, &self.scanner, offset)
    }

    /// Returns the error for the character where the line at the scanner's
    /// position stops matching `expected`, if no syntax may have it.
    #[cold]
    pub(crate) fn disallowed_character_after(&self, expected: &[u8]) -> Option<ParseError> {
        self.disallowed_character_ahead(self.scanner.matching_prefix_length(expected))
    }

    /// Returns the error for the character where the line at the scanner's
    /// position stops matching the one of `phrases` that it matches the most
    /// of, if no syntax may have it.
    #[cold]
    pub(crate) fn disallowed_character_after_any(&self, phrases: &[&[u8]]) -> Option<ParseError> {
        let matched = phrases
            .iter()
            .map(|phrase| self.scanner.matching_prefix_length(phrase))
            .max()
            .unwrap_or(0);
        self.disallowed_character_ahead(matched)
    }

    /// Returns the position of the last character on the line before its line
    /// feed, which must not be empty from the scanner's position.
    #[cold]
    pub(crate) fn end_of_line(&self) -> Position {
        self.scanner
            .position
            .after(self.scanner.rest_of_line())
            .previous_column()
    }
}
