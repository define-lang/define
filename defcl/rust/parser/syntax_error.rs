//! The syntax errors that parsing a DCL file can end in.

use derive_more::{Display, Error};
use source_rendering::SourceLocation;
use strum::{IntoStaticStr, VariantNames};

#[derive(Debug, PartialEq, Eq, Display, Error)]
#[display("{kind}")]
pub struct SyntaxError {
    pub kind: SyntaxErrorKind,
    /// Where the error is, or `None` if it is about the whole file.
    pub location: Option<SourceLocation>,
}

/// Which syntax error a `SyntaxError` is.
///
/// Its message does not include the location. Every error stops the parse,
/// except a layout error, which is an error in the layout of a file and says
/// so, and an error that says where the parse goes on past it.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Display, IntoStaticStr, VariantNames)]
#[strum(serialize_all = "SCREAMING_SNAKE_CASE")]
pub enum SyntaxErrorKind {
    /// A byte order mark. Outside strings, the parse goes on past it as if it
    /// were not there, unless it splits a word such as a field name.
    #[display("Byte order mark not allowed")]
    ByteOrderMark,
    /// The file has no top-level message. It has no location, since it is
    /// about the whole file.
    #[display("The file has no top-level message")]
    MissingTopLevelMessage,
    /// The file does not end with a line feed. The location is the file's
    /// last character. A layout error.
    #[display("The file does not end with a newline")]
    MissingTrailingNewline,
    /// A byte that is not valid UTF-8, or that starts a sequence of bytes that
    /// is not. The location is the byte.
    #[display("Invalid UTF-8: the byte \\x{byte:02x} does not start a valid character")]
    InvalidEncoding { byte: u8 },
    /// A tab outside a string. The parse goes on past it as if it were not
    /// there, unless it splits a word such as a field name. Only the first tab
    /// that starts a line in a file gets an error.
    #[display("Tabs not allowed - use spaces")]
    TabNotAllowed,
    /// A carriage return. Outside strings, the parse goes on past it as if it
    /// were not there, unless it splits a word such as a field name, and only
    /// the first in a file gets an error.
    #[display("Carriage returns not allowed - use LF only")]
    CarriageReturnNotAllowed,
    /// A control character other than a line feed or a carriage return, or a
    /// tab in a string. A string can only have one through an escape. Outside strings, the parse
    /// goes on past it as if it were not there, unless it splits a word such as
    /// a field name.
    #[display("Control character U+{:04X} not allowed", u32::from(*character))]
    ControlCharacter { character: char },
    /// An invisible character that the Invisible Characters rule does not
    /// allow. Outside strings, the parse goes on past it as if it were not
    /// there, unless it splits a word such as a field name.
    #[display("Invisible character U+{:04X} not allowed", u32::from(*character))]
    InvisibleCharacter { character: char },
    /// A character that DCL does not allow outside a string or a comment.
    #[display(
        "Unexpected character '{}' (U+{:04X})",
        character.escape_debug(),
        u32::from(*character)
    )]
    UnexpectedCharacter { character: char },
    /// An uppercase letter in a field name. The location is the first one.
    #[display("Field names cannot have uppercase letters")]
    UppercaseInFieldName,
    /// A field name that starts with a digit or an underscore. The location is
    /// that character.
    #[display("Field names must start with a lowercase letter")]
    FieldNameStartsWithNonLetter,
    /// A `-` or `.` in a field name. The location is the first one.
    #[display("Field names can only have lowercase letters, digits and underscores")]
    InvalidCharacterInFieldName,
    /// An underscore in a field name that is not followed by a lowercase
    /// letter. The location is the first one.
    #[display("Each underscore in a field name must come before a lowercase letter")]
    UnderscoreNotBeforeLetter,
    /// Something other than a field name where a top-level message belongs.
    #[display("Expected a field name")]
    ExpectedFieldName,
    /// Something other than a field name or a `}` in a message value.
    #[display("Expected a field name or }}")]
    ExpectedFieldNameOrCloseBrace,
    /// A field name not followed by a colon. The location is where the colon
    /// belongs.
    #[display("Missing colon after field name")]
    MissingColon,
    /// Whitespace between a field name and its colon. A layout error.
    #[display("No whitespace allowed before the colon")]
    WhitespaceBeforeColon,
    /// Whitespace after a colon that is not exactly one space.
    /// The location is where the space belongs if there are none. A layout
    /// error.
    #[display("Expected exactly one space after the colon")]
    WrongSpacingAfterColon,
    /// A field, an element of a repeated value, or a `}` or `]` that closes
    /// one with fields or elements, on the same line as what comes before it.
    /// The location is where its line belongs to start. A layout error.
    #[display("Missing line break: put this on a new line")]
    MissingLineBreak,
    /// A line with nothing but spaces, or nothing at all. A layout error.
    #[display("Blank lines not allowed")]
    BlankLine,
    /// A line that does not start with the spaces of its indentation: 2 for
    /// each level of the fields and elements that it is in. The location is
    /// the spaces that start the line. A layout error.
    #[display("Expected {expected_spaces} spaces of indentation")]
    WrongIndentation { expected_spaces: u32 },
    /// Spaces at the end of a line, including a comment's line. A layout
    /// error.
    #[display("Trailing whitespace not allowed")]
    TrailingWhitespace,
    /// A comment after something else on its line. A layout error.
    #[display("Comments must be on their own line")]
    CommentNotOnOwnLine,
    /// A comment between a field name and its colon, between a colon and its
    /// value, or between an element of a repeated value and the `,` after it.
    /// The location is from the first comment's `#` to the end of the last.
    /// A layout error.
    #[display("Comments can only go on their own line, between fields or elements")]
    MisplacedComment,
    /// A comment whose text follows its `#` with no space between them. The
    /// location is the `#`. A layout error.
    #[display("Expected a space after #")]
    CommentSpacing,
    /// A message value with no fields. A layout error.
    #[display("Empty message values not allowed - leave the field out")]
    EmptyMessageValue,
    /// A repeated value with no elements. A layout error.
    #[display("Empty repeated values not allowed - leave the field out")]
    EmptyRepeatedValue,
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
    /// Whitespace between a value and the `,` after it in a repeated value. A
    /// layout error.
    #[display("No whitespace allowed before the comma")]
    WhitespaceBeforeComma,
    /// A `,` after a field, where only a line break belongs.
    #[display("Commas not allowed between fields - put each field on its own line")]
    CommaBetweenFields,
    /// A `;` anywhere outside a string or a comment.
    #[display("Semicolons not allowed")]
    SemicolonNotAllowed,
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
    /// A `+` that starts a number. The location is the `+`.
    #[display("Numbers cannot have a plus sign")]
    PlusSignInNumber,
    /// A `-` not directly followed by a digit or a decimal point. The location
    /// is the `-`.
    #[display("A minus sign must be directly followed by digits")]
    MinusSignWithoutDigits,
    /// A `0` followed by a digit at the start of a number. The location is the
    /// `0`.
    #[display("Numbers cannot have leading zeros")]
    LeadingZeroInNumber,
    /// A `0x` or `0X` at the start of a number. The location is the `0`.
    #[display("Hexadecimal numbers not allowed - write the number in decimal")]
    HexadecimalNumber,
    /// A decimal point with no digit before it. The location is the decimal
    /// point.
    #[display("A decimal point needs a digit before it, such as 0.5")]
    MissingDigitBeforeDecimalPoint,
    /// A decimal point with no digit after it. The location is the decimal
    /// point.
    #[display("A decimal point needs a digit after it, such as 10.0")]
    MissingDigitAfterDecimalPoint,
    /// A fraction other than `0` that ends with `0`. The location is the last
    /// `0`.
    #[display("Fractions cannot end with 0, except a fraction of just 0, such as 2.0")]
    TrailingZeroInFraction,
    /// A second decimal point in a number. The location is that decimal
    /// point.
    #[display("A number can only have one decimal point")]
    SecondDecimalPoint,
    /// An `e` or `E` after the digits of a number. The location is the `e` or
    /// `E`.
    #[display("Scientific notation not allowed - write the number out in full")]
    ScientificNotation,
    /// A letter other than `e` or `E` after the digits of a number. The
    /// location is the letter.
    #[display("Numbers cannot have suffixes")]
    SuffixOnNumber,
    /// A `_`, or a `-` or `+` other than at the start, in a number. The
    /// location is that character.
    #[display("Numbers can only have digits, a leading minus sign and a decimal point")]
    InvalidCharacterInNumber,
    /// `-0` or `-0.0`.
    #[display("Negative zero is not allowed")]
    NegativeZero,
    /// `true` or `false` where a value belongs.
    #[display(
        "Boolean literals not supported - write the field's enum value, such as TRUE or FALSE for DCL's Boolean enum"
    )]
    BooleanNotSupported,
    /// A word that starts with a letter where a value belongs and has a
    /// lowercase letter.
    #[display("Enum values must be ALL_CAPS")]
    InvalidEnumCase,
}
