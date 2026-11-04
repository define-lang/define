//! The syntax errors that parsing a DCL file can end in.

use crate::source_location::SourceLocation;

#[derive(Debug, PartialEq, Eq)]
pub enum SyntaxError {
    /// The file starts with a byte order mark.
    ByteOrderMark { location: SourceLocation },
    /// The file has no top-level message.
    MissingTopLevelMessage { location: SourceLocation },
    /// The file does not end with a line feed. The location is the file's
    /// last character.
    MissingTrailingNewline { location: SourceLocation },
    /// A tab outside a string or a comment.
    TabNotAllowed { location: SourceLocation },
    /// A carriage return outside a string or a comment.
    CarriageReturnNotAllowed { location: SourceLocation },
    /// A character that DCL does not allow outside a string or a comment, or
    /// a NUL in a string or a comment.
    UnexpectedCharacter {
        location: SourceLocation,
        character: char,
    },
    /// A field name that does not follow the rules for field names.
    InvalidFieldName { location: SourceLocation },
    /// Something other than a field name where a top-level message belongs.
    ExpectedFieldName { location: SourceLocation },
    /// Something other than a field name or a `}` in a message value.
    ExpectedFieldNameOrCloseBrace { location: SourceLocation },
    /// A field, or a top-level message, that follows the one before it with
    /// no whitespace between them.
    MissingWhitespace { location: SourceLocation },
    /// A field name not followed by a colon. The location is where the colon
    /// belongs.
    MissingColon { location: SourceLocation },
    /// Whitespace between a field name and its colon.
    WhitespaceBeforeColon { location: SourceLocation },
    /// The colon of a top-level message not followed by a space. The location
    /// is where the space belongs.
    MissingSpaceAfterColon { location: SourceLocation },
    /// Whitespace or comments after the one space that follows the colon of a
    /// top-level message.
    ExtraWhitespaceAfterColon { location: SourceLocation },
    /// Something other than a value where a value belongs.
    ExpectedValue { location: SourceLocation },
    /// A top-level message whose value is not a message value.
    ScalarAtToplevel { location: SourceLocation },
    /// A `{` with no `}` that closes it. The location is the `{`.
    UnclosedMessage { location: SourceLocation },
    /// A `[` with no `]` that closes it. The location is the `[`.
    UnclosedRepeatedValue { location: SourceLocation },
    /// A repeated value as an element of a repeated value. The location is its
    /// `[`.
    RepeatedValueInRepeatedValue { location: SourceLocation },
    /// Something other than a `,` or a `]` after a value in a repeated value.
    ExpectedCommaOrCloseBracket { location: SourceLocation },
    /// Whitespace between a value and the `,` after it in a repeated value.
    WhitespaceBeforeComma { location: SourceLocation },
    /// A `,` between fields, or a `;` anywhere outside a string or a comment.
    InvalidSeparator { location: SourceLocation },
    /// A `<`, where a message value belongs or anywhere else outside a string
    /// or a comment.
    AngleBracketsNotAllowed { location: SourceLocation },
    /// A `'`, which DCL does not allow outside a string or a comment.
    SingleQuotesNotAllowed { location: SourceLocation },
    /// A string with no closing `"` on its line.
    UnterminatedString { location: SourceLocation },
    /// A `\` in a string that does not begin a valid escape.
    InvalidEscapeSequence { location: SourceLocation },
    /// A word that starts like a number where a value belongs, but is not an
    /// integer or a float.
    InvalidNumberFormat { location: SourceLocation },
    /// `true` or `false` where a value belongs.
    BooleanNotSupported { location: SourceLocation },
    /// A word that starts with a letter where a value belongs and has a
    /// lowercase letter.
    InvalidEnumCase { location: SourceLocation },
}
