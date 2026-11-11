//! The full message of every syntax error: its location, with its source line
//! and carets under the part that it covers, then its message.

use crate::{DecodeError, SyntaxError, SyntaxErrorKind, decode, parse};
use googletest::prelude::*;
use indoc::indoc;
use source_rendering::SourceLines;
use strum::VariantNames as _;

/// Each test data file, with every syntax error in it as the parser reports
/// them, in order and separated by blank lines.
const CASES: [(&[u8], &str); 55] = [
    (
        include_bytes!("../../testdata/invalid/syntax/file_format/bom.defcl"),
        indoc! {r"
            line 1, column 1
                \u{feff}project: {
                ^^^^^^^^
            Byte order mark not allowed"},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/file_format/empty_file.defcl"),
        "The file has no top-level message",
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/file_format/no_trailing_newline.defcl"),
        indoc! {"
            line 3, column 1
                }
                ^
            The file does not end with a newline"},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/characters/invalid_utf8.defcl"),
        indoc! {r#"
            line 2, column 12
                b: "café �"
                         ^
            Invalid UTF-8: the byte \xff does not start a valid character"#},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/whitespace/tab_char.defcl"),
        indoc! {r#"
            line 2, column 1
                \tvalue: "test"
                ^^
            Tabs not allowed - use spaces

            line 2, column 1
                \tvalue: "test"
                ^^
            Expected 2 spaces of indentation"#},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/whitespace/carriage_return.defcl"),
        indoc! {r"
            line 1, column 10
                config: {\r
                         ^^
            Carriage returns not allowed - use LF only"},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/characters/nul_in_string.defcl"),
        indoc! {r#"
            line 2, column 8
                b: "x\0"
                     ^^
            Control character U+0000 not allowed"#},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/comments/zero_width_space.defcl"),
        indoc! {r"
            line 2, column 6
                # x\u{200b}y
                   ^^^^^^^^
            Invisible character U+200B not allowed"},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/characters/at_sign.defcl"),
        indoc! {"
            line 2, column 6
                b: @
                   ^
            Unexpected character '@' (U+0040)"},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/field_names/uppercase.defcl"),
        indoc! {r#"
            line 2, column 3
                UniverseName: "example"
                ^
            Field names cannot have uppercase letters"#},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/field_names/leading_digit.defcl"),
        indoc! {r#"
            line 2, column 3
                123field: "example"
                ^
            Field names must start with a lowercase letter"#},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/field_names/hyphen.defcl"),
        indoc! {r#"
            line 2, column 11
                universe-name: "example"
                        ^
            Field names can only have lowercase letters, digits and underscores"#},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/field_names/double_underscore.defcl"),
        indoc! {r#"
            line 2, column 9
                config__value: "example"
                      ^
            Each underscore in a field name must come before a lowercase letter"#},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/toplevel/unmatched_close_brace.defcl"),
        indoc! {"
            line 1, column 1
                }
                ^
            Expected a field name"},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/messages/quoted_field_name.defcl"),
        indoc! {r#"
            line 2, column 3
                "b": 1
                ^
            Expected a field name or }"#},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/separators/missing_colon.defcl"),
        indoc! {r#"
            line 2, column 8
                value "test"
                     ^
            Missing colon after field name"#},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/separators/whitespace_before_colon.defcl"),
        indoc! {"
            line 2, column 4
                b : 1
                 ^
            No whitespace allowed before the colon"},
    ),
    (
        include_bytes!(
            "../../testdata/invalid/syntax/toplevel/two_spaces_after_top_level_colon.defcl"
        ),
        indoc! {"
            line 1, column 3
                a:  {
                  ^^
            Expected exactly one space after the colon"},
    ),
    (
        include_bytes!(
            "../../testdata/invalid/syntax/messages/fields_without_whitespace_between_them.defcl"
        ),
        indoc! {r#"
            line 2, column 9
                b: "x"c: 1
                      ^
            Missing line break: put this on a new line"#},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/whitespace/blank_line.defcl"),
        indoc! {"
            line 4, column 1

                ^
            Blank lines not allowed"},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/whitespace/trailing_space.defcl"),
        indoc! {"
            line 2, column 7
                b: 1\x20\x20
                    ^^
            Trailing whitespace not allowed"},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/comments/comment_after_field.defcl"),
        indoc! {"
            line 2, column 8
                b: 1 # x
                     ^^^
            Comments must be on their own line"},
    ),
    (
        include_bytes!(
            "../../testdata/invalid/syntax/separators/comment_before_top_level_colon.defcl"
        ),
        indoc! {"
            line 1, column 3
                a # x
                  ^^^
            Comments can only go on their own line, between fields or elements"},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/comments/no_space_after_hash.defcl"),
        indoc! {"
            line 2, column 3
                #x
                ^
            Expected a space after #"},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/messages/empty_message_value.defcl"),
        indoc! {"
            line 1, column 10
                project: {}
                         ^^
            Empty message values not allowed - leave the field out"},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/repeated_values/empty_repeated_value.defcl"),
        indoc! {"
            line 2, column 17
                dependencies: []
                              ^^
            Empty repeated values not allowed - leave the field out"},
    ),
    (
        include_bytes!(
            "../../testdata/invalid/syntax/values/close_brace_where_value_belongs.defcl"
        ),
        indoc! {"
            line 2, column 6
                b: }
                   ^
            Expected a value"},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/toplevel/scalar_toplevel.defcl"),
        indoc! {r#"
            line 1, column 7
                name: "value"
                      ^^^^^^^
            Top-level values must be messages"#},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/messages/unclosed_message.defcl"),
        indoc! {"
            line 1, column 4
                a: {
                   ^
            Message value has no closing }"},
    ),
    (
        include_bytes!(
            "../../testdata/invalid/syntax/repeated_values/unclosed_repeated_value.defcl"
        ),
        indoc! {"
            line 2, column 6
                b: [
                   ^
            Repeated value has no closing ]"},
    ),
    (
        include_bytes!(
            "../../testdata/invalid/syntax/repeated_values/repeated_value_in_repeated_value.defcl"
        ),
        indoc! {"
            line 4, column 5
                [
                ^
            A repeated value cannot be an element of a repeated value"},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/repeated_values/missing_comma.defcl"),
        indoc! {"
            line 4, column 5
                2
                ^
            Expected , or ] after the value"},
    ),
    (
        include_bytes!(
            "../../testdata/invalid/syntax/repeated_values/whitespace_before_comma.defcl"
        ),
        indoc! {"
            line 3, column 6
                1 ,
                 ^
            No whitespace allowed before the comma"},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/separators/comma_separator.defcl"),
        indoc! {"
            line 2, column 7
                a: 1, b: 2
                    ^
            Commas not allowed between fields - put each field on its own line"},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/separators/semicolon.defcl"),
        indoc! {r#"
            line 2, column 16
                value: "test";
                             ^
            Semicolons not allowed"#},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/messages/angle_brackets.defcl"),
        indoc! {"
            line 1, column 10
                project: <
                         ^
            Use curly braces {} for messages"},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/strings/single_quotes.defcl"),
        indoc! {"
            line 2, column 10
                value: 'hello'
                       ^^^^^^^
            Use double quotes for strings"},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/strings/raw_newline.defcl"),
        indoc! {r#"
            line 2, column 10
                value: "hello
                       ^^^^^^
            Unterminated string - use \n for newlines"#},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/strings/unknown_escape.defcl"),
        indoc! {r#"
            line 2, column 7
                b: "\q"
                    ^^
            Invalid escape sequence"#},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/strings/surrogate_escape.defcl"),
        indoc! {r#"
            line 2, column 7
                b: "\uD800"
                    ^^^^^^
            Unicode escapes cannot be surrogates (U+D800 to U+DFFF)"#},
    ),
    (
        include_bytes!(
            "../../testdata/invalid/syntax/strings/hex_escape_of_invalid_utf8_byte.defcl"
        ),
        indoc! {r#"
            line 2, column 7
                b: "\xff"
                    ^^^^
            Escape sequences must produce valid UTF-8"#},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/numbers/plus_sign.defcl"),
        indoc! {"
            line 2, column 10
                value: +10
                       ^
            Numbers cannot have a plus sign"},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/numbers/space_after_sign.defcl"),
        indoc! {"
            line 2, column 10
                value: - 5
                       ^
            A minus sign must be directly followed by digits"},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/numbers/leading_zeros.defcl"),
        indoc! {"
            line 2, column 10
                value: 007
                       ^
            Numbers cannot have leading zeros"},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/numbers/hex.defcl"),
        indoc! {"
            line 2, column 10
                value: 0x1A
                       ^
            Hexadecimal numbers not allowed - write the number in decimal"},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/numbers/leading_decimal.defcl"),
        indoc! {"
            line 2, column 10
                value: .5
                       ^
            A decimal point needs a digit before it, such as 0.5"},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/numbers/trailing_decimal.defcl"),
        indoc! {"
            line 2, column 12
                value: 10.
                         ^
            A decimal point needs a digit after it, such as 10.0"},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/numbers/fraction_with_trailing_zero.defcl"),
        indoc! {"
            line 2, column 9
                b: 1.50
                      ^
            Fractions cannot end with 0, except a fraction of just 0, such as 2.0"},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/numbers/extra_decimal_after_float.defcl"),
        indoc! {"
            line 2, column 10
                b: 3.14.5
                       ^
            A number can only have one decimal point"},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/numbers/scientific_int.defcl"),
        indoc! {"
            line 2, column 11
                value: 1e5
                        ^
            Scientific notation not allowed - write the number out in full"},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/numbers/type_suffix_f.defcl"),
        indoc! {"
            line 2, column 12
                value: 10f
                         ^
            Numbers cannot have suffixes"},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/numbers/underscore.defcl"),
        indoc! {"
            line 2, column 11
                value: 1_000
                        ^
            Numbers can only have digits, a leading minus sign and a decimal point"},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/numbers/negative_zero_integer.defcl"),
        indoc! {"
            line 2, column 10
                value: -0
                       ^^
            Negative zero is not allowed"},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/booleans/true_literal.defcl"),
        indoc! {"
            line 2, column 12
                enabled: true
                         ^^^^
            Boolean literals not supported - write the field's enum value, such as TRUE or FALSE for DCL's Boolean enum"},
    ),
    (
        include_bytes!("../../testdata/invalid/syntax/enums/lowercase_enum.defcl"),
        indoc! {"
            line 2, column 11
                status: active
                        ^^^^^^
            Enum values must be ALL_CAPS"},
    ),
];

/// The syntax errors in the DCL file whose bytes are `source`, with the text
/// that their locations are in.
fn syntax_errors(source: &[u8]) -> (String, Vec<SyntaxError>) {
    match decode(source.to_vec()) {
        Ok(text) => {
            let errors = parse(&text).errors;
            (text, errors)
        }
        Err(DecodeError { source, error }) => {
            // Only to show the error's line.
            (String::from_utf8_lossy(&source).into_owned(), vec![error])
        }
    }
}

/// Every syntax error in the DCL file whose bytes are `source`, rendered as
/// its location, its source line with carets, then its message, or as just its
/// message if it is about the whole file.
fn rendered_errors(source: &[u8]) -> String {
    let (text, errors) = syntax_errors(source);
    let lines = SourceLines::new(text);
    let mut rendered = Vec::with_capacity(errors.len());
    for error in &errors {
        rendered.push(match error.location {
            Some(location) => format!("{}\n{error}", lines.render(location, None)),
            // The error is about the whole file, which has no path here.
            None => error.to_string(),
        });
    }
    rendered.join("\n\n")
}

#[gtest]
fn each_file_renders_its_errors() {
    for (source, expected) in CASES {
        expect_that!(rendered_errors(source), eq(expected));
    }
}

#[gtest]
fn every_kind_of_syntax_error_has_a_case() -> Result<()> {
    let mut kinds: Vec<&str> = Vec::new();
    for (source, _) in CASES {
        for error in syntax_errors(source).1 {
            kinds.push(error.kind.into());
        }
    }
    kinds.sort_unstable();
    kinds.dedup();
    let mut variants = SyntaxErrorKind::VARIANTS.to_vec();
    variants.sort_unstable();
    verify_that!(kinds, eq(&variants))
}
