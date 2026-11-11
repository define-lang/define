//! The parser: a DCL file into its syntax tree.

use crate::scanner::{Scanner, invisible_syntax_reason};
use crate::syntax_error::{SyntaxError, SyntaxErrorKind};
use crate::syntax_tree::{
    Field, FieldName, MessageValue, ParsedFile, RepeatedValue, Scalar, TopLevelMessage, Value,
};
use source_characters::{
    DisallowedCharacter, DisallowedReason, Neighbors, TextKind, disallowed_characters,
    disallowed_reason, first_disallowed_character,
};
use source_rendering::{Position, SourceLocation};

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

/// A replacement for the bytes of a DCL file from `start` up to `end` that
/// fixes the layout errors in them.
#[derive(Debug, PartialEq, Eq)]
pub struct LayoutFix {
    pub start: usize,
    pub end: usize,
    pub replacement: String,
}

/// Bytes of a DCL file that are not valid UTF-8, with the syntax error that
/// reports them.
#[derive(Debug, PartialEq, Eq)]
pub struct DecodeError {
    pub source: Vec<u8>,
    pub error: SyntaxError,
}

/// Decodes `source`, the bytes of a DCL file, into its text.
///
/// # Errors
///
/// Returns the bytes with an `InvalidEncoding` error if they are not valid
/// UTF-8.
pub fn decode(source: Vec<u8>) -> Result<String, DecodeError> {
    String::from_utf8(source).map_err(|error| {
        let syntax_error = invalid_encoding(error.as_bytes(), error.utf8_error().valid_up_to());
        DecodeError {
            source: error.into_bytes(),
            error: syntax_error,
        }
    })
}

/// Parses `source`, the text of a DCL file, into its syntax tree and its
/// syntax errors. An error in the layout of the file, such as its whitespace,
/// does not stop the parse; any other syntax error does.
#[must_use]
pub fn parse(source: &str) -> ParseResult<'_> {
    parse_with(source, false).0
}

/// Parses `source`, the text of a DCL file, as `parse` does, and also returns
/// the fixes for its layout errors that only change its whitespace and
/// comments, in source order.
#[must_use]
pub fn parse_with_layout_fixes(source: &str) -> (ParseResult<'_>, Vec<LayoutFix>) {
    parse_with(source, true)
}

/// Parses `source`, and records the fixes for its layout errors if
/// `records_fixes`.
fn parse_with(source: &str, records_fixes: bool) -> (ParseResult<'_>, Vec<LayoutFix>) {
    let mut parser = Parser {
        scanner: Scanner::new(source),
        errors: Vec::new(),
        records_fixes,
        fixes: Vec::new(),
        invisible_characters: 0,
        reported_carriage_return: false,
        reported_indentation_tab: false,
    };
    let file = match parser.parse_file() {
        Ok(file) => Some(file),
        Err(error) => {
            parser.errors.push(error);
            None
        }
    };
    (
        ParseResult {
            file,
            errors: parser.errors,
        },
        parser.fixes,
    )
}

/// The error for the byte at `offset` in `source`, which starts the first
/// bytes that are not valid UTF-8.
#[cold]
#[inline(never)]
fn invalid_encoding(source: &[u8], offset: usize) -> SyntaxError {
    let mut position = Position { line: 1, column: 1 };
    for &byte in &source[..offset] {
        if byte == b'\n' {
            position = Position {
                line: position.line + 1,
                column: 1,
            };
        } else if byte & 0b1100_0000 != 0b1000_0000 {
            // A column counts characters, so it skips the bytes that continue
            // one.
            position.column += 1;
        }
    }
    SyntaxError {
        kind: SyntaxErrorKind::InvalidEncoding {
            byte: source[offset],
        },
        location: Some(SourceLocation::at(position)),
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

/// Whether `text` is a valid field name.
///
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

/// The kind of syntax error in `text`, a word of field name characters that
/// starts with a byte that may start a field name and that `is_field_name`
/// rejects, and the byte offset of the character that it is about.
#[cold]
#[inline(never)]
fn field_name_error(text: &str) -> (usize, SyntaxErrorKind) {
    let bytes = text.as_bytes();
    for (index, &byte) in bytes.iter().enumerate() {
        // The field name has an uppercase letter.
        if byte.is_ascii_uppercase() {
            return (index, SyntaxErrorKind::UppercaseInFieldName);
        }
        // The field name starts with something other than a letter.
        if index == 0 && !byte.is_ascii_lowercase() {
            return (index, SyntaxErrorKind::FieldNameStartsWithNonLetter);
        }
        // The field name has an underscore that a lowercase letter does not
        // follow.
        if byte == b'_' && !bytes.get(index + 1).is_some_and(u8::is_ascii_lowercase) {
            return (index, SyntaxErrorKind::UnderscoreNotBeforeLetter);
        }
        // The field name has a `-` or a `.`.
        if matches!(byte, b'-' | b'.') {
            return (index, SyntaxErrorKind::InvalidCharacterInFieldName);
        }
    }
    unreachable!("is_field_name rejected the field name {text:?}")
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

/// The kind of syntax error in `text`, a word of number characters that
/// starts with a byte that may start a number and that is neither an integer,
/// a float nor a negative zero, and the byte offset of the character that it is
/// about.
#[cold]
#[inline(never)]
fn number_error(text: &str) -> (usize, SyntaxErrorKind) {
    let bytes = text.as_bytes();
    let mut index = 0;
    // The number starts with a plus sign.
    if bytes[0] == b'+' {
        return (0, SyntaxErrorKind::PlusSignInNumber);
    }
    if bytes[0] == b'-' {
        // The minus sign is not followed by digits or a decimal point.
        if !bytes
            .get(1)
            .is_some_and(|&byte| byte.is_ascii_digit() || byte == b'.')
        {
            return (0, SyntaxErrorKind::MinusSignWithoutDigits);
        }
        index = 1;
    }
    // The number has no digit before its decimal point.
    if bytes[index] == b'.' {
        return (index, SyntaxErrorKind::MissingDigitBeforeDecimalPoint);
    }
    if bytes[index] == b'0' {
        // The number is hexadecimal.
        if matches!(bytes.get(index + 1), Some(b'x' | b'X')) {
            return (index, SyntaxErrorKind::HexadecimalNumber);
        }
        // The number has a leading zero.
        if bytes.get(index + 1).is_some_and(u8::is_ascii_digit) {
            return (index, SyntaxErrorKind::LeadingZeroInNumber);
        }
    }
    index += digit_count(&bytes[index..]);
    if bytes.get(index) == Some(&b'.') {
        let point = index;
        index += 1;
        let fraction_length = digit_count(&bytes[index..]);
        // The decimal point has no digit after it.
        if fraction_length == 0 {
            return (point, SyntaxErrorKind::MissingDigitAfterDecimalPoint);
        }
        index += fraction_length;
        // The fraction ends the number, and ends with a zero.
        if index == bytes.len() {
            return (index - 1, SyntaxErrorKind::TrailingZeroInFraction);
        }
    }
    let kind = match bytes.get(index) {
        // The number has a second decimal point.
        Some(b'.') => SyntaxErrorKind::SecondDecimalPoint,
        // The number is in scientific notation.
        Some(b'e' | b'E') => SyntaxErrorKind::ScientificNotation,
        // The number has a suffix.
        Some(byte) if byte.is_ascii_alphabetic() => SyntaxErrorKind::SuffixOnNumber,
        // The number has another character that numbers do not have.
        Some(_) => SyntaxErrorKind::InvalidCharacterInNumber,
        None => unreachable!("{text:?} is a valid number"),
    };
    (index, kind)
}

/// The number of ASCII digits that `bytes` starts with.
fn digit_count(bytes: &[u8]) -> usize {
    bytes
        .iter()
        .take_while(|byte| byte.is_ascii_digit())
        .count()
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
                location: Some(SourceLocation {
                    start: self.start,
                    end: self.end,
                }),
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
    /// Whether the parse records the fixes for its layout errors.
    records_fixes: bool,
    /// The fixes for the layout errors so far, if the parse records them.
    fixes: Vec<LayoutFix>,
    /// How many invisible characters outside strings the parse has skipped so
    /// far, each of which a fix deletes.
    invisible_characters: usize,
    /// Whether the file has an error for a carriage return so far.
    reported_carriage_return: bool,
    /// Whether the file has an error for a tab that starts a line so far.
    reported_indentation_tab: bool,
}

/// Whether `comment`, the text after the `#` at `hash`, has text, and where
/// the spaces at its end start, if it ends with any. A fix deletes a character
/// that comments do not allow, so such a character is neither text nor space.
fn comment_text_and_trailing_spaces(hash: Position, comment: &str) -> (bool, Option<Position>) {
    let text_start = hash.next_column();
    // Nearly every comment is printable ASCII, whose characters are its bytes.
    if is_printable_ascii(comment) {
        let text = comment.trim_matches(' ');
        let text_end = comment.trim_end_matches(' ').len();
        let trailing_start = (text_end < comment.len()).then(|| text_start.columns_later(text_end));
        return (!text.is_empty(), trailing_start);
    }
    let mut has_text = false;
    let mut trailing_start = None;
    let mut position = text_start;
    for character in comment.chars() {
        if character == ' ' {
            trailing_start.get_or_insert(position);
        } else if !is_disallowed_in_comment(character) {
            has_text = true;
            trailing_start = None;
        }
        position = position.next_column();
    }
    (has_text, trailing_start)
}

/// Whether comments do not allow `character` wherever it is. A joiner or
/// variation selector is allowed between visible characters, which a comment
/// line's spacing does not depend on, so it counts as not allowed.
fn is_disallowed_in_comment(character: char) -> bool {
    disallowed_reason(character, TextKind::Comment, Neighbors::NONE).is_some()
}

/// The kind of error for `character`, an invisible character outside a string
/// that is not allowed for the reason `reason`.
const fn invisible_character_kind(character: char, reason: DisallowedReason) -> SyntaxErrorKind {
    if character == '\t' {
        return SyntaxErrorKind::TabNotAllowed;
    }
    match reason {
        DisallowedReason::ByteOrderMark => SyntaxErrorKind::ByteOrderMark,
        DisallowedReason::CarriageReturn => SyntaxErrorKind::CarriageReturnNotAllowed,
        DisallowedReason::Control => SyntaxErrorKind::ControlCharacter { character },
        DisallowedReason::Invisible => SyntaxErrorKind::InvisibleCharacter { character },
    }
}

/// Whether `text` has only printable ASCII characters, which every comment and
/// string allows.
fn is_printable_ascii(text: &str) -> bool {
    // Checking every byte without stopping early lets the compiler check many
    // at once.
    text.bytes()
        .fold(true, |all, byte| all & matches!(byte, b' '..=b'~'))
}

/// The error for `found`, a character that a comment or a string does not
/// allow.
const fn disallowed_character_error(found: DisallowedCharacter) -> SyntaxError {
    let character = found.character;
    let kind = match found.reason {
        DisallowedReason::ByteOrderMark => SyntaxErrorKind::ByteOrderMark,
        DisallowedReason::CarriageReturn => SyntaxErrorKind::CarriageReturnNotAllowed,
        DisallowedReason::Control => SyntaxErrorKind::ControlCharacter { character },
        DisallowedReason::Invisible => SyntaxErrorKind::InvisibleCharacter { character },
    };
    SyntaxError {
        kind,
        location: Some(SourceLocation::at(found.position)),
    }
}

/// `comment`, the text of a comment, without the characters that comments do
/// not allow.
fn without_disallowed_characters(comment: &str) -> String {
    let start = Position { line: 1, column: 1 };
    // The comment has no line feed, so the column of each character tells
    // which character it is.
    let disallowed: Vec<u32> = disallowed_characters(start, comment, TextKind::Comment)
        .map(|found| found.position.column)
        .collect();
    let mut kept = String::with_capacity(comment.len());
    for (column, character) in (1..).zip(comment.chars()) {
        if !disallowed.contains(&column) {
            kept.push(character);
        }
    }
    kept
}

/// The spaces of `level` levels of indentation.
const fn indentation(level: u32) -> u32 {
    level * INDENTATION_WIDTH
}

/// Appends the spaces of `level` levels of indentation to `text`.
fn push_indentation(text: &mut String, level: u32) {
    for _ in 0..indentation(level) {
        text.push(' ');
    }
}

impl<'source> Parser<'source> {
    /// ```ebnf
    /// file = { comment_line }, top_level_message, { line_break(0), top_level_message }, line_break(0) ;
    /// ```
    fn parse_file(&mut self) -> Result<ParsedFile<'source>, SyntaxError> {
        let mut top_level_messages = Vec::new();
        while let Some(byte) =
            self.line_break_before(0, |next| next.is_none_or(is_field_name_start))
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
                location: None,
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
    ) -> Option<u8> {
        let mut lookahead = self.scanner;
        lookahead.skip_whitespace();
        let next = lookahead.peek();
        if is_expected(next) {
            self.expect_line_break(level);
        } else {
            self.scanner = lookahead;
        }
        next
    }

    /// Consumes the whitespace and comments before the next field or element
    /// of a block whose fields or elements are indented `level` levels, or
    /// before the block's closing `}` or `]`, which is indented one level
    /// less. The top-level messages are a block of level 0 that the end of the
    /// file closes. Records an error for each way that they are not a line
    /// feed, then comment lines indented `level` levels, then the next token's
    /// indentation.
    ///
    /// ```ebnf
    /// line_break(level) = newline, { comment_line(level) }, indentation(level) ;
    /// comment_line(level) = indentation(level), "#", [ " ", comment_text ], newline ;
    /// comment_text = ( char - " " - newline ), [ { char - newline }, ( char - " " - newline ) ] ;
    /// ```
    fn expect_line_break(&mut self, level: u32) {
        let start = self.scanner.offset();
        let errors = self.errors.len();
        let invisible_characters = self.invisible_characters;
        self.check_line_break(level);
        // A carriage return or a tab that starts a line may have no error of
        // its own, since a file gets only one for each, but is still deleted.
        if self.records_fixes
            && (self.errors.len() > errors || self.invisible_characters > invisible_characters)
        {
            self.fix_line_break(start, level);
        }
    }

    /// Records the fix for the whitespace and comments from the byte `start`
    /// up to the scanner's position, which `expect_line_break(level)` found
    /// errors in: a line feed, unless they start the file, then each comment
    /// on a line of its own, then the next token's indentation.
    #[cold]
    #[inline(never)]
    fn fix_line_break(&mut self, start: usize, level: u32) {
        let mut replacement = String::new();
        if start != 0 {
            replacement.push('\n');
        }
        for line in self.scanner.text_from(start).split('\n') {
            // Only spaces and invisible characters come before a comment's
            // `#` among whitespace.
            let Some(hash) = line.find('#') else {
                continue;
            };
            push_indentation(&mut replacement, level);
            replacement.push('#');
            let comment = without_disallowed_characters(&line[hash + 1..]);
            // Spaces at the start of the text are part of it, such as to draw
            // a diagram, so only the space after the `#` is added.
            let text = comment.trim_end_matches(' ');
            if !text.is_empty() {
                if !text.starts_with(' ') {
                    replacement.push(' ');
                }
                replacement.push_str(text);
            }
            replacement.push('\n');
        }
        match self.scanner.peek() {
            None => {}
            Some(b'}' | b']') => push_indentation(&mut replacement, level.saturating_sub(1)),
            Some(_) => push_indentation(&mut replacement, level),
        }
        self.push_fix(start, replacement);
    }

    /// Records the fix that replaces the bytes from `start` up to the
    /// scanner's position with `replacement`, if the parse records fixes.
    fn push_fix(&mut self, start: usize, replacement: String) {
        if self.records_fixes {
            self.fixes.push(LayoutFix {
                start,
                end: self.scanner.offset(),
                replacement,
            });
        }
    }

    /// Checks the whitespace and comments for `expect_line_break(level)`.
    fn check_line_break(&mut self, level: u32) {
        // The file starts at the start of a line, and everything else that
        // comes before whitespace ends on the line it starts on.
        if self.scanner.position().column != 1 && !self.finish_line() {
            return;
        }
        loop {
            let line_start = self.scanner.position();
            let spaces = self.consume_spaces_and_invisible_characters(true);
            match self.scanner.peek() {
                // The line has nothing but spaces.
                Some(b'\n') => {
                    self.scanner.advance();
                    self.errors.push(SyntaxError {
                        kind: SyntaxErrorKind::BlankLine,
                        location: Some(self.location_from(line_start)),
                    });
                }
                // The file ends with spaces after its last line feed.
                None if spaces > 0 => {
                    self.errors.push(SyntaxError {
                        kind: SyntaxErrorKind::TrailingWhitespace,
                        location: Some(self.location_from(line_start)),
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
                            location: Some(SourceLocation::at(self.scanner.last_consumed())),
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
        let spaces = self.consume_spaces_and_invisible_characters(false);
        match self.scanner.peek() {
            Some(b'\n') => {
                // The line ends with spaces.
                if spaces > 0 {
                    self.errors.push(SyntaxError {
                        kind: SyntaxErrorKind::TrailingWhitespace,
                        location: Some(self.location_from(spaces_start)),
                    });
                }
            }
            // A comment follows something else on its line.
            Some(b'#') => {
                let comment_start = self.scanner.position();
                let comment_offset = self.scanner.offset();
                self.skip_to_line_end();
                self.errors.push(SyntaxError {
                    kind: SyntaxErrorKind::CommentNotOnOwnLine,
                    location: Some(self.location_from(comment_start)),
                });
                let comment = &self.scanner.text_from(comment_offset)[1..];
                self.check_comment_characters(comment_start, comment);
            }
            // The file does not end with a line feed.
            None => {
                self.errors.push(SyntaxError {
                    kind: SyntaxErrorKind::MissingTrailingNewline,
                    location: Some(SourceLocation::at(self.scanner.last_consumed())),
                });
                return false;
            }
            // The next token is on the same line as the one before it.
            Some(_) => {
                self.errors.push(SyntaxError {
                    kind: SyntaxErrorKind::MissingLineBreak,
                    location: Some(SourceLocation::at(self.scanner.position())),
                });
                return false;
            }
        }
        // The file does not end with a line feed after the comment.
        if !self.scanner.consume_byte(b'\n') {
            self.errors.push(SyntaxError {
                kind: SyntaxErrorKind::MissingTrailingNewline,
                location: Some(SourceLocation::at(self.scanner.last_consumed())),
            });
            return false;
        }
        true
    }

    /// Consumes everything up to the next line feed or the end of the source.
    fn skip_to_line_end(&mut self) {
        let _: &str = self.scanner.consume_to_line_end();
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
                location: Some(location),
            });
        }
    }

    /// Consumes the comment that starts with the `#` at the scanner's position
    /// on a line of its own, up to its line feed. Records an error if the `#`
    /// is followed directly by text, without a space between them, if the
    /// comment ends with spaces, and for each character that comments do not
    /// allow. The comment must have no carriage return.
    fn consume_comment_line(&mut self) {
        let hash = self.scanner.position();
        self.scanner.advance();
        let comment = self.scanner.consume_to_line_end();
        let (has_text, trailing_start) = comment_text_and_trailing_spaces(hash, comment);
        // The comment's text follows its `#` with no space between them.
        if has_text && !comment.starts_with(' ') {
            self.errors.push(SyntaxError {
                kind: SyntaxErrorKind::CommentSpacing,
                location: Some(SourceLocation::at(hash)),
            });
        }
        // The comment ends with spaces.
        if let Some(start) = trailing_start {
            self.errors.push(SyntaxError {
                kind: SyntaxErrorKind::TrailingWhitespace,
                location: Some(self.location_from(start)),
            });
        }
        // Comments allow every printable ASCII character, so only other
        // characters need checking, which keeps the check out of the parse
        // of nearly every comment.
        if !is_printable_ascii(comment) {
            self.check_comment_characters(hash, comment);
        }
    }

    /// Records an error for each character that comments do not allow in
    /// `comment`, the text after the `#` at `hash`.
    fn check_comment_characters(&mut self, hash: Position, comment: &str) {
        for found in disallowed_characters(hash.next_column(), comment, TextKind::Comment) {
            self.record_invisible_character(found.position, found.character, found.reason, false);
        }
    }

    /// Records an error for each invisible character among the whitespace and
    /// comments from `start`, the byte `start_offset`, up to the scanner's
    /// position, and for each character that comments do not allow in the
    /// comments among them.
    fn check_skipped_characters(&mut self, start: Position, start_offset: usize) {
        let mut position = start;
        for line in self.scanner.text_from(start_offset).split_inclusive('\n') {
            let (blank, comment) = match line.find('#') {
                Some(hash) => (&line[..hash], Some(&line[hash + 1..])),
                None => (line, None),
            };
            for character in blank.chars() {
                if character != '\n'
                    && let Some(reason) = invisible_syntax_reason(character)
                {
                    self.record_invisible_character(position, character, reason, false);
                }
                position = position.next_column();
            }
            if let Some(comment) = comment {
                self.check_comment_characters(position, comment.trim_end_matches('\n'));
            }
            position = Position {
                line: position.line + 1,
                column: 1,
            };
        }
    }

    /// Records the error for `character` at `position`, an invisible
    /// character outside a string that is not allowed for the reason `reason`
    /// and that a fix deletes. `starts_line` is whether only spaces and
    /// invisible characters come before it on its line.
    #[cold]
    #[inline(never)]
    fn record_invisible_character(
        &mut self,
        position: Position,
        character: char,
        reason: DisallowedReason,
        starts_line: bool,
    ) {
        self.invisible_characters += 1;
        // Carriage returns and tabs that start lines come from an editor's
        // settings for a whole file, so only the first of each gets an error.
        if character == '\r' {
            if self.reported_carriage_return {
                return;
            }
            self.reported_carriage_return = true;
        }
        if character == '\t' && starts_line {
            if self.reported_indentation_tab {
                return;
            }
            self.reported_indentation_tab = true;
        }
        self.errors.push(SyntaxError {
            kind: invisible_character_kind(character, reason),
            location: Some(SourceLocation::at(position)),
        });
    }

    /// Consumes the spaces and invisible characters at the scanner's
    /// position, records an error for each invisible character, and returns
    /// how many spaces there were. `starts_line` is whether they start a line.
    #[inline(always)]
    fn consume_spaces_and_invisible_characters(&mut self, starts_line: bool) -> usize {
        let mut spaces = self.scanner.consume_spaces();
        while let Some((character, reason)) = self.scanner.peek_invisible_character() {
            let position = self.scanner.position();
            self.record_invisible_character(position, character, reason, starts_line);
            self.scanner.advance_character(character);
            spaces += self.scanner.consume_spaces();
        }
        spaces
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
    /// `separator`. Records a `MisplacedComment` error if there were comments,
    /// or else an error of the kind `kind` if there was whitespace, and an
    /// error for each invisible character.
    fn skip_misplaced_whitespace_before(&mut self, separator: u8, kind: SyntaxErrorKind) {
        let start = self.scanner.position();
        let start_offset = self.scanner.offset();
        let mut lookahead = self.scanner;
        let comments = lookahead.skip_whitespace_locating_comments();
        if lookahead.offset() == start_offset || lookahead.peek() != Some(separator) {
            return;
        }
        self.scanner = lookahead;
        if let Some(location) = comments {
            self.errors.push(SyntaxError {
                kind: SyntaxErrorKind::MisplacedComment,
                location: Some(location),
            });
            self.check_skipped_characters(start, start_offset);
            return;
        }
        // Invisible characters alone get only their own errors.
        if self.scanner.text_from(start_offset).contains([' ', '\n']) {
            self.errors.push(SyntaxError {
                kind,
                location: Some(self.location_from(start)),
            });
        }
        self.check_skipped_characters(start, start_offset);
        self.push_fix(start_offset, String::new());
    }

    /// Consumes the whitespace and comments after a field's colon, where
    /// exactly one space belongs, and, if they are followed by what may start
    /// a value, records a `MisplacedComment` error if there were comments, or
    /// else an error if the whitespace other than invisible characters is not
    /// one space, and an error for each invisible character.
    fn expect_one_space(&mut self) {
        let start = self.scanner.position();
        let start_offset = self.scanner.offset();
        let comments = self.scanner.skip_whitespace_locating_comments();
        if !self
            .scanner
            .peek()
            .is_some_and(|byte| byte == b'[' || is_element_start(byte))
        {
            return;
        }
        if let Some(location) = comments {
            self.errors.push(SyntaxError {
                kind: SyntaxErrorKind::MisplacedComment,
                location: Some(location),
            });
            self.check_skipped_characters(start, start_offset);
            return;
        }
        let whitespace = self.scanner.text_from(start_offset);
        if whitespace == " " {
            return;
        }
        let is_one_space = whitespace
            .chars()
            .filter(|&character| matches!(character, ' ' | '\n'))
            .eq([' ']);
        if !is_one_space {
            let location = if whitespace.is_empty() {
                SourceLocation::at(start)
            } else {
                self.location_from(start)
            };
            self.errors.push(SyntaxError {
                kind: SyntaxErrorKind::WrongSpacingAfterColon,
                location: Some(location),
            });
        }
        self.check_skipped_characters(start, start_offset);
        self.push_fix(start_offset, " ".to_owned());
    }

    /// Consumes a message value or a repeated value whose opening `{` or `[`
    /// is at `start` and has been consumed, if it has nothing but whitespace
    /// and comments before `close`, and records an error of the kind `kind`
    /// for it. Returns whether it did.
    fn skip_empty_block(&mut self, start: Position, close: u8, kind: SyntaxErrorKind) -> bool {
        let whitespace_start = self.scanner.position();
        let whitespace_offset = self.scanner.offset();
        let mut lookahead = self.scanner;
        lookahead.skip_whitespace();
        if !lookahead.consume_byte(close) {
            return false;
        }
        self.scanner = lookahead;
        self.errors.push(SyntaxError {
            kind,
            location: Some(self.location_from(start)),
        });
        self.check_skipped_characters(whitespace_start, whitespace_offset);
        true
    }

    /// Parses a top-level message, which starts at the scanner's position with
    /// a byte that may start a field name.
    ///
    /// ```ebnf
    /// top_level_message = FIELD_NAME, ":", " ", message_value(0) ;
    /// ```
    fn parse_top_level_message(&mut self) -> Result<TopLevelMessage<'source>, SyntaxError> {
        let name = self.parse_field_name_and_colon()?;
        self.expect_one_space();
        let value = self.parse_value(0)?;
        let Value::Message(value) = value else {
            return Err(SyntaxError {
                kind: SyntaxErrorKind::ScalarAtToplevel,
                location: Some(value.location()),
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
        self.expect_one_space();
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

    /// Parses a field name and the colon after it, which start at the
    /// scanner's position with a byte that may start a field name.
    ///
    /// ```ebnf
    /// FIELD_NAME = lowercase_letter, { lowercase_letter | dec | ( "_", lowercase_letter ) } ;
    /// field_name_and_colon = FIELD_NAME, ":" ;
    /// ```
    fn parse_field_name_and_colon(&mut self) -> Result<FieldName<'source>, SyntaxError> {
        let start = self.scanner.position();
        let text = self.scanner.consume_while(is_field_name_word_character);
        // An invisible character splits the word.
        if let Some(error) = self.invisible_character_in_word(is_field_name_word_character) {
            return Err(error);
        }
        let location = SourceLocation {
            start,
            end: self.scanner.last_consumed(),
        };
        // The word where the field name belongs is not a valid field name.
        if !is_field_name(text) {
            let (index, kind) = field_name_error(text);
            return Err(SyntaxError {
                kind,
                location: Some(SourceLocation::at(start.columns_later(index))),
            });
        }
        self.skip_misplaced_whitespace_before(b':', SyntaxErrorKind::WhitespaceBeforeColon);
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
                location: Some(SourceLocation::at(self.scanner.position())),
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
                        location: Some(SourceLocation {
                            start,
                            end: self.scanner.last_consumed(),
                        }),
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
                Some(_) => {
                    byte_escape_run.end()?;
                    self.scanner.advance();
                }
            }
        }
        let content = &self.scanner.text_from(start_offset)[1..];
        // Strings allow every printable ASCII character, so only a string with
        // other characters needs checking. The string has a character that
        // strings do not allow.
        if !is_printable_ascii(content)
            && let Some(found) =
                first_disallowed_character(start.next_column(), content, TextKind::LiteralContent)
        {
            return Err(disallowed_character_error(found));
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

    /// Parses a number, which starts at the scanner's position with a byte
    /// that may start one.
    ///
    /// ```ebnf
    /// INTEGER = ( [ "-" ], dec_lit ) - "-0" ;
    /// FLOAT = ( [ "-" ], dec_lit, ".", fraction ) - "-0.0" ;
    /// dec_lit = "0" | ( dec - "0" ), { dec } ;
    /// fraction = "0" | { dec }, ( dec - "0" ) ;
    /// ```
    fn parse_number(&mut self) -> Result<Value<'source>, SyntaxError> {
        let start = self.scanner.position();
        let text = self.scanner.consume_while(is_number_word_character);
        // An invisible character splits the word.
        if let Some(error) = self.invisible_character_in_word(is_number_word_character) {
            return Err(error);
        }
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
                location: Some(scalar.location),
            });
        }
        if is_integer(text) {
            return Ok(Value::Integer(scalar));
        }
        if is_float(text) {
            return Ok(Value::Float(scalar));
        }
        // The word that starts like a number is not an integer or a float.
        let (index, kind) = number_error(text);
        Err(SyntaxError {
            kind,
            location: Some(SourceLocation::at(start.columns_later(index))),
        })
    }

    /// Parses an enum value, which starts at the scanner's position with a
    /// letter.
    ///
    /// ```ebnf
    /// enum_value = uppercase_letter, { uppercase_letter | dec | "_" } ;
    /// ```
    fn parse_enum_value(&mut self) -> Result<Value<'source>, SyntaxError> {
        let start = self.scanner.position();
        let text = self.scanner.consume_while(is_enum_word_character);
        // An invisible character splits the word.
        if let Some(error) = self.invisible_character_in_word(is_enum_word_character) {
            return Err(error);
        }
        let location = SourceLocation {
            start,
            end: self.scanner.last_consumed(),
        };
        // The word is a boolean literal.
        if text == "true" || text == "false" {
            return Err(SyntaxError {
                kind: SyntaxErrorKind::BooleanNotSupported,
                location: Some(location),
            });
        }
        // The word has a lowercase letter.
        if !is_enum_value(text) {
            return Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidEnumCase,
                location: Some(location),
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
        if !self.skip_empty_block(start, b'}', SyntaxErrorKind::EmptyMessageValue) {
            loop {
                let next = self.line_break_before(level + 1, |next| {
                    next == Some(b'}') || next.is_some_and(is_field_name_start)
                });
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
                            location: Some(SourceLocation::at(start)),
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
        if !self.skip_empty_block(start, b']', SyntaxErrorKind::EmptyRepeatedValue) {
            loop {
                // The source ends before the repeated value's `]`.
                if self
                    .line_break_before(level + 1, |next| next.is_some_and(is_element_start))
                    .is_none()
                {
                    return Err(SyntaxError {
                        kind: SyntaxErrorKind::UnclosedRepeatedValue,
                        location: Some(SourceLocation::at(start)),
                    });
                }
                values.push(self.parse_element(level + 1)?);
                self.skip_misplaced_whitespace_before(b',', SyntaxErrorKind::WhitespaceBeforeComma);
                if self.scanner.consume_byte(b',') {
                    continue;
                }
                self.line_break_before(level + 1, |next| next == Some(b']'));
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
                location: Some(SourceLocation::at(self.scanner.position())),
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
        // The source ends before the repeated value's `}`.
        if self.scanner.is_at_end() {
            return SyntaxError {
                kind: SyntaxErrorKind::UnclosedRepeatedValue,
                location: Some(SourceLocation::at(start)),
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
                kind: SyntaxErrorKind::CommaBetweenFields,
                location: Some(SourceLocation::at(self.scanner.position())),
            };
        }
        self.unexpected(expected)
    }

    /// The error for the invisible characters at the scanner's position, if
    /// there are any and `is_word_character` accepts the character after them,
    /// so that they split a word such as a field name in two. The error is for
    /// the first of them.
    #[inline(always)]
    fn invisible_character_in_word(
        &self,
        is_word_character: fn(u8) -> bool,
    ) -> Option<SyntaxError> {
        let (character, reason) = self.scanner.peek_invisible_character()?;
        self.invisible_character_splitting_word(character, reason, is_word_character)
    }

    /// `invisible_character_in_word` for `character`, the invisible character
    /// at the scanner's position, which is not allowed for the reason `reason`.
    #[cold]
    #[inline(never)]
    fn invisible_character_splitting_word(
        &self,
        character: char,
        reason: DisallowedReason,
        is_word_character: fn(u8) -> bool,
    ) -> Option<SyntaxError> {
        let mut lookahead = self.scanner;
        lookahead.advance_character(character);
        while let Some((next, _)) = lookahead.peek_invisible_character() {
            lookahead.advance_character(next);
        }
        if !lookahead.peek().is_some_and(is_word_character) {
            return None;
        }
        Some(SyntaxError {
            kind: invisible_character_kind(character, reason),
            location: Some(SourceLocation::at(self.scanner.position())),
        })
    }

    /// The error for the character at the scanner's position, which is not
    /// the start of what belongs there, or for the end of the source.
    /// `expected` is the kind of error for the end of the source and for a
    /// character that DCL allows elsewhere.
    #[cold]
    fn unexpected(&self, expected: SyntaxErrorKind) -> SyntaxError {
        let kind = match self.scanner.peek_character() {
            Some(';') => SyntaxErrorKind::SemicolonNotAllowed,
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
            location: Some(SourceLocation::at(self.scanner.position())),
        }
    }

    /// The error of the kind `kind` for the escape from `start` through the
    /// last character consumed.
    #[cold]
    #[inline(never)]
    const fn invalid_escape(&self, start: Position, kind: SyntaxErrorKind) -> SyntaxError {
        SyntaxError {
            kind,
            location: Some(SourceLocation {
                start,
                end: self.scanner.last_consumed(),
            }),
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
                        location: Some(SourceLocation::at(start)),
                    };
                }
                Some(b'\'') => {
                    lookahead.advance();
                    return SyntaxError {
                        kind: SyntaxErrorKind::SingleQuotesNotAllowed,
                        location: Some(SourceLocation {
                            start,
                            end: lookahead.last_consumed(),
                        }),
                    };
                }
                Some(_) => lookahead.advance(),
            }
        }
    }
}
