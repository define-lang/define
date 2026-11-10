//! The parser: a DCL file into its syntax tree.

use crate::scanner::Scanner;
use crate::syntax_error::{SyntaxError, SyntaxErrorKind};
use crate::syntax_tree::{
    Field, FieldName, MessageValue, ParsedFile, RepeatedValue, Scalar, TopLevelMessage, Value,
};
use source_rendering::{Position, SourceLocation};

const BYTE_ORDER_MARK: char = '\u{feff}';

/// The spaces of one level of indentation.
const INDENTATION_WIDTH: u32 = 2;

/// The syntax tree of a DCL file, and its syntax errors.
#[derive(Debug, PartialEq, Eq)]
pub struct ParseResult<'source> {
    /// The syntax tree, unless a syntax error stopped the parse.
    pub file: Option<ParsedFile<'source>>,
    /// Every syntax error found, in the order found. If a syntax error stopped
    /// the parse, it is the last.
    pub errors: Vec<SyntaxError>,
}

/// Parses `source`, the text of a DCL file, into its syntax tree and its
/// syntax errors. An error in the layout of the file, such as its whitespace,
/// does not stop the parse; any other syntax error does.
#[must_use]
pub fn parse(source: &str) -> ParseResult<'_> {
    let mut parser = Parser {
        scanner: Scanner::new(source),
        errors: Vec::new(),
    };
    let file = match parser.parse_file() {
        Ok(file) => Some(file),
        Err(error) => {
            parser.errors.push(error);
            None
        }
    };
    ParseResult {
        file,
        errors: parser.errors,
    }
}

const fn is_field_name_start(byte: u8) -> bool {
    byte.is_ascii_alphanumeric() || byte == b'_'
}

/// Whether `byte` is part of the word that starts a field name, which may be
/// an invalid field name.
const fn is_field_name_word_character(byte: u8) -> bool {
    byte.is_ascii_alphanumeric() || matches!(byte, b'_' | b'-' | b'.')
}

/// Whether `byte` starts an element of a repeated value, which may be an
/// invalid one, other than a repeated value.
const fn is_element_start(byte: u8) -> bool {
    matches!(byte, b'"' | b'{') || is_number_start(byte) || byte.is_ascii_alphabetic()
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

struct Parser<'source> {
    scanner: Scanner<'source>,
    /// The errors in the layout of the file so far, which do not stop the
    /// parse.
    errors: Vec<SyntaxError>,
}

/// Consumes whitespace and comments at `scanner`'s position, and returns
/// whether there were any.
///
/// ```ebnf
/// COMMENT    = "#", { char - newline }, [ newline ] ;
/// WHITESPACE = " " | newline ;
/// ```
fn skip_whitespace(scanner: &mut Scanner<'_>) -> Result<bool, SyntaxError> {
    let start = scanner.offset();
    loop {
        match scanner.peek() {
            Some(b' ' | b'\n') => scanner.advance(),
            Some(b'#') => skip_comment(scanner)?,
            _ => return Ok(scanner.offset() != start),
        }
    }
}

/// Consumes a comment up to its line feed.
fn skip_comment(scanner: &mut Scanner<'_>) -> Result<(), SyntaxError> {
    loop {
        match scanner.peek() {
            None | Some(b'\n') => return Ok(()),
            // The comment has a NUL.
            Some(b'\0') => {
                return Err(SyntaxError {
                    kind: SyntaxErrorKind::UnexpectedCharacter { character: '\0' },
                    location: SourceLocation::at(scanner.position()),
                });
            }
            Some(_) => scanner.advance(),
        }
    }
}

/// The spaces of `level` levels of indentation.
const fn indentation(level: u32) -> u32 {
    level * INDENTATION_WIDTH
}

impl<'source> Parser<'source> {
    /// ```ebnf
    /// file = { comment_line }, top_level_message, { line_break(0), top_level_message }, line_break(0) ;
    /// ```
    fn parse_file(&mut self) -> Result<ParsedFile<'source>, SyntaxError> {
        // The file starts with a byte order mark.
        if self.scanner.peek_character() == Some(BYTE_ORDER_MARK) {
            return Err(SyntaxError {
                kind: SyntaxErrorKind::ByteOrderMark,
                location: SourceLocation::at(self.scanner.position()),
            });
        }
        let mut top_level_messages = Vec::new();
        while let Some(byte) =
            self.line_break_before(0, |next| next.is_none_or(is_field_name_start))?
        {
            // Something other than a field name starts where a top-level
            // message belongs.
            if !is_field_name_start(byte) {
                return Err(self.error_where_field_belongs(SyntaxErrorKind::ExpectedFieldName));
            }
            top_level_messages.push(self.parse_top_level_message()?);
        }
        // The file has no top-level message.
        if top_level_messages.is_empty() {
            return Err(SyntaxError {
                kind: SyntaxErrorKind::MissingTopLevelMessage,
                location: SourceLocation::at(self.scanner.position()),
            });
        }
        Ok(ParsedFile { top_level_messages })
    }

    /// Consumes the whitespace and comments before the next token, and returns
    /// its first byte, or `None` at the end of the source. Checks them as
    /// `expect_line_break(level)` does if `is_expected` accepts that byte, so
    /// that a token that is a syntax error is not also reported as out of
    /// place.
    fn line_break_before(
        &mut self,
        level: u32,
        is_expected: impl Fn(Option<u8>) -> bool,
    ) -> Result<Option<u8>, SyntaxError> {
        let mut lookahead = self.scanner;
        // The whitespace and comments have no NUL if this succeeds, so
        // checking them cannot fail.
        skip_whitespace(&mut lookahead)?;
        let next = lookahead.peek();
        if is_expected(next) {
            self.expect_line_break(level);
        } else {
            self.scanner = lookahead;
        }
        Ok(next)
    }

    /// Consumes the whitespace and comments before the next field or element
    /// of a block whose fields or elements are indented `level` levels, or
    /// before the block's closing `}` or `]`, which is indented one level
    /// less. The top-level messages are a block of level 0 that the end of the
    /// file closes. Records an error for each way that they are not a line
    /// feed, then comment lines indented `level` levels, then the next token's
    /// indentation. The whitespace and comments must have no NUL.
    ///
    /// ```ebnf
    /// line_break(level) = newline, { comment_line(level) }, indentation(level) ;
    /// comment_line(level) = indentation(level), "#", [ " ", comment_text ], newline ;
    /// comment_text = ( char - " " - newline ), [ { char - newline }, ( char - " " - "\t" - newline ) ] ;
    /// ```
    fn expect_line_break(&mut self, level: u32) {
        // The file starts at the start of a line, and everything else that
        // comes before whitespace ends on the line it starts on.
        if self.scanner.position().column != 1 && !self.finish_line() {
            return;
        }
        loop {
            let line_start = self.scanner.position();
            let spaces = self.scanner.consume_spaces();
            match self.scanner.peek() {
                // The line has nothing but spaces.
                Some(b'\n') => {
                    self.scanner.advance();
                    self.errors.push(SyntaxError {
                        kind: SyntaxErrorKind::BlankLine,
                        location: self.location_from(line_start),
                    });
                }
                // The file ends with spaces after its last line feed.
                None if spaces > 0 => {
                    self.errors.push(SyntaxError {
                        kind: SyntaxErrorKind::TrailingWhitespace,
                        location: self.location_from(line_start),
                    });
                    return;
                }
                None => return,
                Some(b'#') => {
                    self.check_indentation(line_start, spaces, indentation(level));
                    self.consume_comment_line();
                    // The file ends without a line feed after the comment.
                    if !self.scanner.consume_byte(b'\n') {
                        self.errors.push(SyntaxError {
                            kind: SyntaxErrorKind::MissingTrailingNewline,
                            location: SourceLocation::at(self.scanner.last_consumed()),
                        });
                        return;
                    }
                }
                Some(byte) => {
                    let token_level = if matches!(byte, b'}' | b']') {
                        level.saturating_sub(1)
                    } else {
                        level
                    };
                    self.check_indentation(line_start, spaces, indentation(token_level));
                    return;
                }
            }
        }
    }

    /// Consumes the rest of the line that the scanner is in the middle of,
    /// where only its line feed belongs, and returns whether it ended with
    /// one. Records an error for each thing other than the line feed.
    fn finish_line(&mut self) -> bool {
        let spaces_start = self.scanner.position();
        let spaces = self.scanner.consume_spaces();
        match self.scanner.peek() {
            Some(b'\n') => {
                // The line ends with spaces.
                if spaces > 0 {
                    self.errors.push(SyntaxError {
                        kind: SyntaxErrorKind::TrailingWhitespace,
                        location: self.location_from(spaces_start),
                    });
                }
            }
            // A comment follows something else on its line.
            Some(b'#') => {
                let comment_start = self.scanner.position();
                self.skip_to_line_end();
                self.errors.push(SyntaxError {
                    kind: SyntaxErrorKind::CommentNotOnOwnLine,
                    location: self.location_from(comment_start),
                });
            }
            // The file does not end with a line feed.
            None => {
                self.errors.push(SyntaxError {
                    kind: SyntaxErrorKind::MissingTrailingNewline,
                    location: SourceLocation::at(self.scanner.last_consumed()),
                });
                return false;
            }
            // The next token is on the same line as the one before it.
            Some(_) => {
                self.errors.push(SyntaxError {
                    kind: SyntaxErrorKind::MissingLineBreak,
                    location: SourceLocation::at(self.scanner.position()),
                });
                return false;
            }
        }
        // The file does not end with a line feed after the comment.
        if !self.scanner.consume_byte(b'\n') {
            self.errors.push(SyntaxError {
                kind: SyntaxErrorKind::MissingTrailingNewline,
                location: SourceLocation::at(self.scanner.last_consumed()),
            });
            return false;
        }
        true
    }

    /// Consumes everything up to the next line feed or the end of the source.
    fn skip_to_line_end(&mut self) {
        while self.scanner.peek().is_some_and(|byte| byte != b'\n') {
            self.scanner.advance();
        }
    }

    /// Records an error if `spaces`, the spaces that start the line that
    /// starts at `line_start`, are not `expected` spaces.
    fn check_indentation(&mut self, line_start: Position, spaces: usize, expected: u32) {
        if spaces != expected as usize {
            let location = if spaces == 0 {
                SourceLocation::at(line_start)
            } else {
                self.location_from(line_start)
            };
            self.errors.push(SyntaxError {
                kind: SyntaxErrorKind::WrongIndentation {
                    expected_spaces: expected,
                },
                location,
            });
        }
    }

    /// Consumes the comment that starts with the `#` at the scanner's position
    /// on a line of its own, up to its line feed. Records an error if the `#`
    /// is followed directly by text, without a space between them, and if the
    /// comment ends with spaces or tabs. The comment must have no NUL.
    fn consume_comment_line(&mut self) {
        let hash = self.scanner.position();
        self.scanner.advance();
        let spaces = self.scanner.consume_spaces();
        // Where the spaces and tabs at the end of the comment so far start.
        let mut trailing_start = (spaces > 0).then(|| hash.next_column());
        let mut has_text = false;
        loop {
            match self.scanner.peek() {
                None | Some(b'\n') => break,
                Some(b' ' | b'\t') => {
                    trailing_start.get_or_insert_with(|| self.scanner.position());
                    self.scanner.advance();
                }
                Some(_) => {
                    has_text = true;
                    trailing_start = None;
                    self.scanner.advance();
                }
            }
        }
        // The comment's text follows its `#` with no space between them.
        if has_text && spaces == 0 {
            self.errors.push(SyntaxError {
                kind: SyntaxErrorKind::CommentSpacing,
                location: SourceLocation::at(hash),
            });
        }
        // The comment ends with spaces or tabs.
        if let Some(start) = trailing_start {
            self.errors.push(SyntaxError {
                kind: SyntaxErrorKind::TrailingWhitespace,
                location: self.location_from(start),
            });
        }
    }

    /// The location from `start` through the last character consumed.
    const fn location_from(&self, start: Position) -> SourceLocation {
        SourceLocation {
            start,
            end: self.scanner.last_consumed(),
        }
    }

    /// Consumes the whitespace and comments between a field name and its
    /// colon, or between an element of a repeated value and the comma after
    /// it, where nothing belongs, if the next character after them is
    /// `separator`. Records an error of the kind `kind` if there were any.
    fn skip_misplaced_whitespace_before(
        &mut self,
        separator: u8,
        kind: SyntaxErrorKind,
    ) -> Result<(), SyntaxError> {
        let start = self.scanner.position();
        let mut lookahead = self.scanner;
        if !skip_whitespace(&mut lookahead)? || lookahead.peek() != Some(separator) {
            return Ok(());
        }
        self.scanner = lookahead;
        self.errors.push(SyntaxError {
            kind,
            location: self.location_from(start),
        });
        Ok(())
    }

    /// Consumes the whitespace and comments after a field's colon, where
    /// exactly one space belongs, and records an error if they are anything
    /// else and are followed by what may start a value.
    fn expect_one_space(&mut self) -> Result<(), SyntaxError> {
        let start = self.scanner.position();
        let start_offset = self.scanner.offset();
        skip_whitespace(&mut self.scanner)?;
        if !self
            .scanner
            .peek()
            .is_some_and(|byte| byte == b'[' || is_element_start(byte))
        {
            return Ok(());
        }
        let whitespace = self.scanner.text_from(start_offset);
        if whitespace == " " {
            return Ok(());
        }
        let location = if whitespace.is_empty() {
            SourceLocation::at(start)
        } else {
            self.location_from(start)
        };
        self.errors.push(SyntaxError {
            kind: SyntaxErrorKind::WrongSpacingAfterColon,
            location,
        });
        Ok(())
    }

    /// Consumes a message value or a repeated value whose opening `{` or `[`
    /// is at `start` and has been consumed, if it has nothing but whitespace
    /// and comments before `close`, and records an error of the kind `kind`
    /// for it. Returns whether it did.
    fn skip_empty_block(
        &mut self,
        start: Position,
        close: u8,
        kind: SyntaxErrorKind,
    ) -> Result<bool, SyntaxError> {
        let mut lookahead = self.scanner;
        skip_whitespace(&mut lookahead)?;
        if !lookahead.consume_byte(close) {
            return Ok(false);
        }
        self.scanner = lookahead;
        self.errors.push(SyntaxError {
            kind,
            location: self.location_from(start),
        });
        Ok(true)
    }

    /// Parses a top-level message, which starts at the scanner's position with
    /// a byte that may start a field name.
    ///
    /// ```ebnf
    /// top_level_message = FIELD_NAME, ":", " ", message_value(0) ;
    /// ```
    fn parse_top_level_message(&mut self) -> Result<TopLevelMessage<'source>, SyntaxError> {
        let name = self.parse_field_name_and_colon()?;
        self.expect_one_space()?;
        let value = self.parse_value(0)?;
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

    /// Parses a field indented `level` levels, which starts at the scanner's
    /// position with a byte that may start a field name.
    ///
    /// ```ebnf
    /// field(level) = FIELD_NAME, ":", " ", value(level) ;
    /// ```
    fn parse_field(&mut self, level: u32) -> Result<Field<'source>, SyntaxError> {
        let name = self.parse_field_name_and_colon()?;
        self.expect_one_space()?;
        let value = self.parse_value(level)?;
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
        self.skip_misplaced_whitespace_before(b':', SyntaxErrorKind::WhitespaceBeforeColon)?;
        // The field name is not followed by a colon.
        if !self.scanner.consume_byte(b':') {
            return Err(self.missing_colon());
        }
        Ok(FieldName { text, location })
    }

    /// Parses a value on a line indented `level` levels.
    ///
    /// ```ebnf
    /// value(level) = STRING | INTEGER | FLOAT | enum_value | message_value(level) | repeated_value(level) ;
    /// ```
    fn parse_value(&mut self, level: u32) -> Result<Value<'source>, SyntaxError> {
        match self.scanner.peek() {
            Some(b'"') => self.parse_string(),
            Some(b'{') => Ok(Value::Message(self.parse_message_value(level)?)),
            Some(b'[') => Ok(Value::Repeated(self.parse_repeated_value(level)?)),
            Some(byte) if is_number_start(byte) => self.parse_number(),
            Some(byte) if byte.is_ascii_alphabetic() => self.parse_enum_value(),
            // Something other than a value is where a value belongs.
            _ => Err(self.unexpected(SyntaxErrorKind::ExpectedValue)),
        }
    }

    /// Parses an element of a repeated value, on a line indented `level`
    /// levels.
    ///
    /// ```ebnf
    /// element(level) = STRING | INTEGER | FLOAT | enum_value | message_value(level) ;
    /// ```
    fn parse_element(&mut self, level: u32) -> Result<Value<'source>, SyntaxError> {
        // A repeated value is an element of a repeated value.
        if self.scanner.peek() == Some(b'[') {
            return Err(SyntaxError {
                kind: SyntaxErrorKind::RepeatedValueInRepeatedValue,
                location: SourceLocation::at(self.scanner.position()),
            });
        }
        self.parse_value(level)
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

    /// Parses a message value on a line indented `level` levels, whose fields
    /// are indented one level more.
    ///
    /// ```ebnf
    /// message_value(level) = "{", line_break(level + 1), field(level + 1),
    ///     { line_break(level + 1), field(level + 1) }, line_break(level + 1), "}" ;
    /// ```
    fn parse_message_value(&mut self, level: u32) -> Result<MessageValue<'source>, SyntaxError> {
        let start = self.scanner.position();
        self.scanner.advance();
        let mut fields = Vec::new();
        if !self.skip_empty_block(start, b'}', SyntaxErrorKind::EmptyMessageValue)? {
            loop {
                let next = self.line_break_before(level + 1, |next| {
                    next == Some(b'}') || next.is_some_and(is_field_name_start)
                })?;
                match next {
                    Some(b'}') => {
                        self.scanner.advance();
                        break;
                    }
                    Some(byte) if is_field_name_start(byte) => {
                        fields.push(self.parse_field(level + 1)?);
                    }
                    // The source ends before the message value's `}`.
                    None => {
                        return Err(SyntaxError {
                            kind: SyntaxErrorKind::UnclosedMessage,
                            location: SourceLocation::at(start),
                        });
                    }
                    // Something other than a field name or a `}` is where a
                    // field belongs.
                    Some(_) => {
                        return Err(self.error_where_field_belongs(
                            SyntaxErrorKind::ExpectedFieldNameOrCloseBrace,
                        ));
                    }
                }
            }
        }
        Ok(MessageValue {
            fields,
            location: self.location_from(start),
        })
    }

    /// Parses a repeated value on a line indented `level` levels, whose
    /// elements are indented one level more.
    ///
    /// ```ebnf
    /// repeated_value(level) = "[", line_break(level + 1), element(level + 1),
    ///     { ",", line_break(level + 1), element(level + 1) }, line_break(level + 1), "]" ;
    /// ```
    fn parse_repeated_value(&mut self, level: u32) -> Result<RepeatedValue<'source>, SyntaxError> {
        let start = self.scanner.position();
        self.scanner.advance();
        let mut values = Vec::new();
        if !self.skip_empty_block(start, b']', SyntaxErrorKind::EmptyRepeatedValue)? {
            loop {
                // The source ends before the repeated value's `]`.
                if self
                    .line_break_before(level + 1, |next| next.is_some_and(is_element_start))?
                    .is_none()
                {
                    return Err(SyntaxError {
                        kind: SyntaxErrorKind::UnclosedRepeatedValue,
                        location: SourceLocation::at(start),
                    });
                }
                values.push(self.parse_element(level + 1)?);
                self.skip_misplaced_whitespace_before(
                    b',',
                    SyntaxErrorKind::WhitespaceBeforeComma,
                )?;
                if self.scanner.consume_byte(b',') {
                    continue;
                }
                self.line_break_before(level + 1, |next| next == Some(b']'))?;
                if self.scanner.consume_byte(b']') {
                    break;
                }
                return Err(self.error_after_repeated_element(start));
            }
        }
        Ok(RepeatedValue {
            values,
            location: self.location_from(start),
        })
    }
}

// The functions that only run on an error path.
impl Parser<'_> {
    /// The error for the field name before the scanner's position, which is
    /// not followed by a colon, even after whitespace.
    #[cold]
    #[inline(never)]
    fn missing_colon(&self) -> SyntaxError {
        // Whitespace follows the field name where its colon belongs.
        if matches!(self.scanner.peek(), Some(b' ' | b'\n' | b'#')) {
            return SyntaxError {
                kind: SyntaxErrorKind::MissingColon,
                location: SourceLocation::at(self.scanner.position()),
            };
        }
        self.unexpected(SyntaxErrorKind::MissingColon)
    }

    /// The error for what follows an element of the repeated value that starts
    /// at `start`, at the scanner's position after any whitespace, when it is
    /// not a `,` or the `]`.
    #[cold]
    #[inline(never)]
    fn error_after_repeated_element(&self, start: Position) -> SyntaxError {
        // The source ends before the repeated value's `]`.
        if self.scanner.is_at_end() {
            return SyntaxError {
                kind: SyntaxErrorKind::UnclosedRepeatedValue,
                location: SourceLocation::at(start),
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
