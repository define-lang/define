//! The formatting of a defcl file: fixing the layout errors that changing only
//! its whitespace and comments fixes.

use defcl_parser::{LayoutFix, ParseResult, SyntaxError, parse, parse_with_layout_fixes};

/// Formats `source`, the text of a defcl file.
///
/// Returns its text with each layout error fixed that changing only its
/// whitespace and comments fixes, and each invisible character outside its
/// strings deleted, or `None` if that changes nothing, and the syntax errors
/// that the text still has. A file whose parse a syntax error stops is not
/// changed, and that error is the only one returned.
#[must_use]
pub fn format(source: &str) -> (Option<String>, Vec<SyntaxError>) {
    let (result, fixes) = match parse_unless_stopped(source) {
        Ok(parsed) => parsed,
        Err(stop) => return (None, stop),
    };
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

/// Whether `format` changes `source`, the text of a defcl file, and the syntax
/// errors that the formatted text still has, at their places in `source`.
#[must_use]
pub fn check(source: &str) -> (bool, Vec<SyntaxError>) {
    let (mut result, fixes) = match parse_unless_stopped(source) {
        Ok(parsed) => parsed,
        Err(stop) => return (false, stop),
    };
    let mut fixed_errors = fixes.iter().map(|fix| &fix.fixed_errors).peekable();
    let mut index = 0;
    result.errors.retain(|_| {
        let error = index;
        index += 1;
        while fixed_errors.next_if(|errors| errors.end <= error).is_some() {}
        !fixed_errors
            .peek()
            .is_some_and(|errors| errors.contains(&error))
    });
    (!fixes.is_empty(), result.errors)
}

/// Parses `source` with the fixes for its layout errors, or returns the
/// syntax error that stops its parse.
fn parse_unless_stopped(
    source: &str,
) -> Result<(ParseResult<'_>, Vec<LayoutFix>), Vec<SyntaxError>> {
    let (mut result, fixes) = parse_with_layout_fixes(source);
    if result.file.is_none() {
        // The error that stopped the parse is the last.
        return Err(result.errors.split_off(result.errors.len() - 1));
    }
    Ok((result, fixes))
}

#[cfg(test)]
mod tests {
    use super::{check, format};
    use defcl_parser::{SyntaxError, SyntaxErrorKind};
    use googletest::prelude::*;
    use indoc::{formatdoc, indoc};
    use source_rendering::{Position, SourceLocation};

    const BYTE_ORDER_MARK: char = '\u{feff}';
    const ZERO_WIDTH_SPACE: char = '\u{200b}';

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
            format(indoc! {"
                # x\r
                a: {\r
                  b: \"y\"\r
                }\r
            "}),
            (
                some(eq(indoc! {"
                    # x
                    a: {
                      b: \"y\"
                    }
                "})),
                is_empty()
            )
        )
    }

    #[gtest]
    fn windows_line_endings_with_layout_errors() -> Result<()> {
        verify_that!(
            format(indoc! {"
                a: {\r
                    b: 1\r
                }\r
            "}),
            (
                some(eq(indoc! {"
                    a: {
                      b: 1
                    }
                "})),
                is_empty()
            )
        )
    }

    #[gtest]
    fn windows_line_endings_and_another_stopping_error_are_left_unchanged() -> Result<()> {
        verify_that!(
            format(indoc! {"
                a: {\r
                  b: @\r
                }\r
            "}),
            (
                none(),
                eq(&vec![SyntaxError {
                    kind: SyntaxErrorKind::UnexpectedCharacter { character: '@' },
                    location: Some(location(2, 6, 2, 6)),
                }])
            )
        )
    }

    #[gtest]
    fn carriage_return_without_a_line_feed_is_deleted() -> Result<()> {
        verify_that!(
            format(indoc! {"
                a: {
                  b: 1\r}
            "}),
            (
                some(eq(indoc! {"
                    a: {
                      b: 1
                    }
                "})),
                is_empty()
            )
        )
    }

    #[gtest]
    fn invisible_characters_outside_strings_are_deleted() -> Result<()> {
        verify_that!(
            format(&formatdoc! {"
                {BYTE_ORDER_MARK}a: {{
                \tb:\t1
                  c: \"\\t\"{ZERO_WIDTH_SPACE}
                }}
            "}),
            (
                some(eq(indoc! {"
                    a: {
                      b: 1
                      c: \"\\t\"
                    }
                "})),
                is_empty()
            )
        )
    }

    #[gtest]
    fn tabs_in_comments_are_deleted() -> Result<()> {
        verify_that!(
            format(indoc! {"
                a: {
                  # x \t
                  # y\tz
                  b: 1
                }
            "}),
            (
                some(eq(indoc! {"
                    a: {
                      # x
                      # yz
                      b: 1
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
                    location: Some(location(2, 6, 2, 7)),
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
                    location: Some(location(1, 3, 1, 5)),
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
                    location: Some(location(2, 8, 2, 8)),
                }])
            )
        )
    }

    #[gtest]
    fn check_finds_a_formatted_file_unchanged() -> Result<()> {
        verify_that!(
            check(indoc! {"
                a: {
                  b: 1
                }
            "}),
            (eq(&false), is_empty())
        )
    }

    #[gtest]
    fn check_reports_the_remaining_errors_at_their_places_in_the_source() -> Result<()> {
        verify_that!(
            check(indoc! {"
                a: {
                    b: {}
                }
            "}),
            (
                eq(&true),
                eq(&vec![SyntaxError {
                    kind: SyntaxErrorKind::EmptyMessageValue,
                    location: Some(location(2, 8, 2, 9)),
                }])
            )
        )
    }

    #[gtest]
    fn check_reports_an_error_that_formatting_leaves() -> Result<()> {
        verify_that!(
            check(indoc! {"
                a # x
                : {
                    b: 1
                }
            "}),
            (
                eq(&true),
                eq(&vec![SyntaxError {
                    kind: SyntaxErrorKind::MisplacedComment,
                    location: Some(location(1, 3, 1, 5)),
                }])
            )
        )
    }

    #[gtest]
    fn check_reports_the_first_carriage_return_that_formatting_leaves() -> Result<()> {
        // Formatting deletes the carriage return on the first line, but not
        // the one among the whitespace that the misplaced comment is in.
        verify_that!(
            check(indoc! {"
                a: {\r
                  b\r
                  # x
                  : 1
                }
            "}),
            (
                eq(&true),
                eq(&vec![
                    SyntaxError {
                        kind: SyntaxErrorKind::MisplacedComment,
                        location: Some(location(3, 3, 3, 5)),
                    },
                    SyntaxError {
                        kind: SyntaxErrorKind::CarriageReturnNotAllowed,
                        location: Some(location(2, 4, 2, 4)),
                    },
                ])
            )
        )
    }

    #[gtest]
    fn check_reports_the_error_that_stops_the_parse() -> Result<()> {
        verify_that!(
            check(indoc! {"
                a: {
                    b: @
                }
            "}),
            (eq(&false), len(eq(1)))
        )
    }
}
