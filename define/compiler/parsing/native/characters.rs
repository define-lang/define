//! The characters that Define does not allow, and the syntax errors for them.

// Everything here runs only after parsing has already failed, or after a
// vector scan has found text that is not printable ASCII, such as a comment in
// a language other than English. Source that is printable ASCII never comes
// here, so this decodes and checks characters one at a time instead of
// vectorizing.

mod invisible_ranges;

use crate::parse_error::ParseError;
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
    Comment,
}

/// Returns the error for the first character in `text`, which begins at
/// `start` and has no line feed, that `kind` does not allow.
pub fn first_disallowed_character(
    errors: &SyntaxErrors,
    start: Position,
    text: &[u8],
    kind: TextKind,
) -> Option<ParseError> {
    let mut position = start;
    // A joiner or variation selector must be next to visible characters in
    // the same text, so a character outside `text` does not count.
    let mut previous = None;
    for chunk in text.utf8_chunks() {
        let mut characters = chunk.valid().chars().peekable();
        while let Some(character) = characters.next() {
            let next = characters.peek().copied();
            let neighbors = Neighbors { previous, next };
            if let Some(error) = disallowed_character(errors, position, character, kind, neighbors)
            {
                return Some(error);
            }
            previous = Some(character);
            position = position.next_column();
        }
        if !chunk.invalid().is_empty() {
            return Some(invalid_encoding(errors, position, chunk.invalid()));
        }
    }
    None
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
    let chunk = scanner.rest_of_line().bytes[offset..]
        .utf8_chunks()
        .next()?;
    let Some(character) = chunk.valid().chars().next() else {
        return Some(invalid_encoding(errors, position, chunk.invalid()));
    };
    let neighbors = Neighbors {
        previous: None,
        next: None,
    };
    disallowed_character(errors, position, character, TextKind::Syntax, neighbors)
}

/// The characters on either side of a character being checked, where `None`
/// is something other than a character.
#[derive(Clone, Copy)]
struct Neighbors {
    previous: Option<char>,
    next: Option<char>,
}

/// Returns the error for `character` at `position`, between `neighbors`, if
/// `kind` does not allow it.
fn disallowed_character(
    errors: &SyntaxErrors,
    position: Position,
    character: char,
    kind: TextKind,
    neighbors: Neighbors,
) -> Option<ParseError> {
    let mut buffer = [0; 4];
    let text = &*character.encode_utf8(&mut buffer);
    let error = match character {
        // Most characters in comments are printable ASCII, which every kind
        // of text allows.
        ' '..='~' => return None,
        BYTE_ORDER_MARK => errors.byte_order_mark_error(position, position, text),
        CARRIAGE_RETURN => errors.carriage_return_error(position, position, text),
        _ if character.is_control() => errors.control_character_error(position, position, text),
        _ if DIRECTION_MARKS.contains(&character) => {
            if kind == TextKind::Comment {
                return None;
            }
            errors.invisible_character_error(position, position, text)
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
            errors.invisible_character_error(position, position, text)
        }
        _ if JOINERS.contains(&character) => {
            let previous_allows = neighbors.previous.is_some_and(|previous| {
                is_visible(previous) || VARIATION_SELECTORS.contains(&previous)
            });
            if previous_allows && neighbors.next.is_some_and(is_visible) {
                return None;
            }
            errors.invisible_character_error(position, position, text)
        }
        _ if is_invisible(character) => errors.invisible_character_error(position, position, text),
        _ => return None,
    };
    Some(error)
}

/// Returns the error for the bytes at `position` that are not valid UTF-8.
#[cold]
#[inline(never)]
fn invalid_encoding(errors: &SyntaxErrors, position: Position, bytes: &[u8]) -> ParseError {
    // The bytes are not characters, so the error shows them as escapes.
    let escaped: String = bytes.iter().map(|byte| format!("\\x{byte:02x}")).collect();
    errors.invalid_encoding_error(position, position, &escaped)
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
