//! Places in the source, and how errors show them.

const CODE_INDENTATION: &str = "    ";

/// The text of a DCL file, with where each of its lines starts, so that
/// showing many locations in it reads it only once.
pub struct SourceLines<'source> {
    source: &'source str,
    // The byte offset of each line's first character.
    line_starts: Vec<usize>,
}

impl<'source> SourceLines<'source> {
    #[must_use]
    pub fn new(source: &'source str) -> Self {
        let mut line_starts = vec![0];
        line_starts.extend(source.match_indices('\n').map(|(offset, _)| offset + 1));
        Self {
            source,
            line_starts,
        }
    }

    /// The text of the 1-based line `line`, without its line feed.
    fn line(&self, line: usize) -> &'source str {
        let start = self.line_starts[line - 1];
        let end = self
            .line_starts
            .get(line)
            .map_or(self.source.len(), |&next_start| next_start - 1);
        &self.source[start..end]
    }
}

/// A point in the source, as a 1-based line and a 1-based column counted in
/// characters.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Position {
    pub line: usize,
    pub column: usize,
}

/// The part of the source that a node or an error covers.
///
/// Lines and columns are 1-based, columns count characters, and `end_line` and
/// `end_column` are the position of the last character that the location
/// covers.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct SourceLocation {
    pub line: usize,
    pub column: usize,
    pub end_line: usize,
    pub end_column: usize,
}

impl SourceLocation {
    /// The location from `start` through `end`, the position of the last
    /// character covered.
    pub(crate) const fn new(start: Position, end: Position) -> Self {
        Self {
            line: start.line,
            column: start.column,
            end_line: end.line,
            end_column: end.column,
        }
    }

    /// The location of the one character at `position`, or of the point
    /// where something belongs.
    pub(crate) const fn at(position: Position) -> Self {
        Self::new(position, position)
    }

    pub(crate) const fn start(self) -> Position {
        Position {
            line: self.line,
            column: self.column,
        }
    }

    pub(crate) const fn end(self) -> Position {
        Position {
            line: self.end_line,
            column: self.end_column,
        }
    }

    /// The header `File "<file_path>", line N, column M`, or
    /// `line N, column M` with no `file_path`, then the line of `source_lines`
    /// that the location starts on, with carets under the part that it covers.
    ///
    /// A location that continues onto later lines is underlined to the end of
    /// its first line. Characters that are not printable, such as control
    /// characters, invisible formatting characters and separators other than
    /// the space, show as the escapes that Rust's `char::escape_debug` writes,
    /// such as `\t`, `\0` and `\u{200b}`, so that they cannot change what a
    /// terminal shows.
    #[must_use]
    pub fn render(self, source_lines: &SourceLines, file_path: Option<&str>) -> String {
        let mut rendered = match file_path {
            Some(file_path) => format!(
                "File \"{file_path}\", line {}, column {}",
                self.line, self.column
            ),
            None => format!("line {}, column {}", self.line, self.column),
        };
        let source_line = source_lines.line(self.line);
        // Only our own indentation should show, not the source's, unless the
        // location is in that indentation.
        let mut indentation = source_line.len() - source_line.trim_start_matches(' ').len();
        if self.column - 1 < indentation {
            indentation = 0;
        }
        // Spaces are one byte each, so the indentation's length in bytes is
        // its length in characters.
        let code = &source_line[indentation..];
        let start = self.column - 1 - indentation;
        // end_column is the column of the location's last character. A
        // location that continues onto later lines has no end on this line.
        let end = (self.end_line == self.line).then(|| self.end_column - indentation);
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
        // Nearly all of a DCL file is printable ASCII, which needs no escaping,
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
    use super::{SourceLines, SourceLocation};
    use googletest::prelude::*;

    #[gtest]
    fn underlines_the_location_after_the_file_header() -> Result<()> {
        verify_that!(
            SourceLocation {
                line: 2,
                column: 11,
                end_line: 2,
                end_column: 11
            }
            .render(
                &SourceLines::new("project: {\n    name: @\n}\n"),
                Some("config.defcl")
            ),
            eq("File \"config.defcl\", line 2, column 11\n    name: @\n          ^")
        )
    }

    #[gtest]
    fn without_a_file_path_the_header_has_only_the_line_and_column() -> Result<()> {
        verify_that!(
            SourceLocation {
                line: 1,
                column: 8,
                end_line: 1,
                end_column: 9
            }
            .render(&SourceLines::new("count: {}\n"), None),
            eq("line 1, column 8\n    count: {}\n           ^^")
        )
    }

    #[gtest]
    fn location_in_the_indentation_keeps_the_indentation() -> Result<()> {
        verify_that!(
            SourceLocation {
                line: 2,
                column: 2,
                end_line: 2,
                end_column: 2
            }
            .render(&SourceLines::new("project: {\n  \n}\n"), None),
            eq("line 2, column 2\n      \n     ^")
        )
    }

    #[gtest]
    fn location_onto_later_lines_is_underlined_to_the_end_of_its_first_line() -> Result<()> {
        verify_that!(
            SourceLocation {
                line: 1,
                column: 8,
                end_line: 2,
                end_column: 1
            }
            .render(&SourceLines::new("count: {\n}\n"), None),
            eq("line 1, column 8\n    count: {\n           ^")
        )
    }

    #[gtest]
    fn control_characters_are_escaped_and_the_underline_moves_with_them() -> Result<()> {
        verify_that!(
            SourceLocation {
                line: 1,
                column: 5,
                end_line: 1,
                end_column: 5
            }
            .render(&SourceLines::new("a:\t{\0}\r\n"), None),
            eq("line 1, column 5\n    a:\\t{\\0}\\r\n         ^^")
        )
    }

    #[gtest]
    fn invisible_characters_are_escaped() -> Result<()> {
        verify_that!(
            SourceLocation {
                line: 1,
                column: 7,
                end_line: 1,
                end_column: 7
            }
            .render(&SourceLines::new("# a\u{200b}b\u{e0001}c\u{301}\\\n"), None),
            eq(
                "line 1, column 7\n    # a\\u{200b}b\\u{e0001}c\u{301}\\\n                         ^"
            )
        )
    }

    #[gtest]
    fn location_at_the_end_of_an_empty_file_has_no_source_line() -> Result<()> {
        verify_that!(
            SourceLocation {
                line: 1,
                column: 1,
                end_line: 1,
                end_column: 1
            }
            .render(&SourceLines::new(""), None),
            eq("line 1, column 1\n\n    ^")
        )
    }
}
