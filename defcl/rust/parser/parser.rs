//! The parser: a DCL file into its syntax tree.

use crate::scanner::Scanner;
use crate::syntax_error::{SyntaxError, SyntaxErrorKind};
use crate::syntax_tree::{
    Field, FieldName, MessageValue, ParsedFile, RepeatedValue, Scalar, TopLevelMessage, Value,
};
use source_rendering::{Position, SourceLocation};

const BYTE_ORDER_MARK: char = '\u{feff}';

/// Parses `source`, the text of a DCL file, into its syntax tree, or returns
/// the first syntax error in it.
///
/// # Errors
///
/// Returns the first syntax error in `source`.
pub fn parse(source: &str) -> Result<ParsedFile<'_>, SyntaxError> {
    Parser {
        scanner: Scanner::new(source),
    }
    .parse_file()
}

const fn is_field_name_start(byte: u8) -> bool {
    byte.is_ascii_alphanumeric() || byte == b'_'
}

/// Whether `byte` is part of the word that starts a field name, which may be
/// an invalid field name.
const fn is_field_name_word_character(byte: u8) -> bool {
    byte.is_ascii_alphanumeric() || matches!(byte, b'_' | b'-' | b'.')
}

/// Whether `byte` starts a number where a value belongs, which may be an
/// invalid number.
const fn is_number_start(byte: u8) -> bool {
    byte.is_ascii_digit() || matches!(byte, b'-' | b'+' | b'.')
}

const fn is_number_word_character(byte: u8) -> bool {
    byte.is_ascii_alphanumeric() || matches!(byte, b'_' | b'-' | b'+' | b'.')
}

const fn is_enum_word_character(byte: u8) -> bool {
    byte.is_ascii_alphanumeric() || byte == b'_'
}

/// ```ebnf
/// FIELD_NAME = lowercase_letter, { lowercase_letter | dec | ( "_", lowercase_letter ) } ;
/// ```
fn is_field_name(text: &str) -> bool {
    let bytes = text.as_bytes();
    if !bytes.first().is_some_and(u8::is_ascii_lowercase) {
        return false;
    }
    let mut index = 1;
    while let Some(&byte) = bytes.get(index) {
        if byte == b'_' {
            if !bytes.get(index + 1).is_some_and(u8::is_ascii_lowercase) {
                return false;
            }
            index += 2;
            continue;
        }
        if !byte.is_ascii_lowercase() && !byte.is_ascii_digit() {
            return false;
        }
        index += 1;
    }
    true
}

/// ```ebnf
/// enum_value = uppercase_letter, { uppercase_letter | dec | "_" } ;
/// ```
fn is_enum_value(text: &str) -> bool {
    let bytes = text.as_bytes();
    bytes.first().is_some_and(u8::is_ascii_uppercase)
        && bytes[1..]
            .iter()
            .all(|&byte| byte.is_ascii_uppercase() || byte.is_ascii_digit() || byte == b'_')
}

/// Returns the text after the `dec_lit` that starts `text`, if it starts
/// with one.
///
/// ```ebnf
/// dec_lit = "0" | ( dec - "0" ), { dec } ;
/// ```
fn after_decimal_literal(text: &str) -> Option<&str> {
    if let Some(rest) = text.strip_prefix('0') {
        return Some(rest);
    }
    if !text.as_bytes().first().is_some_and(u8::is_ascii_digit) {
        return None;
    }
    Some(text.trim_start_matches(|character: char| character.is_ascii_digit()))
}

/// ```ebnf
/// INTEGER = [ "-" ], dec_lit ;
/// ```
fn is_integer(text: &str) -> bool {
    after_decimal_literal(text.strip_prefix('-').unwrap_or(text)) == Some("")
}

/// ```ebnf
/// fraction = "0" | { dec }, ( dec - "0" ) ;
/// FLOAT = [ "-" ], dec_lit, ".", fraction ;
/// ```
fn is_float(text: &str) -> bool {
    let Some(fraction) = after_decimal_literal(text.strip_prefix('-').unwrap_or(text))
        .and_then(|rest| rest.strip_prefix('.'))
    else {
        return false;
    };
    if fraction == "0" {
        return true;
    }
    fraction.bytes().all(|byte| byte.is_ascii_digit())
        && fraction.bytes().last().is_some_and(|byte| byte != b'0')
}

/// The value of `digits`, digits in base `radix` that are all valid in it.
fn digits_value(digits: &str, radix: u32) -> u32 {
    digits
        .bytes()
        .fold(0, |value, digit| value * radix + hex_digit_value(digit))
}

/// The value of `digit`, a hex digit.
const fn hex_digit_value(digit: u8) -> u32 {
    (match digit {
        b'0'..=b'9' => digit - b'0',
        b'a'..=b'f' => digit - b'a' + 10,
        _ => digit - b'A' + 10,
    }) as u32
}

/// What an escape in a string stands for.
enum Escape {
    /// An octal or hex escape, which stands for one byte.
    Byte(u8),
    /// An escape that stands for a whole character.
    Character,
    /// A `\` at the end of the line.
    Unfinished,
}

/// The bytes of a run of back-to-back octal and hex escapes in a string.
/// Every other part of a string stands for whole characters, so each run must
/// be valid UTF-8 by itself.
struct ByteEscapeRun {
    bytes: Vec<u8>,
    /// Where the run's first escape starts.
    start: Position,
    /// The last character of the run's last escape.
    end: Position,
}

impl ByteEscapeRun {
    /// Adds the byte of the escape from `start` through `end`.
    fn push(&mut self, byte: u8, start: Position, end: Position) {
        if self.bytes.is_empty() {
            self.start = start;
        }
        self.bytes.push(byte);
        self.end = end;
    }

    /// Ends the run, if there is one.
    ///
    /// # Errors
    ///
    /// Returns an error if the run's bytes are not valid UTF-8.
    fn end(&mut self) -> Result<(), SyntaxError> {
        if self.bytes.is_empty() {
            return Ok(());
        }
        // The run's bytes are not valid UTF-8.
        if str::from_utf8(&self.bytes).is_err() {
            return Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidUtf8,
                location: SourceLocation {
                    start: self.start,
                    end: self.end,
                },
            });
        }
        self.bytes.clear();
        Ok(())
    }
}

#[derive(Clone, Copy)]
struct Parser<'source> {
    scanner: Scanner<'source>,
}

impl<'source> Parser<'source> {
    /// ```ebnf
    /// file = { WHITESPACE }, top_level_message, { WHITESPACE, top_level_message }, { WHITESPACE } ;
    /// ```
    fn parse_file(mut self) -> Result<ParsedFile<'source>, SyntaxError> {
        // The file starts with a byte order mark.
        if self.scanner.peek_character() == Some(BYTE_ORDER_MARK) {
            return Err(SyntaxError {
                kind: SyntaxErrorKind::ByteOrderMark,
                location: SourceLocation::at(self.scanner.position()),
            });
        }
        let mut top_level_messages = Vec::new();
        let mut has_whitespace = self.skip_whitespace()?;
        while let Some(byte) = self.scanner.peek() {
            // Something other than a field name starts where a top-level
            // message belongs.
            if !is_field_name_start(byte) {
                return Err(self.error_where_field_belongs(SyntaxErrorKind::ExpectedFieldName));
            }
            // The top-level message follows the one before it with no
            // whitespace between them.
            if !has_whitespace && !top_level_messages.is_empty() {
                return Err(SyntaxError {
                    kind: SyntaxErrorKind::MissingWhitespace,
                    location: SourceLocation::at(self.scanner.position()),
                });
            }
            top_level_messages.push(self.parse_top_level_message()?);
            has_whitespace = self.skip_whitespace()?;
        }
        // The file has no top-level message.
        if top_level_messages.is_empty() {
            return Err(SyntaxError {
                kind: SyntaxErrorKind::MissingTopLevelMessage,
                location: SourceLocation::at(self.scanner.position()),
            });
        }
        // The file does not end with a line feed. Only a line feed moves the
        // scanner to the first column, and the file is not empty.
        if self.scanner.position().column != 1 {
            return Err(SyntaxError {
                kind: SyntaxErrorKind::MissingTrailingNewline,
                location: SourceLocation::at(self.scanner.last_consumed()),
            });
        }
        Ok(ParsedFile { top_level_messages })
    }

    /// Consumes whitespace and comments, and returns whether there were any.
    ///
    /// ```ebnf
    /// COMMENT    = "#", { char - newline }, [ newline ] ;
    /// WHITESPACE = " " | newline ;
    /// ```
    fn skip_whitespace(&mut self) -> Result<bool, SyntaxError> {
        let start = self.scanner.offset();
        loop {
            match self.scanner.peek() {
                Some(b' ' | b'\n') => self.scanner.advance(),
                Some(b'#') => self.skip_comment()?,
                _ => return Ok(self.scanner.offset() != start),
            }
        }
    }

    /// Consumes a comment up to its line feed.
    fn skip_comment(&mut self) -> Result<(), SyntaxError> {
        loop {
            match self.scanner.peek() {
                None | Some(b'\n') => return Ok(()),
                // The comment has a NUL.
                Some(b'\0') => {
                    return Err(SyntaxError {
                        kind: SyntaxErrorKind::UnexpectedCharacter { character: '\0' },
                        location: SourceLocation::at(self.scanner.position()),
                    });
                }
                Some(_) => self.scanner.advance(),
            }
        }
    }

    /// Parses a top-level message, which starts at the scanner's position with
    /// a byte that may start a field name.
    ///
    /// ```ebnf
    /// top_level_message = FIELD_NAME, ":", " ", message_value ;
    /// ```
    fn parse_top_level_message(&mut self) -> Result<TopLevelMessage<'source>, SyntaxError> {
        let name = self.parse_field_name_and_colon()?;
        // The colon is not followed by a space.
        if !self.scanner.consume_byte(b' ') {
            return Err(self.missing_space_after_colon());
        }
        // The space after the colon is followed by more whitespace.
        if matches!(self.scanner.peek(), Some(b' ' | b'\n' | b'#')) {
            return Err(self.extra_whitespace_after_colon());
        }
        let value = self.parse_value()?;
        let Value::Message(value) = value else {
            return Err(SyntaxError {
                kind: SyntaxErrorKind::ScalarAtToplevel,
                location: value.location(),
            });
        };
        let location = SourceLocation {
            start: name.location.start,
            end: value.location.end,
        };
        Ok(TopLevelMessage {
            name,
            value,
            location,
        })
    }

    /// Parses a field, which starts at the scanner's position with a byte that
    /// may start a field name.
    ///
    /// ```ebnf
    /// field = FIELD_NAME, ":", [ WHITESPACE ], value ;
    /// ```
    fn parse_field(&mut self) -> Result<Field<'source>, SyntaxError> {
        let name = self.parse_field_name_and_colon()?;
        self.skip_whitespace()?;
        let value = self.parse_value()?;
        let location = SourceLocation {
            start: name.location.start,
            end: value.location().end,
        };
        Ok(Field {
            name,
            value,
            location,
        })
    }

    fn parse_field_name_and_colon(&mut self) -> Result<FieldName<'source>, SyntaxError> {
        let start = self.scanner.position();
        let text = self.scanner.consume_while(is_field_name_word_character);
        let location = SourceLocation {
            start,
            end: self.scanner.last_consumed(),
        };
        // The word where the field name belongs is not a valid field name.
        if !is_field_name(text) {
            return Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidFieldName,
                location,
            });
        }
        // The field name is not followed directly by a colon.
        if !self.scanner.consume_byte(b':') {
            return Err(self.missing_colon());
        }
        Ok(FieldName { text, location })
    }

    /// ```ebnf
    /// value = STRING | INTEGER | FLOAT | enum_value | message_value | repeated_value ;
    /// ```
    fn parse_value(&mut self) -> Result<Value<'source>, SyntaxError> {
        match self.scanner.peek() {
            Some(b'"') => self.parse_string(),
            Some(b'{') => Ok(Value::Message(self.parse_message_value()?)),
            Some(b'[') => Ok(Value::Repeated(self.parse_repeated_value()?)),
            Some(byte) if is_number_start(byte) => self.parse_number(),
            Some(byte) if byte.is_ascii_alphabetic() => self.parse_enum_value(),
            // Something other than a value is where a value belongs.
            _ => Err(self.unexpected(SyntaxErrorKind::ExpectedValue)),
        }
    }

    /// ```ebnf
    /// element = STRING | INTEGER | FLOAT | enum_value | message_value ;
    /// ```
    fn parse_element(&mut self) -> Result<Value<'source>, SyntaxError> {
        // A repeated value is an element of a repeated value.
        if self.scanner.peek() == Some(b'[') {
            return Err(SyntaxError {
                kind: SyntaxErrorKind::RepeatedValueInRepeatedValue,
                location: SourceLocation::at(self.scanner.position()),
            });
        }
        self.parse_value()
    }

    /// ```ebnf
    /// STRING = '"', { escape | char - '"' - newline - "\" }, '"' ;
    /// ```
    fn parse_string(&mut self) -> Result<Value<'source>, SyntaxError> {
        let start = self.scanner.position();
        let start_offset = self.scanner.offset();
        self.scanner.advance();
        let mut byte_escape_run = ByteEscapeRun {
            bytes: Vec::new(),
            start,
            end: start,
        };
        loop {
            match self.scanner.peek() {
                // The string has no closing quote on its line.
                None | Some(b'\n') => {
                    return Err(SyntaxError {
                        kind: SyntaxErrorKind::UnterminatedString,
                        location: SourceLocation {
                            start,
                            end: self.scanner.last_consumed(),
                        },
                    });
                }
                Some(b'"') => break,
                Some(b'\\') => {
                    let escape_start = self.scanner.position();
                    match self.consume_escape()? {
                        Escape::Byte(byte) => {
                            byte_escape_run.push(byte, escape_start, self.scanner.last_consumed());
                        }
                        Escape::Character => byte_escape_run.end()?,
                        Escape::Unfinished => {}
                    }
                }
                // The string has a NUL.
                Some(b'\0') => {
                    return Err(SyntaxError {
                        kind: SyntaxErrorKind::UnexpectedCharacter { character: '\0' },
                        location: SourceLocation::at(self.scanner.position()),
                    });
                }
                Some(_) => {
                    byte_escape_run.end()?;
                    self.scanner.advance();
                }
            }
        }
        byte_escape_run.end()?;
        self.scanner.advance();
        Ok(Value::String(Scalar {
            text: self.scanner.text_from(start_offset),
            location: SourceLocation {
                start,
                end: self.scanner.last_consumed(),
            },
        }))
    }

    /// Consumes an escape, which starts with the `\` at the scanner's
    /// position. A `\` at the end of the line is left for the string to
    /// report as unterminated.
    ///
    /// ```ebnf
    /// escape = "\a" | "\b" | "\f" | "\n" | "\r" | "\t" | "\v" | "\?" | "\\" | "\'" | '\"'
    ///        | "\", oct, [ oct, [ oct ] ]
    ///        | "\x", hex, [ hex ]
    ///        | "\u", hex, hex, hex, hex
    ///        | "\U000", hex, hex, hex, hex, hex
    ///        | "\U0010", hex, hex, hex, hex ;
    /// ```
    fn consume_escape(&mut self) -> Result<Escape, SyntaxError> {
        let start = self.scanner.position();
        self.scanner.advance();
        let Some(escaped) = self.scanner.peek() else {
            return Ok(Escape::Unfinished);
        };
        match escaped {
            b'\n' => Ok(Escape::Unfinished),
            b'a' | b'b' | b'f' | b'n' | b'r' | b't' | b'v' | b'?' | b'\\' | b'\'' | b'"' => {
                self.scanner.advance();
                Ok(Escape::Character)
            }
            b'0'..=b'7' => {
                let digits_offset = self.scanner.offset();
                self.scanner
                    .consume_up_to(3, |byte| matches!(byte, b'0'..=b'7'));
                let value = digits_value(self.scanner.text_from(digits_offset), 8);
                // The octal escape's value does not fit in a byte.
                let Ok(byte) = u8::try_from(value) else {
                    return Err(self.invalid_escape(start, SyntaxErrorKind::InvalidEscapeSequence));
                };
                Ok(Escape::Byte(byte))
            }
            b'x' => {
                self.scanner.advance();
                let digits_offset = self.scanner.offset();
                // The `\x` has no hex digit after it.
                if self
                    .scanner
                    .consume_up_to(2, |byte| byte.is_ascii_hexdigit())
                    == 0
                {
                    return Err(self.invalid_escape(start, SyntaxErrorKind::InvalidEscapeSequence));
                }
                #[expect(
                    clippy::cast_possible_truncation,
                    reason = "two hex digits always fit in a byte"
                )]
                let byte = digits_value(self.scanner.text_from(digits_offset), 16) as u8;
                Ok(Escape::Byte(byte))
            }
            b'u' => {
                self.scanner.advance();
                let digits_offset = self.scanner.offset();
                // The `\u` has fewer than four hex digits after it.
                if self
                    .scanner
                    .consume_up_to(4, |byte| byte.is_ascii_hexdigit())
                    < 4
                {
                    return Err(self.invalid_escape(start, SyntaxErrorKind::InvalidEscapeSequence));
                }
                // The `\u` escape is a surrogate, which is not a character.
                if (0xD800..=0xDFFF)
                    .contains(&digits_value(self.scanner.text_from(digits_offset), 16))
                {
                    return Err(self.invalid_escape(start, SyntaxErrorKind::SurrogateEscape));
                }
                Ok(Escape::Character)
            }
            b'U' => {
                self.scanner.advance();
                let digits_offset = self.scanner.offset();
                let count = self
                    .scanner
                    .consume_up_to(8, |byte| byte.is_ascii_hexdigit());
                let digits = self.scanner.text_from(digits_offset);
                // The `\U` does not have eight hex digits after it that start
                // with `000` or `0010`.
                if count < 8 || !(digits.starts_with("000") || digits.starts_with("0010")) {
                    return Err(self.invalid_escape(start, SyntaxErrorKind::InvalidEscapeSequence));
                }
                Ok(Escape::Character)
            }
            // The `\` is followed by a character that no escape starts with.
            _ => {
                self.scanner.advance();
                Err(self.invalid_escape(start, SyntaxErrorKind::InvalidEscapeSequence))
            }
        }
    }

    fn parse_number(&mut self) -> Result<Value<'source>, SyntaxError> {
        let start = self.scanner.position();
        let text = self.scanner.consume_while(is_number_word_character);
        let scalar = Scalar {
            text,
            location: SourceLocation {
                start,
                end: self.scanner.last_consumed(),
            },
        };
        // The number is a negative zero.
        if text == "-0" || text == "-0.0" {
            return Err(SyntaxError {
                kind: SyntaxErrorKind::NegativeZero,
                location: scalar.location,
            });
        }
        if is_integer(text) {
            return Ok(Value::Integer(scalar));
        }
        if is_float(text) {
            return Ok(Value::Float(scalar));
        }
        // The word that starts like a number is not an integer or a float.
        Err(SyntaxError {
            kind: SyntaxErrorKind::InvalidNumberFormat,
            location: scalar.location,
        })
    }

    fn parse_enum_value(&mut self) -> Result<Value<'source>, SyntaxError> {
        let start = self.scanner.position();
        let text = self.scanner.consume_while(is_enum_word_character);
        let location = SourceLocation {
            start,
            end: self.scanner.last_consumed(),
        };
        // The word is a boolean literal.
        if text == "true" || text == "false" {
            return Err(SyntaxError {
                kind: SyntaxErrorKind::BooleanNotSupported,
                location,
            });
        }
        // The word has a lowercase letter.
        if !is_enum_value(text) {
            return Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidEnumCase,
                location,
            });
        }
        Ok(Value::Enum(Scalar { text, location }))
    }

    /// ```ebnf
    /// message_value = "{", [ WHITESPACE ], [ field_list ], [ WHITESPACE ], "}" ;
    /// field_list = field, { WHITESPACE, field } ;
    /// ```
    fn parse_message_value(&mut self) -> Result<MessageValue<'source>, SyntaxError> {
        let start = self.scanner.position();
        self.scanner.advance();
        let mut fields = Vec::new();
        let mut has_whitespace = self.skip_whitespace()?;
        loop {
            match self.scanner.peek() {
                Some(b'}') => break,
                Some(byte) if is_field_name_start(byte) => {
                    // The field follows the one before it with no whitespace
                    // between them.
                    if !has_whitespace && !fields.is_empty() {
                        return Err(SyntaxError {
                            kind: SyntaxErrorKind::MissingWhitespace,
                            location: SourceLocation::at(self.scanner.position()),
                        });
                    }
                    fields.push(self.parse_field()?);
                    has_whitespace = self.skip_whitespace()?;
                }
                // The source ends before the message value's `}`.
                None => {
                    return Err(SyntaxError {
                        kind: SyntaxErrorKind::UnclosedMessage,
                        location: SourceLocation::at(start),
                    });
                }
                // Something other than a field name or a `}` is where a field
                // belongs.
                Some(_) => {
                    return Err(self.error_where_field_belongs(
                        SyntaxErrorKind::ExpectedFieldNameOrCloseBrace,
                    ));
                }
            }
        }
        self.scanner.advance();
        Ok(MessageValue {
            fields,
            location: SourceLocation {
                start,
                end: self.scanner.last_consumed(),
            },
        })
    }

    /// ```ebnf
    /// repeated_value = "[", [ WHITESPACE ], [ element_list ], [ WHITESPACE ], "]" ;
    /// element_list = element, { ",", [ WHITESPACE ], element } ;
    /// ```
    fn parse_repeated_value(&mut self) -> Result<RepeatedValue<'source>, SyntaxError> {
        let start = self.scanner.position();
        self.scanner.advance();
        let mut values = Vec::new();
        self.skip_whitespace()?;
        if !self.scanner.consume_byte(b']') {
            // The source ends before the repeated value's `]`.
            if self.scanner.is_at_end() {
                return Err(SyntaxError {
                    kind: SyntaxErrorKind::UnclosedRepeatedValue,
                    location: SourceLocation::at(start),
                });
            }
            loop {
                values.push(self.parse_element()?);
                if self.scanner.consume_byte(b',') {
                    self.skip_whitespace()?;
                    continue;
                }
                let whitespace_start = self.scanner.position();
                self.skip_whitespace()?;
                if self.scanner.consume_byte(b']') {
                    break;
                }
                return Err(self.error_after_repeated_element(start, whitespace_start));
            }
        }
        Ok(RepeatedValue {
            values,
            location: SourceLocation {
                start,
                end: self.scanner.last_consumed(),
            },
        })
    }
}

// The functions that only run on an error path.
impl Parser<'_> {
    /// The error for the field name at the scanner's position, which is not
    /// followed directly by a colon.
    #[cold]
    #[inline(never)]
    fn missing_colon(&self) -> SyntaxError {
        let after_name = self.scanner.position();
        let mut lookahead = *self;
        match lookahead.skip_whitespace() {
            Err(error) => return error,
            // Whitespace separates the field name from its colon.
            Ok(true) if lookahead.scanner.peek() == Some(b':') => {
                return SyntaxError {
                    kind: SyntaxErrorKind::WhitespaceBeforeColon,
                    location: SourceLocation {
                        start: after_name,
                        end: lookahead.scanner.last_consumed(),
                    },
                };
            }
            Ok(_) => {}
        }
        // Whitespace follows the field name where its colon belongs.
        if matches!(self.scanner.peek(), Some(b' ' | b'\n' | b'#')) {
            return SyntaxError {
                kind: SyntaxErrorKind::MissingColon,
                location: SourceLocation::at(after_name),
            };
        }
        self.unexpected(SyntaxErrorKind::MissingColon)
    }

    /// The error for what follows the colon of a top-level message, which is
    /// not a space.
    #[cold]
    #[inline(never)]
    fn missing_space_after_colon(&self) -> SyntaxError {
        // A line feed or a comment is where the space belongs.
        if matches!(self.scanner.peek(), Some(b'\n' | b'#')) {
            return SyntaxError {
                kind: SyntaxErrorKind::MissingSpaceAfterColon,
                location: SourceLocation::at(self.scanner.position()),
            };
        }
        self.unexpected(SyntaxErrorKind::MissingSpaceAfterColon)
    }

    /// The error for the whitespace and comments that follow the space after
    /// the colon of a top-level message.
    #[cold]
    #[inline(never)]
    fn extra_whitespace_after_colon(&self) -> SyntaxError {
        let start = self.scanner.position();
        let mut lookahead = *self;
        if let Err(error) = lookahead.skip_whitespace() {
            return error;
        }
        SyntaxError {
            kind: SyntaxErrorKind::ExtraWhitespaceAfterColon,
            location: SourceLocation {
                start,
                end: lookahead.scanner.last_consumed(),
            },
        }
    }

    /// The error for what follows a value in the repeated value that starts at
    /// `start`, when it is not a `,` or the `]`. Any whitespace after the
    /// value, which started at `whitespace_start`, has been consumed.
    #[cold]
    #[inline(never)]
    fn error_after_repeated_element(
        &self,
        start: Position,
        whitespace_start: Position,
    ) -> SyntaxError {
        // The source ends before the repeated value's `]`.
        if self.scanner.is_at_end() {
            return SyntaxError {
                kind: SyntaxErrorKind::UnclosedRepeatedValue,
                location: SourceLocation::at(start),
            };
        }
        // Whitespace separates the value from the `,` after it.
        if self.scanner.peek() == Some(b',') {
            return SyntaxError {
                kind: SyntaxErrorKind::WhitespaceBeforeComma,
                location: SourceLocation {
                    start: whitespace_start,
                    end: self.scanner.last_consumed(),
                },
            };
        }
        self.unexpected(SyntaxErrorKind::ExpectedCommaOrCloseBracket)
    }

    /// The error for the character at the scanner's position, where a field
    /// belongs.
    #[cold]
    #[inline(never)]
    fn error_where_field_belongs(&self, expected: SyntaxErrorKind) -> SyntaxError {
        // A comma separates fields.
        if self.scanner.peek() == Some(b',') {
            return SyntaxError {
                kind: SyntaxErrorKind::InvalidSeparator,
                location: SourceLocation::at(self.scanner.position()),
            };
        }
        self.unexpected(expected)
    }

    /// The error for the character at the scanner's position, which is not
    /// the start of what belongs there, or for the end of the source.
    /// `expected` is the kind of error for the end of the source and for a
    /// character that DCL allows elsewhere.
    #[cold]
    fn unexpected(&self, expected: SyntaxErrorKind) -> SyntaxError {
        let kind = match self.scanner.peek_character() {
            Some('\t') => SyntaxErrorKind::TabNotAllowed,
            Some('\r') => SyntaxErrorKind::CarriageReturnNotAllowed,
            Some(';') => SyntaxErrorKind::InvalidSeparator,
            Some('<') => SyntaxErrorKind::AngleBracketsNotAllowed,
            Some('\'') => return self.single_quotes_not_allowed(),
            Some(character)
                if !character.is_ascii_alphanumeric() && !"_-.\"{}[]:,".contains(character) =>
            {
                SyntaxErrorKind::UnexpectedCharacter { character }
            }
            _ => expected,
        };
        SyntaxError {
            kind,
            location: SourceLocation::at(self.scanner.position()),
        }
    }

    /// The error of the kind `kind` for the escape from `start` through the
    /// last character consumed.
    #[cold]
    #[inline(never)]
    const fn invalid_escape(&self, start: Position, kind: SyntaxErrorKind) -> SyntaxError {
        SyntaxError {
            kind,
            location: SourceLocation {
                start,
                end: self.scanner.last_consumed(),
            },
        }
    }

    /// The error for the `'` at the scanner's position, which covers the
    /// single-quoted string that it starts if its closing `'` is on the same
    /// line.
    #[cold]
    fn single_quotes_not_allowed(&self) -> SyntaxError {
        let start = self.scanner.position();
        let mut lookahead = self.scanner;
        lookahead.advance();
        loop {
            match lookahead.peek() {
                None | Some(b'\n') => {
                    return SyntaxError {
                        kind: SyntaxErrorKind::SingleQuotesNotAllowed,
                        location: SourceLocation::at(start),
                    };
                }
                Some(b'\'') => {
                    lookahead.advance();
                    return SyntaxError {
                        kind: SyntaxErrorKind::SingleQuotesNotAllowed,
                        location: SourceLocation {
                            start,
                            end: lookahead.last_consumed(),
                        },
                    };
                }
                Some(_) => lookahead.advance(),
            }
        }
    }
}
