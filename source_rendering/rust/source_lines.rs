//! The lines of a source file.

use crate::SourceLocation;

/// The text of a source file, with where each of its lines starts, so that
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

    /// `location` as `SourceLocation::render` shows it, with the line of the
    /// file that it starts on, in the file at `file_path`.
    #[must_use]
    pub fn render(&self, location: SourceLocation, file_path: Option<&str>) -> String {
        location.render(Some(self.line(location.start.line_index())), file_path)
    }

    /// The text of the line at the 0-based `index`, without its line feed.
    fn line(&self, index: usize) -> &'source str {
        let start = self.line_starts[index];
        let end = self
            .line_starts
            .get(index + 1)
            .map_or(self.source.len(), |&next_start| next_start - 1);
        &self.source[start..end]
    }
}

#[cfg(test)]
mod tests {
    use super::SourceLines;
    use crate::{Position, SourceLocation};
    use googletest::prelude::*;

    #[gtest]
    fn renders_a_location_with_the_line_that_it_starts_on() -> Result<()> {
        verify_that!(
            SourceLines::new("project: {\n    name: @\n}\n").render(
                SourceLocation {
                    start: Position {
                        line: 2,
                        column: 11
                    },
                    end: Position {
                        line: 2,
                        column: 11
                    }
                },
                Some("config.defcl")
            ),
            eq("File \"config.defcl\", line 2, column 11\n    name: @\n          ^")
        )
    }

    #[gtest]
    fn location_at_the_end_of_an_empty_file_has_no_source_line() -> Result<()> {
        verify_that!(
            SourceLines::new("").render(
                SourceLocation {
                    start: Position { line: 1, column: 1 },
                    end: Position { line: 1, column: 1 }
                },
                None
            ),
            eq("line 1, column 1\n\n    ^")
        )
    }

    #[gtest]
    fn last_line_without_a_line_feed() -> Result<()> {
        verify_that!(
            SourceLines::new("a: {}").render(
                SourceLocation {
                    start: Position { line: 1, column: 4 },
                    end: Position { line: 1, column: 5 }
                },
                None
            ),
            eq("line 1, column 4\n    a: {}\n       ^^")
        )
    }
}
