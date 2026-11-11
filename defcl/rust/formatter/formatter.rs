//! The formatting of a DCL file: fixing the layout errors that changing only
//! its whitespace and comments fixes.

use defcl_parser::{SyntaxError, SyntaxErrorKind, parse, parse_with_layout_fixes};

/// Formats `source`, the text of a DCL file.
///
/// Returns its text with Windows line endings replaced by line feeds and each
/// layout error fixed that changing only its whitespace and comments fixes, or
/// `None` if that changes nothing, and the syntax errors that the text still
/// has. A file whose parse a syntax error stops is not changed, and that error
/// is the only one returned.
#[must_use]
pub fn format(source: &str) -> (Option<String>, Vec<SyntaxError>) {
    match format_layout(source) {
        Formatted::Parsed(formatted, errors) => (formatted, errors),
        // A Windows line ending stops the parse at its carriage return, so only
        // a file whose parse stops there needs its line endings replaced. A
        // string cannot span lines, so a carriage return before a line feed is
        // always part of a line ending.
        Formatted::Stopped(stop)
            if stop.kind == SyntaxErrorKind::CarriageReturnNotAllowed
                && source.contains("\r\n") =>
        {
            let line_feeds_only = source.replace("\r\n", "\n");
            match format_layout(&line_feeds_only) {
                Formatted::Parsed(formatted, errors) => {
                    (Some(formatted.unwrap_or(line_feeds_only)), errors)
                }
                Formatted::Stopped(error) => (None, vec![error]),
            }
        }
        Formatted::Stopped(error) => (None, vec![error]),
    }
}

/// What fixing the layout errors of a DCL file's text found.
enum Formatted {
    /// The text with its layout errors fixed, or `None` if it had none to fix,
    /// and the syntax errors that it still has.
    Parsed(Option<String>, Vec<SyntaxError>),
    /// The syntax error that stopped the parse of the text.
    Stopped(SyntaxError),
}

/// Fixes the layout errors in `text` that changing only its whitespace and
/// comments fixes.
fn format_layout(text: &str) -> Formatted {
    let (mut result, fixes) = parse_with_layout_fixes(text);
    if result.file.is_none() {
        // The error that stopped the parse is the last.
        return Formatted::Stopped(result.errors.swap_remove(result.errors.len() - 1));
    }
    if fixes.is_empty() {
        let errors = result.errors;
        return Formatted::Parsed(None, errors);
    }
    let mut formatted = String::with_capacity(text.len());
    let mut copied = 0;
    for fix in &fixes {
        formatted.push_str(&text[copied..fix.start]);
        formatted.push_str(&fix.replacement);
        copied = fix.end;
    }
    formatted.push_str(&text[copied..]);
    let errors = parse(&formatted).errors;
    Formatted::Parsed(Some(formatted), errors)
}

#[cfg(test)]
mod tests {
    use super::format;
    use defcl_parser::{SyntaxError, SyntaxErrorKind};
    use googletest::prelude::*;
    use indoc::indoc;
    use source_rendering::{Position, SourceLocation};

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
    fn formatted_file_is_unchanged() -> Result<()> {
        let source = indoc! {"
            a: {
              b: 1
            }
        "};
        verify_that!(format(source), (none(), is_empty()))
    }

    #[gtest]
    fn indentation() -> Result<()> {
        verify_that!(
            format(indoc! {"
                a: {
                    b: {
                        c: 1
                    }
                }
            "}),
            (
                some(eq(indoc! {"
                    a: {
                      b: {
                        c: 1
                      }
                    }
                "})),
                is_empty()
            )
        )
    }

    #[gtest]
    fn values_on_one_line() -> Result<()> {
        verify_that!(
            format("a: { b: 1 c: [1, 2] }\n"),
            (
                some(eq(indoc! {"
                    a: {
                      b: 1
                      c: [
                        1,
                        2
                      ]
                    }
                "})),
                is_empty()
            )
        )
    }

    #[gtest]
    fn comments_blank_lines_and_trailing_whitespace() -> Result<()> {
        verify_that!(
            format(indoc! {"
                # top
                a: {
                  b: 1 # trailing
                  #x

                  c: 2\x20\x20
                }"}),
            (
                some(eq(indoc! {"
                    # top
                    a: {
                      b: 1
                      # trailing
                      # x
                      c: 2
                    }
                "})),
                is_empty()
            )
        )
    }

    #[gtest]
    fn windows_line_endings_become_line_feeds() -> Result<()> {
        verify_that!(
            format("# x\r\na: {\r\n  b: \"y\"\r\n}\r\n"),
            (some(eq("# x\na: {\n  b: \"y\"\n}\n")), is_empty())
        )
    }

    #[gtest]
    fn windows_line_endings_with_layout_errors() -> Result<()> {
        verify_that!(
            format("a: {\r\n    b: 1\r\n}\r\n"),
            (some(eq("a: {\n  b: 1\n}\n")), is_empty())
        )
    }

    #[gtest]
    fn windows_line_endings_and_another_stopping_error_are_left_unchanged() -> Result<()> {
        verify_that!(
            format("a: {\r\n  b: @\r\n}\r\n"),
            (
                none(),
                eq(&vec![SyntaxError {
                    kind: SyntaxErrorKind::UnexpectedCharacter { character: '@' },
                    location: location(2, 6, 2, 6),
                }])
            )
        )
    }

    #[gtest]
    fn carriage_return_without_a_line_feed_is_left_with_its_error() -> Result<()> {
        verify_that!(
            format("a: {\n  b: 1\r}\n"),
            (
                none(),
                eq(&vec![SyntaxError {
                    kind: SyntaxErrorKind::CarriageReturnNotAllowed,
                    location: location(2, 7, 2, 7),
                }])
            )
        )
    }

    #[gtest]
    fn tabs_that_end_a_comment_are_removed() -> Result<()> {
        verify_that!(
            format("a: {\n  # x \t\n  # y\tz\n  b: 1\n}\n"),
            (
                some(eq("a: {\n  # x\n  # y\tz\n  b: 1\n}\n")),
                eq(&vec![SyntaxError {
                    kind: SyntaxErrorKind::ControlCharacter { character: '\t' },
                    location: location(3, 6, 3, 6),
                }])
            )
        )
    }

    #[gtest]
    fn spaces_that_start_a_comment_s_text_are_kept() -> Result<()> {
        verify_that!(
            format(indoc! {"
                a: {
                    #   |
                  b: 1
                }
            "}),
            (
                some(eq(indoc! {"
                    a: {
                      #   |
                      b: 1
                    }
                "})),
                is_empty()
            )
        )
    }

    #[gtest]
    fn comment_that_starts_the_file() -> Result<()> {
        verify_that!(
            format(indoc! {"
                  # top
                a: {
                  b: 1
                }
            "}),
            (
                some(eq(indoc! {"
                    # top
                    a: {
                      b: 1
                    }
                "})),
                is_empty()
            )
        )
    }

    #[gtest]
    fn comment_of_only_spaces_becomes_a_bare_hash() -> Result<()> {
        verify_that!(
            format(indoc! {"
                a: {
                    #\x20\x20
                  b: 1
                }
            "}),
            (
                some(eq(indoc! {"
                    a: {
                      #
                      b: 1
                    }
                "})),
                is_empty()
            )
        )
    }

    #[gtest]
    fn spacing_around_colons_and_commas() -> Result<()> {
        verify_that!(
            format(indoc! {"
                a: {
                  b :1
                  c: [
                    1 ,
                    2
                  ]
                }
            "}),
            (
                some(eq(indoc! {"
                    a: {
                      b: 1
                      c: [
                        1,
                        2
                      ]
                    }
                "})),
                is_empty()
            )
        )
    }

    #[gtest]
    fn empty_message_value_is_left_with_its_error() -> Result<()> {
        verify_that!(
            format(indoc! {"
                a: {
                    b: {}
                }
            "}),
            (
                some(eq(indoc! {"
                    a: {
                      b: {}
                    }
                "})),
                eq(&vec![SyntaxError {
                    kind: SyntaxErrorKind::EmptyMessageValue,
                    location: location(2, 6, 2, 7),
                }])
            )
        )
    }

    #[gtest]
    fn comment_between_a_field_name_and_its_colon_is_left_with_its_error() -> Result<()> {
        let source = indoc! {"
            a # x
            : {
              b: 1
            }
        "};
        verify_that!(
            format(source),
            (
                none(),
                eq(&vec![SyntaxError {
                    kind: SyntaxErrorKind::MisplacedComment,
                    location: location(1, 3, 1, 5),
                }])
            )
        )
    }

    #[gtest]
    fn file_whose_parse_stops_is_unchanged() -> Result<()> {
        let source = indoc! {"
            a: {
                b: @
            }
        "};
        verify_that!(
            format(source),
            (
                none(),
                eq(&vec![SyntaxError {
                    kind: SyntaxErrorKind::UnexpectedCharacter { character: '@' },
                    location: location(2, 8, 2, 8),
                }])
            )
        )
    }
}
