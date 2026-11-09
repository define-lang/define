//! The syntax errors that parsing a DCL file can end in.

use derive_more::{Display, Error};
use source_rendering::{SourceLines, SourceLocation};
use strum::{IntoStaticStr, VariantNames};

#[derive(Debug, PartialEq, Eq, Display, Error)]
#[display("{kind}")]
pub struct SyntaxError {
    pub kind: SyntaxErrorKind,
    pub location: SourceLocation,
}

impl SyntaxError {
    /// The error as the Define compiler shows errors: the location as
    /// `SourceLines::render` shows it in `source_lines`, the text of the
    /// file at `file_path`, then the message.
    #[must_use]
    pub fn render(&self, source_lines: &SourceLines, file_path: Option<&str>) -> String {
        format!("{}\n{self}", source_lines.render(self.location, file_path))
    }
}

/// Which syntax error a `SyntaxError` is. Its message does not include the
/// location.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Display, IntoStaticStr, VariantNames)]
#[strum(serialize_all = "SCREAMING_SNAKE_CASE")]
pub enum SyntaxErrorKind {
    /// The file starts with a byte order mark.
    #[display("Byte order mark not allowed")]
    ByteOrderMark,
    /// The file has no top-level message.
    #[display("The file has no top-level message")]
    MissingTopLevelMessage,
    /// The file does not end with a line feed. The location is the file's
    /// last character.
    #[display("The file does not end with a newline")]
    MissingTrailingNewline,
    /// A tab outside a string or a comment.
    #[display("Tabs not allowed - use spaces")]
    TabNotAllowed,
    /// A carriage return outside a string or a comment.
    #[display("Carriage returns not allowed - use LF only")]
    CarriageReturnNotAllowed,
    /// A character that DCL does not allow outside a string or a comment, or
    /// a NUL in a string or a comment.
    #[display(
        "Unexpected character '{}' (U+{:04X})",
        character.escape_debug(),
        u32::from(*character)
    )]
    UnexpectedCharacter { character: char },
    /// A field name that does not follow the rules for field names.
    #[display("Invalid field name")]
    InvalidFieldName,
    /// Something other than a field name where a top-level message belongs.
    #[display("Expected a field name")]
    ExpectedFieldName,
    /// Something other than a field name or a `}` in a message value.
    #[display("Expected a field name or }}")]
    ExpectedFieldNameOrCloseBrace,
    /// A field, or a top-level message, that follows the one before it with
    /// no whitespace between them.
    #[display("Missing whitespace before the field name")]
    MissingWhitespace,
    /// A field name not followed by a colon. The location is where the colon
    /// belongs.
    #[display("Missing colon after field name")]
    MissingColon,
    /// Whitespace between a field name and its colon.
    #[display("No whitespace allowed before the colon")]
    WhitespaceBeforeColon,
    /// The colon of a top-level message not followed by a space. The location
    /// is where the space belongs.
    #[display("Missing space after the colon")]
    MissingSpaceAfterColon,
    /// Whitespace or comments after the one space that follows the colon of a
    /// top-level message.
    #[display("Only one space allowed after the colon of a top-level message")]
    ExtraWhitespaceAfterColon,
    /// Something other than a value where a value belongs.
    #[display("Expected a value")]
    ExpectedValue,
    /// A top-level message whose value is not a message value.
    #[display("Top-level values must be messages")]
    ScalarAtToplevel,
    /// A `{` with no `}` that closes it. The location is the `{`.
    #[display("Message value has no closing }}")]
    UnclosedMessage,
    /// A `[` with no `]` that closes it. The location is the `[`.
    #[display("Repeated value has no closing ]")]
    UnclosedRepeatedValue,
    /// A repeated value as an element of a repeated value. The location is its
    /// `[`.
    #[display("A repeated value cannot be an element of a repeated value")]
    RepeatedValueInRepeatedValue,
    /// Something other than a `,` or a `]` after a value in a repeated value.
    #[display("Expected , or ] after the value")]
    ExpectedCommaOrCloseBracket,
    /// Whitespace between a value and the `,` after it in a repeated value.
    #[display("No whitespace allowed before the comma")]
    WhitespaceBeforeComma,
    /// A `,` between fields, or a `;` anywhere outside a string or a comment.
    #[display("Invalid separator")]
    InvalidSeparator,
    /// A `<`, where a message value belongs or anywhere else outside a string
    /// or a comment.
    #[display("Use curly braces {{}} for messages")]
    AngleBracketsNotAllowed,
    /// A `'`, which DCL does not allow outside a string or a comment.
    #[display("Use double quotes for strings")]
    SingleQuotesNotAllowed,
    /// A string with no closing `"` on its line.
    #[display("Unterminated string - use \\n for newlines")]
    UnterminatedString,
    /// A `\` in a string that does not begin a valid escape, including an
    /// octal escape whose value does not fit in a byte.
    #[display("Invalid escape sequence")]
    InvalidEscapeSequence,
    /// A `\u` escape of a surrogate code point. The location is the escape.
    #[display("Unicode escapes cannot be surrogates (U+D800 to U+DFFF)")]
    SurrogateEscape,
    /// A run of back-to-back octal and hex escapes whose bytes are not valid
    /// UTF-8. The location is the run.
    #[display("Escape sequences must produce valid UTF-8")]
    InvalidUtf8,
    /// A word that starts like a number where a value belongs, but is not an
    /// integer or a float.
    #[display("Invalid number format")]
    InvalidNumberFormat,
    /// `-0` or `-0.0`.
    #[display("Negative zero is not allowed")]
    NegativeZero,
    /// `true` or `false` where a value belongs.
    #[display("Boolean literals not supported - use enums instead")]
    BooleanNotSupported,
    /// A word that starts with a letter where a value belongs and has a
    /// lowercase letter.
    #[display("Enum values must be ALL_CAPS")]
    InvalidEnumCase,
}

#[cfg(test)]
mod tests {
    use super::{SyntaxError, SyntaxErrorKind};
    use googletest::prelude::*;
    use indoc::indoc;
    use source_rendering::{Position, SourceLines, SourceLocation};

    #[gtest]
    fn shows_its_location_then_its_message() -> Result<()> {
        verify_that!(
            SyntaxError {
                kind: SyntaxErrorKind::MissingColon,
                location: SourceLocation {
                    start: Position { line: 1, column: 6 },
                    end: Position { line: 1, column: 6 }
                },
            }
            .render(&SourceLines::new("count {}\n"), Some("config.defcl")),
            eq(indoc! {r#"
                File "config.defcl", line 1, column 6
                    count {}
                         ^
                Missing colon after field name"#})
        )
    }
}
