//! The characters that Define does not allow, and the syntax errors for them.

// Everything here runs only after parsing has already failed, or after a
// vector scan has found text that is not printable ASCII, such as a comment in
// a language other than English. Source that is printable ASCII never comes
// here.

use crate::parse_error::{ParseError, ParseResult};
use crate::parser_diagnostics::ParserDiagnostics;
use crate::scanner::Scanner;
use crate::syntax_errors::SyntaxErrors;
pub use source_characters::TextKind;
use source_characters::{DisallowedCharacter, DisallowedReason, Neighbors, disallowed_reason};
use source_rendering::{Position, escape_invisible};
use std::fmt::Write as _;

/// Returns the error for the first character in `text`, which begins at
/// `start` and has no line feed, that `kind` does not allow.
pub fn first_disallowed_character(
    errors: &SyntaxErrors,
    start: Position,
    text: &[u8],
    kind: TextKind,
) -> Option<ParseError> {
    let (valid, invalid) = split_at_invalid_bytes(text);
    if let Some(found) = source_characters::first_disallowed_character(start, valid, kind) {
        return Some(character_error(errors, found));
    }
    invalid_bytes_error(errors, start, valid, invalid)
}

/// Adds a diagnostic for each byte order mark, control character, and
/// invisible character that comments do not allow in `comment`, which begins
/// at `start` and has no line feed, and returns the error for the first
/// carriage return or bytes that are not valid UTF-8 in it, if it has one.
pub fn check_comment_characters(
    errors: &SyntaxErrors,
    diagnostics: &mut ParserDiagnostics,
    start: Position,
    comment: &[u8],
) -> ParseResult<()> {
    let (valid, invalid) = split_at_invalid_bytes(comment);
    for found in source_characters::disallowed_characters(start, valid, TextKind::Comment) {
        if let Some(error) = add_comment_character_diagnostic(errors, diagnostics, found) {
            return Err(error);
        }
    }
    invalid_bytes_error(errors, start, valid, invalid).map_or(Ok(()), Err)
}

/// The characters of `text` up to its first bytes that are not valid UTF-8,
/// and those bytes, which are empty if it has none.
fn split_at_invalid_bytes(text: &[u8]) -> (&str, &[u8]) {
    // Only the last chunk can end without invalid bytes, so the first chunk
    // ends either with the first invalid bytes or with the text.
    text.utf8_chunks()
        .next()
        .map_or(("", &[]), |chunk| (chunk.valid(), chunk.invalid()))
}

/// Returns the error for `invalid`, the bytes that are not valid UTF-8 after
/// the characters `valid` that begin at `start`, if there are any.
fn invalid_bytes_error(
    errors: &SyntaxErrors,
    start: Position,
    valid: &str,
    invalid: &[u8],
) -> Option<ParseError> {
    if invalid.is_empty() {
        return None;
    }
    let position = start.columns_later(valid.chars().count());
    Some(invalid_encoding(errors, position, invalid))
}

/// Returns the error for `found`, a character that a kind of text does not
/// allow.
fn character_error(errors: &SyntaxErrors, found: DisallowedCharacter) -> ParseError {
    let position = found.position;
    // The errors show the character as text.
    let mut buffer = [0; 4];
    let character = &*found.character.encode_utf8(&mut buffer);
    match found.reason {
        DisallowedReason::ByteOrderMark => {
            errors.byte_order_mark_error(position, position, &escape_invisible(character))
        }
        DisallowedReason::CarriageReturn => {
            errors.carriage_return_error(position, position, &escape_invisible(character))
        }
        DisallowedReason::Control => {
            errors.control_character_error(position, position, &escape_invisible(character))
        }
        DisallowedReason::Invisible => {
            errors.invisible_character_error(position, position, character)
        }
    }
}

/// Adds the diagnostic for `found`, a character that comments do not allow,
/// and returns the error if it must stop the parse instead.
fn add_comment_character_diagnostic(
    errors: &SyntaxErrors,
    diagnostics: &mut ParserDiagnostics,
    found: DisallowedCharacter,
) -> Option<ParseError> {
    let position = found.position;
    // The diagnostics show the character as text.
    let mut buffer = [0; 4];
    let text = &*found.character.encode_utf8(&mut buffer);
    let added = match found.reason {
        DisallowedReason::ByteOrderMark => {
            diagnostics.byte_order_mark_in_comment_diagnostic(position, position)
        }
        DisallowedReason::Control => diagnostics.control_character_in_comment_diagnostic(
            position,
            position,
            &escape_invisible(text),
        ),
        DisallowedReason::Invisible => {
            diagnostics.invisible_character_in_comment_diagnostic(position, position, text)
        }
        // Carriage returns come from the line endings of a whole file, so they
        // stop the parse instead of getting a diagnostic on every line.
        DisallowedReason::CarriageReturn => {
            return Some(character_error(errors, found));
        }
    };
    added.err().map(ParseError::from)
}

/// Returns the error for the character `offset` bytes, which are ASCII, past
/// the scanner's position, where the syntax there went wrong, if no syntax may
/// have it.
#[cold]
pub fn disallowed_character_ahead(
    errors: &SyntaxErrors,
    scanner: &Scanner,
    offset: usize,
) -> Option<ParseError> {
    let start = scanner.position;
    let position = start.columns_later(offset);
    disallowed_first_character(errors, position, &scanner.rest_of_line().bytes[offset..])
}

/// Returns the error for the first character of `text`, which begins at
/// `position` and has no line feed, if no syntax may have it.
#[cold]
pub fn disallowed_first_character(
    errors: &SyntaxErrors,
    position: Position,
    text: &[u8],
) -> Option<ParseError> {
    let chunk = text.utf8_chunks().next()?;
    let Some(character) = chunk.valid().chars().next() else {
        return Some(invalid_encoding(errors, position, chunk.invalid()));
    };
    let neighbors = Neighbors {
        previous: None,
        next: None,
    };
    let reason = disallowed_reason(character, TextKind::Syntax, neighbors)?;
    Some(character_error(
        errors,
        DisallowedCharacter {
            position,
            character,
            reason,
        },
    ))
}

/// Returns the error for the bytes at `position` that are not valid UTF-8.
#[cold]
#[inline(never)]
fn invalid_encoding(errors: &SyntaxErrors, position: Position, bytes: &[u8]) -> ParseError {
    // The bytes are not characters, so the error shows them as escapes.
    let mut escaped = String::with_capacity(bytes.len() * 4);
    for byte in bytes {
        // Writing to a String cannot fail.
        let _ = write!(escaped, "\\x{byte:02x}");
    }
    errors.invalid_encoding_error(position, position, &escaped)
}
