//! The characters that Define does not allow, and the syntax errors for them.

// Everything here runs only after parsing has already failed, or after a
// vector scan has found text that is not printable ASCII, such as a comment in
// a language other than English. Source that is printable ASCII never comes
// here, so this decodes and checks characters one at a time instead of
// vectorizing.

mod invisible_ranges;

use crate::parse_error::{ParseError, ParseResult};
use crate::parser_diagnostics::ParserDiagnostics;
use crate::scanner::{Position, Scanner};
use crate::syntax_errors::SyntaxErrors;
use invisible_ranges::INVISIBLE_RANGES;

const BYTE_ORDER_MARK: char = '\u{feff}';
const CARRIAGE_RETURN: char = '\r';
/// The direction marks, which only comments may have.
const DIRECTION_MARKS: [char; 3] = ['\u{061c}', '\u{200e}', '\u{200f}'];
/// Variation selectors 15 and 16, which may only follow a visible character.
const VARIATION_SELECTORS: [char; 2] = ['\u{fe0e}', '\u{fe0f}'];
/// The zero width non-joiner and joiner, which may only come between a visible
/// character or variation selector and a visible character.
const JOINERS: [char; 2] = ['\u{200c}', '\u{200d}'];

/// The kind of text that characters are in, which decides which characters
/// it may have.
#[derive(Clone, Copy, PartialEq, Eq)]
pub enum TextKind {
    /// Syntax with semantics. Its errors are for characters that no syntax may
    /// have; any other character that does not belong is a syntax error.
    Syntax,
    Name,
    LiteralContent,
    Comment,
}

/// Why a kind of text does not allow a character.
#[derive(Clone, Copy)]
enum DisallowedCharacter {
    ByteOrderMark,
    CarriageReturn,
    Control,
    Invisible,
}

/// Returns the error for the first character in `text`, which begins at
/// `start` and has no line feed, that `kind` does not allow.
pub fn first_disallowed_character(
    errors: &SyntaxErrors,
    start: Position,
    text: &[u8],
    kind: TextKind,
) -> Option<ParseError> {
    find_disallowed(
        start,
        text,
        kind,
        |position, character, disallowed| {
            Some(character_error(errors, position, character, disallowed))
        },
        |position, bytes| invalid_encoding(errors, position, bytes),
    )
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
    let error = find_disallowed(
        start,
        comment,
        TextKind::Comment,
        |position, character, disallowed| {
            add_comment_character_diagnostic(errors, diagnostics, position, character, disallowed)
        },
        |position, bytes| invalid_encoding(errors, position, bytes),
    );
    error.map_or(Ok(()), Err)
}

/// Calls `found` with each character in `text`, which begins at `start` and
/// has no line feed, that `kind` does not allow, and `invalid` with the first
/// bytes that are not valid UTF-8, and returns the first result of either.
fn find_disallowed<'text>(
    start: Position,
    text: &'text [u8],
    kind: TextKind,
    mut found: impl FnMut(Position, &'text str, DisallowedCharacter) -> Option<ParseError>,
    invalid: impl FnOnce(Position, &'text [u8]) -> ParseError,
) -> Option<ParseError> {
    let mut position = start;
    // A joiner or variation selector must be next to visible characters in
    // the same text, so a character outside `text` does not count.
    let mut previous = None;
    for chunk in text.utf8_chunks() {
        let valid = chunk.valid();
        let mut characters = valid.char_indices().peekable();
        while let Some((index, character)) = characters.next() {
            let next = characters.peek().map(|&(_, next)| next);
            let neighbors = Neighbors { previous, next };
            if let Some(disallowed) = disallowed_character(character, kind, neighbors) {
                let character_text = &valid[index..index + character.len_utf8()];
                if let Some(error) = found(position, character_text, disallowed) {
                    return Some(error);
                }
            }
            previous = Some(character);
            position = position.next_column();
        }
        if !chunk.invalid().is_empty() {
            return Some(invalid(position, chunk.invalid()));
        }
    }
    None
}

/// Returns the error for `character` at `position`, which a kind of text does
/// not allow for the reason `disallowed`.
fn character_error(
    errors: &SyntaxErrors,
    position: Position,
    character: &str,
    disallowed: DisallowedCharacter,
) -> ParseError {
    match disallowed {
        DisallowedCharacter::ByteOrderMark => {
            errors.byte_order_mark_error(position, position, character)
        }
        DisallowedCharacter::CarriageReturn => {
            errors.carriage_return_error(position, position, character)
        }
        DisallowedCharacter::Control => {
            errors.control_character_error(position, position, character)
        }
        DisallowedCharacter::Invisible => {
            errors.invisible_character_error(position, position, character)
        }
    }
}

/// Adds the diagnostic for `character` at `position` in a comment, which
/// comments do not allow for the reason `disallowed`, and returns the error
/// if `character` must stop the parse instead.
fn add_comment_character_diagnostic(
    errors: &SyntaxErrors,
    diagnostics: &mut ParserDiagnostics,
    position: Position,
    character: &str,
    disallowed: DisallowedCharacter,
) -> Option<ParseError> {
    let added = match disallowed {
        DisallowedCharacter::ByteOrderMark => {
            diagnostics.byte_order_mark_in_comment_diagnostic(position, position)
        }
        DisallowedCharacter::Control => {
            diagnostics.control_character_in_comment_diagnostic(position, position, character)
        }
        DisallowedCharacter::Invisible => {
            diagnostics.invisible_character_in_comment_diagnostic(position, position, character)
        }
        // Carriage returns come from the line endings of a whole file, so they
        // stop the parse instead of getting a diagnostic on every line.
        DisallowedCharacter::CarriageReturn => {
            return Some(character_error(errors, position, character, disallowed));
        }
    };
    added.err().map(ParseError::from)
}

/// The characters on either side of a character being checked, where `None`
/// is something other than a character.
#[derive(Clone, Copy)]
struct Neighbors {
    previous: Option<char>,
    next: Option<char>,
}

/// Returns why `kind` does not allow `character` between `neighbors`, if it
/// does not.
fn disallowed_character(
    character: char,
    kind: TextKind,
    neighbors: Neighbors,
) -> Option<DisallowedCharacter> {
    let disallowed = match character {
        // Most characters in comments are printable ASCII, which every kind
        // of text allows.
        ' '..='~' => return None,
        BYTE_ORDER_MARK => DisallowedCharacter::ByteOrderMark,
        CARRIAGE_RETURN => DisallowedCharacter::CarriageReturn,
        _ if character.is_control() => DisallowedCharacter::Control,
        _ if DIRECTION_MARKS.contains(&character) => {
            if kind == TextKind::Comment {
                return None;
            }
            DisallowedCharacter::Invisible
        }
        // Where syntax goes wrong, a variation selector or joiner is a syntax
        // error, since syntax may not have it either way.
        _ if kind == TextKind::Syntax
            && (VARIATION_SELECTORS.contains(&character) || JOINERS.contains(&character)) =>
        {
            return None;
        }
        _ if VARIATION_SELECTORS.contains(&character) => {
            if neighbors.previous.is_some_and(is_visible) {
                return None;
            }
            DisallowedCharacter::Invisible
        }
        _ if JOINERS.contains(&character) => {
            let previous_allows = neighbors.previous.is_some_and(|previous| {
                is_visible(previous) || VARIATION_SELECTORS.contains(&previous)
            });
            if previous_allows && neighbors.next.is_some_and(is_visible) {
                return None;
            }
            DisallowedCharacter::Invisible
        }
        _ if is_invisible(character) => DisallowedCharacter::Invisible,
        _ => return None,
    };
    Some(disallowed)
}

/// Whether `character` is in the spec's invisible ranges, apart from the
/// characters that its Invisible Characters rule allows in some contexts.
fn is_invisible(character: char) -> bool {
    let code_point = u32::from(character);
    let after = INVISIBLE_RANGES.partition_point(|&(start, _)| start <= code_point);
    after > 0 && code_point <= INVISIBLE_RANGES[after - 1].1
}

/// Whether `character` is visible under the spec's Invisible Characters rule.
fn is_visible(character: char) -> bool {
    character > ' '
        && character != '\u{7f}'
        && !DIRECTION_MARKS.contains(&character)
        && !VARIATION_SELECTORS.contains(&character)
        && !JOINERS.contains(&character)
        && !is_invisible(character)
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
    let position = Position {
        line: start.line,
        column: start.column + offset,
    };
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
    let disallowed = disallowed_character(character, TextKind::Syntax, neighbors)?;
    let text = &chunk.valid()[..character.len_utf8()];
    Some(character_error(errors, position, text, disallowed))
}

/// Returns the error for the bytes at `position` that are not valid UTF-8.
#[cold]
#[inline(never)]
fn invalid_encoding(errors: &SyntaxErrors, position: Position, bytes: &[u8]) -> ParseError {
    // The bytes are not characters, so the error shows them as escapes.
    let escaped: String = bytes.iter().map(|byte| format!("\\x{byte:02x}")).collect();
    errors.invalid_encoding_error(position, position, &escaped)
}
