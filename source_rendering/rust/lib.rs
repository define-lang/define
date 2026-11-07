//! How diagnostics show a location in a source file: a header that names its
//! line and column, then its source line with carets under the part that it
//! covers. The Define compiler and the Define Configuration Language share it.

mod source_lines;

pub use source_lines::SourceLines;

const CODE_INDENTATION: &str = "    ";

/// A point in a source file, as a 1-based line and a 1-based column counted in
/// characters.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Position {
    pub line: usize,
    pub column: usize,
}

/// The part of a source file that something, such as an error, covers: from
/// `start` through `end`, the position of the last character that it covers.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct SourceLocation {
    pub start: Position,
    pub end: Position,
}

impl SourceLocation {
    /// The location of the one character at `position`, or of the point
    /// where something belongs.
    #[must_use]
    pub const fn at(position: Position) -> Self {
        Self {
            start: position,
            end: position,
        }
    }

    /// The header `File "<file_path>", line N, column M`, or
    /// `line N, column M` with no `file_path`, then `source_line`, the line
    /// that the location starts on, with carets under the part that it covers.
    /// With no `source_line`, only the header.
    ///
    /// A location that continues onto later lines is underlined to the end of
    /// its first line. Characters that are not printable show as
    /// `escape_invisible` shows them, so that they cannot change what a
    /// terminal shows.
    #[must_use]
    pub fn render(self, source_line: Option<&str>, file_path: Option<&str>) -> String {
        let mut rendered = match file_path {
            Some(file_path) => format!(
                "File \"{file_path}\", line {}, column {}",
                self.start.line, self.start.column
            ),
            None => format!("line {}, column {}", self.start.line, self.start.column),
        };
        let Some(source_line) = source_line else {
            return rendered;
        };
        // Only our own indentation should show, not the source's, unless the
        // location is in that indentation.
        let mut indentation = source_line.len() - source_line.trim_start_matches(' ').len();
        if self.start.column - 1 < indentation {
            indentation = 0;
        }
        // Spaces are one byte each, so the indentation's length in bytes is
        // its length in characters.
        let code = &source_line[indentation..];
        let start = self.start.column - 1 - indentation;
        // The end is the location's last character. A location that
        // continues onto later lines has no end on this line.
        let end = (self.end.line == self.start.line).then(|| self.end.column - indentation);
        rendered.push('\n');
        if !code.is_empty() {
            rendered.push_str(CODE_INDENTATION);
        }
        // Escaped characters are wider, so the underline moves with them.
        let (start, end) = push_escaped(&mut rendered, code, start, end);
        rendered.push('\n');
        rendered.push_str(CODE_INDENTATION);
        rendered.extend(std::iter::repeat_n(' ', start));
        rendered.extend(std::iter::repeat_n('^', end.saturating_sub(start).max(1)));
        rendered
    }
}

/// `text`, with its characters that are not printable replaced by the escapes
/// that Rust's `char::escape_debug` writes, such as `\t`, `\0` and `\u{200b}`.
/// Backslashes and quotes stay as they are.
#[must_use]
pub fn escape_invisible(text: &str) -> String {
    let mut escaped = String::with_capacity(text.len());
    // Escaping the whole text needs no positions in it.
    let _: (usize, usize) = push_escaped(&mut escaped, text, 0, None);
    escaped
}

/// Pushes `code` onto `rendered`, with its characters that are not printable
/// escaped, and returns where the character indexes `start` and `end` of
/// `code` are in the escaped code. An index after the last character, or no
/// `end`, is the end of the escaped code.
fn push_escaped(
    rendered: &mut String,
    code: &str,
    start: usize,
    end: Option<usize>,
) -> (usize, usize) {
    let mut width = 0;
    let mut escaped_start = None;
    let mut escaped_end = None;
    for (index, character) in code.chars().enumerate() {
        if index == start {
            escaped_start = Some(width);
        }
        if end == Some(index) {
            escaped_end = Some(width);
        }
        // Nearly all source text is printable ASCII, which needs no escaping,
        // so most characters skip building the string that escaping needs.
        // This also keeps backslashes and quotes, which `escape_debug` escapes
        // although they are printable.
        if character == ' ' || character.is_ascii_graphic() {
            rendered.push(character);
            width += 1;
            continue;
        }
        // Other than backslashes and quotes, `str::escape_debug` escapes exactly
        // the characters that are not printable. It also escapes a combining
        // character that starts a string, so the character follows a space,
        // which it leaves as it is.
        let mut text = String::from(" ");
        text.push(character);
        for escaped in text.escape_debug().skip(1) {
            rendered.push(escaped);
            width += 1;
        }
    }
    (escaped_start.unwrap_or(width), escaped_end.unwrap_or(width))
}

#[cfg(test)]
mod tests {
    use super::{Position, SourceLocation, escape_invisible};
    use googletest::prelude::*;

    const fn location(
        line: usize,
        column: usize,
        end_line: usize,
        end_column: usize,
    ) -> SourceLocation {
        SourceLocation {
            start: Position { line, column },
            end: Position {
                line: end_line,
                column: end_column,
            },
        }
    }

    #[gtest]
    fn underlines_the_location_after_the_file_header() -> Result<()> {
        verify_that!(
            location(2, 11, 2, 11).render(Some("    name: @"), Some("config.defcl")),
            eq("File \"config.defcl\", line 2, column 11\n    name: @\n          ^")
        )
    }

    #[gtest]
    fn without_a_file_path_the_header_has_only_the_line_and_column() -> Result<()> {
        verify_that!(
            location(1, 8, 1, 9).render(Some("count: {}"), None),
            eq("line 1, column 8\n    count: {}\n           ^^")
        )
    }

    #[gtest]
    fn without_a_source_line_only_the_header_shows() -> Result<()> {
        verify_that!(
            location(3, 5, 3, 9).render(None, Some("test.dfn")),
            eq("File \"test.dfn\", line 3, column 5")
        )
    }

    #[gtest]
    fn location_in_the_indentation_keeps_the_indentation() -> Result<()> {
        verify_that!(
            location(2, 2, 2, 2).render(Some("  "), None),
            eq("line 2, column 2\n      \n     ^")
        )
    }

    #[gtest]
    fn location_onto_later_lines_is_underlined_to_the_end_of_its_first_line() -> Result<()> {
        verify_that!(
            location(1, 8, 2, 1).render(Some("count: {"), None),
            eq("line 1, column 8\n    count: {\n           ^")
        )
    }

    #[gtest]
    fn control_characters_are_escaped_and_the_underline_moves_with_them() -> Result<()> {
        verify_that!(
            location(1, 5, 1, 5).render(Some("a:\t{\0}\r"), None),
            eq("line 1, column 5\n    a:\\t{\\0}\\r\n         ^^")
        )
    }

    #[gtest]
    fn invisible_characters_are_escaped() -> Result<()> {
        verify_that!(
            location(1, 7, 1, 7).render(Some("# a\u{200b}b\u{e0001}c\u{301}\\"), None),
            eq(
                "line 1, column 7\n    # a\\u{200b}b\\u{e0001}c\u{301}\\\n                         ^"
            )
        )
    }

    #[gtest]
    fn empty_source_line_shows_no_code() -> Result<()> {
        verify_that!(
            location(1, 1, 1, 1).render(Some(""), None),
            eq("line 1, column 1\n\n    ^")
        )
    }

    #[gtest]
    fn escape_invisible_escapes_only_characters_that_are_not_printable() -> Result<()> {
        verify_that!(
            escape_invisible("a\u{200b}\t\"é\\\u{1}"),
            eq("a\\u{200b}\\t\"é\\\\u{1}")
        )
    }
}
