//! Scans of the words of defcl files (field names, numbers and enum values) that
//! compare 32 bytes at a time.
//!
//! Benchmarks of field names, numbers and enum values showed these scans
//! about 60% faster than checking one byte at a time, and also faster than a
//! 256-entry table of the bytes that each kind of word allows.

// Everything in this module is optimized for performance, not readability
// (other than the tests).

use source_scanning::{WIDTH, byte_mask, in_range_mask, low_bits};
use wide::u8x32;

/// Whether `byte` may be in the word where a field name belongs, which is
/// then checked for the rules of field names.
pub const fn is_field_name_word_character(byte: u8) -> bool {
    byte.is_ascii_alphanumeric() || matches!(byte, b'_' | b'-' | b'.')
}

/// Whether `byte` may be in the word where a number belongs, which is then
/// checked for the rules of numbers.
pub const fn is_number_word_character(byte: u8) -> bool {
    byte.is_ascii_alphanumeric() || matches!(byte, b'_' | b'-' | b'+' | b'.')
}

/// Whether `byte` may be in an enum value's word.
pub const fn is_enum_word_character(byte: u8) -> bool {
    byte.is_ascii_alphanumeric() || byte == b'_'
}

/// What a scan of the word where a field name belongs found.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct FieldNameWord {
    /// The length of the word in bytes.
    pub length: usize,
    /// Whether the word follows the rules for field names.
    pub is_field_name: bool,
}

/// Scans the word where a field name belongs at the start of `source`, which
/// starts with a byte that `is_field_name_word_character` accepts.
///
/// ```ebnf
/// FIELD_NAME = lowercase_letter, { lowercase_letter | dec | ( "_", lowercase_letter ) } ;
/// ```
#[inline]
#[must_use]
pub fn field_name_word(source: &[u8]) -> FieldNameWord {
    // Almost every field name and the byte after it fit in one vector, which
    // then answers both how long the word is and whether it is a field name.
    if let Some(&chunk) = source.first_chunk::<WIDTH>() {
        let vector = u8x32::new(chunk);
        let ends = !field_name_word_mask(vector);
        if ends != 0 {
            let length = ends.trailing_zeros() as usize;
            let within = low_bits(length);
            let lowercase = in_range_mask(vector, b'a', b'z');
            let digits = in_range_mask(vector, b'0', b'9');
            let underscores = byte_mask(vector, b'_');
            let other = !(lowercase | digits | underscores) & within;
            // An underscore is followed by something other than a lowercase
            // letter, including the byte after the word.
            let bad_underscores = underscores & !(lowercase >> 1) & within;
            let bad_start = !lowercase & 1;
            return FieldNameWord {
                length,
                is_field_name: (other | bad_underscores | bad_start) == 0,
            };
        }
    }
    let length = word_length(source, field_name_word_mask, is_field_name_word_character);
    FieldNameWord {
        length,
        is_field_name: is_field_name(&source[..length]),
    }
}

/// Whether `word`, the bytes of the word where a field name belongs, follow
/// the rules for field names, checked one byte at a time.
fn is_field_name(word: &[u8]) -> bool {
    if !word.first().is_some_and(u8::is_ascii_lowercase) {
        return false;
    }
    let mut index = 1;
    while let Some(&byte) = word.get(index) {
        if byte == b'_' {
            if !word.get(index + 1).is_some_and(u8::is_ascii_lowercase) {
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

/// The number of spaces after the line feed that `source` starts with, and
/// the byte after them, if `source` starts with a line feed and something
/// other than spaces follows them.
#[inline]
#[must_use]
pub fn line_feed_and_spaces(source: &[u8]) -> Option<(usize, u8)> {
    if source.first() != Some(&b'\n') {
        return None;
    }
    let after = &source[1..];
    // Indentation is almost always shorter than one vector, which then finds
    // its end and the byte after it.
    if let Some(&chunk) = after.first_chunk::<WIDTH>() {
        let spaces = (!byte_mask(u8x32::new(chunk), b' ')).trailing_zeros() as usize;
        if spaces < WIDTH {
            return Some((spaces, after[spaces]));
        }
    }
    let spaces = after.iter().take_while(|&&byte| byte == b' ').count();
    after.get(spaces).map(|&byte| (spaces, byte))
}

/// The length in bytes of the word where a number belongs at the start of
/// `source`, which starts with a byte that `is_number_word_character` accepts.
#[inline]
#[must_use]
pub fn number_word_length(source: &[u8]) -> usize {
    word_length(source, number_word_mask, is_number_word_character)
}

/// The length in bytes of the enum value's word at the start of `source`,
/// which starts with a byte that `is_enum_word_character` accepts.
#[inline]
#[must_use]
pub fn enum_word_length(source: &[u8]) -> usize {
    word_length(source, enum_word_mask, is_enum_word_character)
}

/// The length of the bytes at the start of `source` that `included_mask`
/// accepts a vector of and `is_included` accepts one of.
fn word_length(
    source: &[u8],
    included_mask: impl Fn(u8x32) -> u32,
    is_included: impl Fn(u8) -> bool,
) -> usize {
    let (chunks, remainder) = source.as_chunks::<WIDTH>();
    for (index, &chunk) in chunks.iter().enumerate() {
        let ends = !included_mask(u8x32::new(chunk));
        if ends != 0 {
            return index * WIDTH + ends.trailing_zeros() as usize;
        }
    }
    let remainder_length = match source.last_chunk::<WIDTH>() {
        // Loading the last 32 bytes, which overlap bytes already scanned, is
        // faster than copying the remainder into a zeroed array.
        Some(&last_chunk) if !remainder.is_empty() => {
            let ends = !included_mask(u8x32::new(last_chunk)) >> (WIDTH - remainder.len());
            if ends == 0 {
                remainder.len()
            } else {
                ends.trailing_zeros() as usize
            }
        }
        // For a source shorter than one vector, a byte loop is faster than
        // copying it into a zeroed array.
        _ => remainder
            .iter()
            .take_while(|&&byte| is_included(byte))
            .count(),
    };
    chunks.len() * WIDTH + remainder_length
}

/// A mask of the bytes of `vector` that `is_field_name_word_character`
/// accepts.
fn field_name_word_mask(vector: u8x32) -> u32 {
    alphanumeric_mask(vector)
        | byte_mask(vector, b'_')
        | byte_mask(vector, b'-')
        | byte_mask(vector, b'.')
}

/// A mask of the bytes of `vector` that `is_number_word_character` accepts.
fn number_word_mask(vector: u8x32) -> u32 {
    field_name_word_mask(vector) | byte_mask(vector, b'+')
}

/// A mask of the bytes of `vector` that `is_enum_word_character` accepts.
fn enum_word_mask(vector: u8x32) -> u32 {
    alphanumeric_mask(vector) | byte_mask(vector, b'_')
}

/// A mask of the ASCII letters and digits in `vector`.
fn alphanumeric_mask(vector: u8x32) -> u32 {
    // Setting the bit that tells a lowercase ASCII letter from an uppercase
    // one makes every letter lowercase, and no other byte a lowercase letter.
    let lowercase = vector | u8x32::splat(0x20);
    in_range_mask(lowercase, b'a', b'z') | in_range_mask(vector, b'0', b'9')
}

// These tests cover the scans' own logic: what each scan reports, and the
// separate paths for words near the end of the source and for words longer
// than one vector. They are not tests of defcl syntax, which the parser tests
// cover.
#[cfg(test)]
mod tests {
    use super::*;
    use googletest::prelude::*;

    /// `word`, then a space and enough text that the word and the byte after
    /// it fit in the first vector.
    fn in_long_source(word: &str) -> Vec<u8> {
        format!("{word} and more text after it, to fill a vector").into_bytes()
    }

    #[gtest]
    fn field_name_in_one_vector() -> Result<()> {
        verify_that!(
            field_name_word(&in_long_source("universe_name")),
            eq(FieldNameWord {
                length: 13,
                is_field_name: true,
            })
        )
    }

    #[gtest]
    fn field_name_with_digits_in_one_vector() -> Result<()> {
        verify_that!(
            field_name_word(&in_long_source("level2")),
            eq(FieldNameWord {
                length: 6,
                is_field_name: true,
            })
        )
    }

    #[gtest]
    fn invalid_field_names_in_one_vector() {
        for word in [
            "Universe", "uNiverse", "2level", "_name", "a__b", "name_", "a_1", "a-b", "a.b",
        ] {
            expect_that!(
                field_name_word(&in_long_source(word)),
                eq(FieldNameWord {
                    length: word.len(),
                    is_field_name: false,
                })
            );
        }
    }

    #[gtest]
    fn field_name_near_end_of_source() -> Result<()> {
        verify_that!(
            field_name_word(b"a_b: 1\n"),
            eq(FieldNameWord {
                length: 3,
                is_field_name: true,
            })
        )
    }

    #[gtest]
    fn invalid_field_name_near_end_of_source() -> Result<()> {
        verify_that!(
            field_name_word(b"a_: 1\n"),
            eq(FieldNameWord {
                length: 2,
                is_field_name: false,
            })
        )
    }

    #[gtest]
    fn field_name_longer_than_one_vector() -> Result<()> {
        let word = "a_field_name_that_is_longer_than_one_vector";
        verify_that!(
            field_name_word(&in_long_source(word)),
            eq(FieldNameWord {
                length: word.len(),
                is_field_name: true,
            })
        )
    }

    #[gtest]
    fn invalid_field_name_longer_than_one_vector() -> Result<()> {
        let word = "a_field_name_that_is_longer_than_one_vector_";
        verify_that!(
            field_name_word(&in_long_source(word)),
            eq(FieldNameWord {
                length: word.len(),
                is_field_name: false,
            })
        )
    }

    #[gtest]
    fn field_name_ending_with_underscore_at_end_of_first_vector() -> Result<()> {
        // The underscore is the last byte of the first vector, so whether a
        // lowercase letter follows it is in the next vector.
        let word = "abcdefghijklmnopqrstuvwxyzabcde_f";
        verify_that!(
            field_name_word(&in_long_source(word)),
            eq(FieldNameWord {
                length: word.len(),
                is_field_name: true,
            })
        )
    }

    #[gtest]
    fn line_feed_and_spaces_in_one_vector() -> Result<()> {
        verify_that!(
            line_feed_and_spaces(&in_long_source("\n  name")),
            some(eq((2, b'n')))
        )
    }

    #[gtest]
    fn line_feed_and_spaces_near_end_of_source() -> Result<()> {
        verify_that!(line_feed_and_spaces(b"\n  }"), some(eq((2, b'}'))))
    }

    #[gtest]
    fn line_feed_and_spaces_longer_than_one_vector() -> Result<()> {
        let source = format!("\n{}name", " ".repeat(40));
        verify_that!(
            line_feed_and_spaces(&in_long_source(&source)),
            some(eq((40, b'n')))
        )
    }

    #[gtest]
    fn line_feed_and_spaces_to_end_of_source() -> Result<()> {
        verify_that!(line_feed_and_spaces(b"\n  "), none())
    }

    #[gtest]
    fn no_line_feed() -> Result<()> {
        verify_that!(line_feed_and_spaces(b"  name"), none())
    }

    #[gtest]
    fn number_in_one_vector() -> Result<()> {
        verify_that!(number_word_length(&in_long_source("-12.5")), eq(5))
    }

    #[gtest]
    fn number_with_characters_that_numbers_do_not_have() -> Result<()> {
        verify_that!(number_word_length(&in_long_source("+1_0e-5x")), eq(8))
    }

    #[gtest]
    fn number_near_end_of_source() -> Result<()> {
        verify_that!(number_word_length(b"12\n"), eq(2))
    }

    #[gtest]
    fn number_at_end_of_source() -> Result<()> {
        verify_that!(number_word_length(b"12"), eq(2))
    }

    #[gtest]
    fn number_longer_than_one_vector() -> Result<()> {
        let word = "1234567890123456789012345678901234567890";
        verify_that!(number_word_length(&in_long_source(word)), eq(word.len()))
    }

    #[gtest]
    fn number_ending_in_last_vector_overlapping_the_one_before() -> Result<()> {
        let source = "1234567890123456789012345678901234567890 x";
        verify_that!(number_word_length(source.as_bytes()), eq(40))
    }

    #[gtest]
    fn number_filling_the_source_past_one_vector() -> Result<()> {
        let source = "1234567890123456789012345678901234567890";
        verify_that!(number_word_length(source.as_bytes()), eq(40))
    }

    #[gtest]
    fn enum_value_in_one_vector() -> Result<()> {
        verify_that!(enum_word_length(&in_long_source("STATUS_ACTIVE")), eq(13))
    }

    #[gtest]
    fn enum_value_does_not_include_hyphen() -> Result<()> {
        verify_that!(enum_word_length(&in_long_source("ACTIVE-2")), eq(6))
    }
}
