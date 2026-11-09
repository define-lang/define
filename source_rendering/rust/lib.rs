//! How diagnostics show a location in a source file: a header that names its
//! line and column, then its source line with carets under the part that it
//! covers. The Define compiler and the Define Configuration Language share it.

mod source_lines;
mod source_map;

use source_lines::SourceLines;
pub use source_map::{NoInMemorySource, SourceMap};

pub(crate) const CODE_INDENTATION: &str = "    ";

/// A point in a source file, as a 1-based line and a 1-based column counted in
/// characters.
#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct Position {
    pub line: u32,
    pub column: u32,
}

impl Position {
    /// The 0-based index of the line.
    #[must_use]
    pub const fn line_index(self) -> usize {
        self.line as usize - 1
    }

    /// The 0-based index of the column, counted in characters.
    #[must_use]
    pub const fn column_index(self) -> usize {
        self.column as usize - 1
    }

    /// The position `count` columns later on the same line.
    #[must_use]
    #[expect(
        clippy::cast_possible_truncation,
        reason = "Positions are u32 to keep locations small, which limits a line to 4 Gi characters."
    )]
    pub const fn columns_later(self, count: usize) -> Self {
        Self {
            line: self.line,
            column: self.column + count as u32,
        }
    }

    /// The position one column later on the same line.
    #[must_use]
    pub const fn next_column(self) -> Self {
        self.columns_later(1)
    }

    /// The position one column earlier on the same line, which must not be the
    /// first column.
    #[must_use]
    pub const fn previous_column(self) -> Self {
        Self {
            line: self.line,
            column: self.column - 1,
        }
    }
}

/// The part of a source file that something, such as an error, covers: from
/// `start` through `end`, the position of the last character that it covers.
// `repr(C)` lets the Python extension's capsule pass it to other extensions.
#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
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
        let start_index = self.start.column_index();
        let mut indentation = source_line.len() - source_line.trim_start_matches(' ').len();
        if start_index < indentation {
            indentation = 0;
        }
        // Spaces are one byte each, so the indentation's length in bytes is
        // its length in characters.
        let code = &source_line[indentation..];
        let start = start_index - indentation;
        // The underline ends after the location's last character. A location
        // that continues onto later lines has no end on this line.
        let end =
            (self.end.line == self.start.line).then(|| self.end.column_index() + 1 - indentation);
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
    use indoc::indoc;

    const fn location(line: u32, column: u32, end_line: u32, end_column: u32) -> SourceLocation {
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
            eq(indoc! {r#"
                File "config.defcl", line 2, column 11
                    name: @
                          ^"#})
        )
    }

    #[gtest]
    fn without_a_file_path_the_header_has_only_the_line_and_column() -> Result<()> {
        verify_that!(
            location(1, 8, 1, 9).render(Some("count: {}"), None),
            eq(indoc! {"
                line 1, column 8
                    count: {}
                           ^^"})
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
            // One string, since its second line has only spaces, which editors
            // strip from the end of a line.
            eq("line 2, column 2\n      \n     ^")
        )
    }

    #[gtest]
    fn location_onto_later_lines_is_underlined_to_the_end_of_its_first_line() -> Result<()> {
        verify_that!(
            location(1, 8, 2, 1).render(Some("count: {"), None),
            eq(indoc! {"
                line 1, column 8
                    count: {
                           ^"})
        )
    }

    #[gtest]
    fn control_characters_are_escaped_and_the_underline_moves_with_them() -> Result<()> {
        verify_that!(
            location(1, 5, 1, 5).render(Some("a:\t{\0}\r"), None),
            eq(indoc! {r"
                line 1, column 5
                    a:\t{\0}\r
                         ^^"})
        )
    }

    #[gtest]
    fn invisible_characters_are_escaped() -> Result<()> {
        verify_that!(
            location(1, 7, 1, 7).render(Some("# a\u{200b}b\u{e0001}c\u{301}\\"), None),
            // One string, since rustfmt reindents the line after one that ends
            // in a backslash, and the combining character must stay escaped.
            eq(
                "line 1, column 7\n    # a\\u{200b}b\\u{e0001}c\u{301}\\\n                         ^"
            )
        )
    }

    #[gtest]
    fn empty_source_line_shows_no_code() -> Result<()> {
        verify_that!(
            location(1, 1, 1, 1).render(Some(""), None),
            eq(indoc! {"
                line 1, column 1

                    ^"})
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
