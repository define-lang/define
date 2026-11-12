//! The characters that text in Define and defcl files may not have: the
//! Invisible Characters rule that the two languages share, and the byte order
//! marks, carriage returns and control characters that neither allows.

// Most text is printable ASCII, which every kind of text allows, so this
// decodes and checks characters one at a time instead of vectorizing.

mod invisible_ranges;

use invisible_ranges::INVISIBLE_RANGES;
use source_rendering::Position;
use std::iter::Peekable;
use std::str::Chars;

const BYTE_ORDER_MARK: char = '\u{feff}';
const CARRIAGE_RETURN: char = '\r';
const DELETE: char = '\u{7f}';
/// The direction marks, which only comments may have.
const DIRECTION_MARKS: [char; 3] = ['\u{061c}', '\u{200e}', '\u{200f}'];
/// Variation selectors 15 and 16, which may only follow a visible character.
const VARIATION_SELECTORS: [char; 2] = ['\u{fe0e}', '\u{fe0f}'];
/// The zero width non-joiner and joiner, which may only come between a visible
/// character or variation selector and a visible character.
const JOINERS: [char; 2] = ['\u{200c}', '\u{200d}'];

/// The kind of text that characters are in, which decides which characters
/// it may have.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum TextKind {
    /// Syntax with semantics. Its errors are for characters that no syntax may
    /// have; any other character that does not belong is a syntax error.
    Syntax,
    Name,
    /// The content of a Define literal or a defcl string.
    LiteralContent,
    Comment,
}

/// Why a kind of text does not allow a character.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum DisallowedReason {
    ByteOrderMark,
    CarriageReturn,
    Control,
    Invisible,
}

/// A character that a kind of text does not allow, where it is, and why.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct DisallowedCharacter {
    pub position: Position,
    pub character: char,
    pub reason: DisallowedReason,
}

/// The characters on either side of a character being checked, where `None`
/// is something other than a character.
#[derive(Clone, Copy)]
pub struct Neighbors {
    pub previous: Option<char>,
    pub next: Option<char>,
}

impl Neighbors {
    /// No character on either side, for a character checked on its own.
    pub const NONE: Self = Self {
        previous: None,
        next: None,
    };
}

/// The first character in `text`, which begins at `start` and has no line
/// feed, that `kind` does not allow, if there is one.
#[must_use]
pub fn first_disallowed_character(
    start: Position,
    text: &str,
    kind: TextKind,
) -> Option<DisallowedCharacter> {
    disallowed_characters(start, text, kind).next()
}

/// Each character in `text`, which begins at `start` and has no line feed,
/// that `kind` does not allow, in order.
#[must_use]
pub fn disallowed_characters(
    start: Position,
    text: &str,
    kind: TextKind,
) -> DisallowedCharacters<'_> {
    DisallowedCharacters {
        characters: text.chars().peekable(),
        kind,
        position: start,
        previous: None,
    }
}

/// The iterator that `disallowed_characters` returns.
pub struct DisallowedCharacters<'text> {
    characters: Peekable<Chars<'text>>,
    kind: TextKind,
    /// The position of the next character.
    position: Position,
    /// The character before the next one. A joiner or variation selector must
    /// be next to visible characters in the same text, so a character outside
    /// the text does not count.
    previous: Option<char>,
}

impl Iterator for DisallowedCharacters<'_> {
    type Item = DisallowedCharacter;

    fn next(&mut self) -> Option<DisallowedCharacter> {
        loop {
            let character = self.characters.next()?;
            let neighbors = Neighbors {
                previous: self.previous,
                next: self.characters.peek().copied(),
            };
            let position = self.position;
            self.position = position.next_column();
            self.previous = Some(character);
            if let Some(reason) = disallowed_reason(character, self.kind, neighbors) {
                return Some(DisallowedCharacter {
                    position,
                    character,
                    reason,
                });
            }
        }
    }
}

/// Returns why `kind` does not allow `character` between `neighbors`, if it
/// does not.
#[must_use]
pub fn disallowed_reason(
    character: char,
    kind: TextKind,
    neighbors: Neighbors,
) -> Option<DisallowedReason> {
    let disallowed = match character {
        // Most characters in comments are printable ASCII, which every kind
        // of text allows.
        ' '..='~' => return None,
        BYTE_ORDER_MARK => DisallowedReason::ByteOrderMark,
        CARRIAGE_RETURN => DisallowedReason::CarriageReturn,
        _ if character.is_control() => DisallowedReason::Control,
        _ if DIRECTION_MARKS.contains(&character) => {
            if kind == TextKind::Comment {
                return None;
            }
            DisallowedReason::Invisible
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
            DisallowedReason::Invisible
        }
        _ if JOINERS.contains(&character) => {
            let previous_allows = neighbors.previous.is_some_and(|previous| {
                is_visible(previous) || VARIATION_SELECTORS.contains(&previous)
            });
            if previous_allows && neighbors.next.is_some_and(is_visible) {
                return None;
            }
            DisallowedReason::Invisible
        }
        _ if is_invisible(character) => DisallowedReason::Invisible,
        _ => return None,
    };
    Some(disallowed)
}

/// Whether `character` is in the invisible ranges, apart from the characters
/// that the Invisible Characters rule allows in some contexts.
fn is_invisible(character: char) -> bool {
    let code_point = u32::from(character);
    let after = INVISIBLE_RANGES.partition_point(|&(start, _)| start <= code_point);
    after > 0 && code_point <= INVISIBLE_RANGES[after - 1].1
}

/// Whether `character` is visible under the Invisible Characters rule.
fn is_visible(character: char) -> bool {
    character > ' '
        && character != DELETE
        && !DIRECTION_MARKS.contains(&character)
        && !VARIATION_SELECTORS.contains(&character)
        && !JOINERS.contains(&character)
        && !is_invisible(character)
}

#[cfg(test)]
mod tests {
    use super::{
        DisallowedCharacter, DisallowedReason, TextKind, disallowed_characters,
        first_disallowed_character,
    };
    use googletest::prelude::*;
    use source_rendering::Position;

    const RIGHT_TO_LEFT_OVERRIDE: char = '\u{202e}';
    const BYTE_ORDER_MARK: char = '\u{feff}';
    const RIGHT_TO_LEFT_MARK: char = '\u{200f}';
    const VARIATION_SELECTOR_16: char = '\u{fe0f}';
    const ZERO_WIDTH_JOINER: char = '\u{200d}';

    /// Each character of `text`, which starts at line 1, column 1, that `kind`
    /// does not allow, with its column and why.
    fn disallowed(text: &str, kind: TextKind) -> Vec<(u32, char, DisallowedReason)> {
        disallowed_characters(Position::START, text, kind)
            .map(|found| (found.position.column, found.character, found.reason))
            .collect()
    }

    #[gtest]
    fn printable_text_is_allowed() -> Result<()> {
        verify_that!(disallowed("café 😀", TextKind::LiteralContent), is_empty())
    }

    #[gtest]
    fn reports_each_disallowed_character_at_its_column() -> Result<()> {
        verify_that!(
            disallowed(
                &format!("a{RIGHT_TO_LEFT_OVERRIDE}b\tc{BYTE_ORDER_MARK}\r"),
                TextKind::LiteralContent
            ),
            elements_are![
                eq(&(2, RIGHT_TO_LEFT_OVERRIDE, DisallowedReason::Invisible)),
                eq(&(4, '\t', DisallowedReason::Control)),
                eq(&(6, BYTE_ORDER_MARK, DisallowedReason::ByteOrderMark)),
                eq(&(7, '\r', DisallowedReason::CarriageReturn)),
            ]
        )
    }

    #[gtest]
    fn direction_marks_only_in_comments() {
        let text = format!("a{RIGHT_TO_LEFT_MARK}b");
        expect_that!(disallowed(&text, TextKind::Comment), is_empty());
        expect_that!(
            disallowed(&text, TextKind::LiteralContent),
            elements_are![eq(&(2, RIGHT_TO_LEFT_MARK, DisallowedReason::Invisible))]
        );
    }

    #[gtest]
    fn joiners_and_variation_selectors_need_visible_neighbors() {
        expect_that!(
            disallowed(
                &format!("❤{VARIATION_SELECTOR_16}{ZERO_WIDTH_JOINER}🔥"),
                TextKind::LiteralContent
            ),
            is_empty()
        );
        expect_that!(
            disallowed(
                &format!("{VARIATION_SELECTOR_16}a{ZERO_WIDTH_JOINER}"),
                TextKind::LiteralContent
            ),
            elements_are![
                eq(&(1, VARIATION_SELECTOR_16, DisallowedReason::Invisible)),
                eq(&(3, ZERO_WIDTH_JOINER, DisallowedReason::Invisible)),
            ]
        );
    }

    #[gtest]
    fn first_disallowed_character_is_the_first() -> Result<()> {
        verify_that!(
            first_disallowed_character(Position::START, "a\tb\tc", TextKind::Comment),
            some(eq(DisallowedCharacter {
                position: Position { line: 1, column: 2 },
                character: '\t',
                reason: DisallowedReason::Control,
            }))
        )
    }
}
