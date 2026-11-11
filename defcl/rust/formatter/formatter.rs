//! The formatting of a DCL file: fixing the layout errors that changing only
//! its whitespace and comments fixes.

use defcl_parser::{SyntaxError, parse, parse_with_layout_fixes};

/// Formats `source`, the text of a DCL file.
///
/// Returns its text with each layout error fixed that changing only its
/// whitespace and comments fixes, or `None` if that changes nothing, and the
/// syntax errors that the text still has. A file whose parse a syntax error
/// stops is not changed, and that error is the only one returned.
#[must_use]
pub fn format(source: &str) -> (Option<String>, Vec<SyntaxError>) {
    let (mut result, fixes) = parse_with_layout_fixes(source);
    if result.file.is_none() {
        // The error that stopped the parse is the last.
        let stop = result.errors.split_off(result.errors.len() - 1);
        return (None, stop);
    }
    if fixes.is_empty() {
        return (None, result.errors);
    }
    let mut formatted = String::with_capacity(source.len());
    let mut copied = 0;
    for fix in &fixes {
        formatted.push_str(&source[copied..fix.start]);
        formatted.push_str(&fix.replacement);
        copied = fix.end;
    }
    formatted.push_str(&source[copied..]);
    let errors = parse(&formatted).errors;
    (Some(formatted), errors)
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
