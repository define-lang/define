//! The characters that Define does not allow, and the syntax errors for them.

// Everything here is on a cold path. It runs only after parsing has already
// failed, or after a vector scan has found text that is not printable ASCII,
// so it decodes and checks characters one at a time instead of vectorizing.

use crate::parse_error::ParseError;
use crate::scanner::{Position, Scanner};
use crate::syntax_errors::SyntaxErrors;

const BYTE_ORDER_MARK: char = '\u{feff}';
const CARRIAGE_RETURN: char = '\r';
/// The direction marks, which only comments may have.
const DIRECTION_MARKS: [char; 3] = ['\u{061c}', '\u{200e}', '\u{200f}'];

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
    for chunk in text.utf8_chunks() {
        for character in chunk.valid().chars() {
            if let Some(error) = disallowed_character(errors, position, character, kind) {
                return Some(error);
            }
            position = position.next_column();
        }
        if !chunk.invalid().is_empty() {
            return Some(ParseError::not_yet_supported(position, "invalid UTF-8"));
        }
    }
    None
}

/// Returns the error for the character `offset` bytes, which are ASCII, past
/// the scanner's position, where the syntax there went wrong, if no syntax may
/// have it.
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
        return Some(ParseError::not_yet_supported(position, "invalid UTF-8"));
    };
    disallowed_character(errors, position, character, TextKind::Syntax)
}

/// Returns the error for `character` at `position` if `kind` does not allow
/// it.
fn disallowed_character(
    errors: &SyntaxErrors,
    position: Position,
    character: char,
    kind: TextKind,
) -> Option<ParseError> {
    let mut buffer = [0; 4];
    let text = &*character.encode_utf8(&mut buffer);
    let error = match character {
        BYTE_ORDER_MARK => errors.byte_order_mark_error(position, position, text),
        CARRIAGE_RETURN => errors.carriage_return_error(position, position, text),
        _ if character.is_control() => errors.control_character_error(position, position, text),
        _ if kind != TextKind::Comment && DIRECTION_MARKS.contains(&character) => {
            errors.invisible_character_error(position, position, text)
        }
        _ if kind == TextKind::Name && !character.is_ascii() => {
            return Some(ParseError::not_yet_supported(position, "non-ASCII names"));
        }
        _ => return None,
    };
    Some(error)
}
