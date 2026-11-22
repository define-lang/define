//! Scans of the words of defcl files (field names, numbers and enum values) that
//! compare 32 bytes at a time.
//!
//! Benchmarks of field names, numbers and enum values showed these scans
//! about 60% faster than checking one byte at a time, and also faster than a
//! 256-entry table of the bytes that each kind of word allows.

// Everything in this module is optimized for performance, not readability
// (other than the tests).

use source_scanning::{WIDTH, byte_mask, in_range_mask, in_range_vector, low_bits_before};
use wide::u8x32;

/// Whether `byte` may be in the word where a field name belongs, which is
/// then checked for the rules of field names.
pub(crate) const fn is_field_name_word_character(byte: u8) -> bool {
    byte.is_ascii_alphanumeric() || matches!(byte, b'_' | b'-' | b'.')
}

/// Whether `byte` may be in the word where a number belongs, which is then
/// checked for the rules of numbers.
pub(crate) const fn is_number_word_character(byte: u8) -> bool {
    byte.is_ascii_alphanumeric() || matches!(byte, b'_' | b'-' | b'+' | b'.')
}

/// Whether `byte` may be in an enum value's word.
pub(crate) const fn is_enum_word_character(byte: u8) -> bool {
    byte.is_ascii_alphanumeric() || byte == b'_'
}

/// What a scan of the word where a field name belongs found.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) struct FieldNameWord {
    /// The length of the word in bytes.
    pub length: usize,
    /// Whether the word follows the rules for field names, if the scan
    /// determined it in one vector.
    pub is_field_name: Option<bool>,
}

/// Scans the word where a field name belongs at the start of `source`, which
/// starts with a byte that `is_field_name_word_character` accepts.
///
/// ```ebnf
/// FIELD_NAME = lowercase_letter, { lowercase_letter | dec | ( "_", lowercase_letter ) } ;
/// ```
#[inline]
#[must_use]
pub(crate) fn field_name_word(source: &[u8]) -> FieldNameWord {
    // Almost every field name is valid and fits in one vector with the byte
    // after it, so checking only valid field-name characters answers both the
    // length and validity without testing uppercase letters, `-`, or `.`.
    if let Some(&chunk) = source.first_chunk::<WIDTH>() {
        let vector = u8x32::new(chunk);
        let lowercase = in_range_mask(vector, b'a', b'z');
        let digits = in_range_mask(vector, b'0', b'9');
        let underscores = byte_mask(vector, b'_');
        let ends = !(lowercase | digits | underscores);
        if ends != 0 {
            let length = ends.trailing_zeros() as usize;
            let next = source[length];
            // `next` is not a lowercase letter, digit, or `_`, so only an
            // uppercase letter, `-`, or `.` continues the word.
            if !next.is_ascii_uppercase() && !matches!(next, b'-' | b'.') {
                let within = low_bits_before(ends);
                // An underscore is followed by something other than a lowercase
                // letter, including the byte after the word.
                let bad_underscores = underscores & !(lowercase >> 1) & within;
                let bad_start = !lowercase & 1;
                return FieldNameWord {
                    length,
                    is_field_name: Some((bad_underscores | bad_start) == 0),
                };
            }
            return invalid_field_name_word(source, length);
        }
    }
    FieldNameWord {
        length: word_length(source, field_name_word_mask, is_field_name_word_character),
        is_field_name: None,
    }
}

/// Scans a field-name word whose byte at `valid_prefix` already disqualifies
/// the word from being a valid field name.
#[cold]
#[inline(never)]
fn invalid_field_name_word(source: &[u8], valid_prefix: usize) -> FieldNameWord {
    let rest = word_length(
        &source[valid_prefix..],
        field_name_word_mask,
        is_field_name_word_character,
    );
    FieldNameWord {
        length: valid_prefix + rest,
        is_field_name: Some(false),
    }
}

/// The number of spaces after the line feed that `source` starts with, and
/// the byte after them, if `source` starts with a line feed and something
/// other than spaces follows them.
#[inline]
#[must_use]
pub(crate) fn line_feed_and_spaces(source: &[u8]) -> Option<(usize, u8)> {
    if source.first() != Some(&b'\n') {
        return None;
    }
    let after = &source[1..];
    // Indentation is almost always shorter than one vector, which then finds
    // its end and the byte after it.
    if let Some(&chunk) = after.first_chunk::<WIDTH>() {
        let non_spaces = !byte_mask(u8x32::new(chunk), b' ');
        if non_spaces != 0 {
            let spaces = non_spaces.trailing_zeros() as usize;
            return Some((spaces, after[spaces]));
        }
    }
    remaining_spaces(after)
}

/// Counts leading spaces in `after` when `after` is shorter than one vector or
/// starts with a full vector of spaces.
#[cold]
#[inline(never)]
fn remaining_spaces(after: &[u8]) -> Option<(usize, u8)> {
    let spaces = after.iter().take_while(|&&byte| byte == b' ').count();
    after.get(spaces).map(|&byte| (spaces, byte))
}

/// What kind of number a scanned number word is.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum NumberKind {
    Integer,
    Float,
    Invalid,
}

/// What a scan of the word where a number belongs found.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) struct NumberWord {
    /// The length of the word in bytes.
    pub length: usize,
    /// Whether the word is a valid integer, a valid float, or neither, if the
    /// scan determined it in one vector.
    pub kind: Option<NumberKind>,
}

/// What a scan of an enum value's word found.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) struct EnumWord {
    /// The length of the word in bytes.
    pub length: usize,
    /// Whether the word follows the rules for enum values, if the scan
    /// determined it in one vector.
    pub is_enum_value: Option<bool>,
}

/// Scans the word where a number belongs at the start of `source`, which
/// starts with a byte that `is_number_word_character` accepts.
///
/// ```ebnf
/// INTEGER = ( [ "-" ], dec_lit ) - "-0" ;
/// FLOAT = ( [ "-" ], dec_lit, ".", fraction ) - "-0.0" ;
/// dec_lit = "0" | ( dec - "0" ), { dec } ;
/// fraction = "0" | { dec }, ( dec - "0" ) ;
/// ```
#[inline]
#[must_use]
pub(crate) fn number_word(source: &[u8]) -> NumberWord {
    // Almost every number contains only digits, `-`, and `.` and fits in one
    // vector with the byte after it, which then answers both length and kind.
    if let Some(&chunk) = source.first_chunk::<WIDTH>() {
        let vector = u8x32::new(chunk);
        let digits = in_range_mask(vector, b'0', b'9');
        let minuses = byte_mask(vector, b'-');
        let dots = byte_mask(vector, b'.');
        let ends = !(digits | minuses | dots);
        if ends != 0 {
            let length = ends.trailing_zeros() as usize;
            let next = source[length];
            // `next` is not a digit, `-`, or `.`, so only a letter, `_`, or `+`
            // continues the word.
            if !next.is_ascii_alphabetic() && !matches!(next, b'_' | b'+') {
                let within = low_bits_before(ends);
                let minuses_within = minuses & within;
                if minuses_within > 1 {
                    return NumberWord {
                        length,
                        kind: Some(NumberKind::Invalid),
                    };
                }
                let int_start = minuses_within as usize;
                let dots_within = dots & within;
                let kind = if dots_within == 0 {
                    if length > int_start
                        && (source[int_start] != b'0' || (int_start == 0 && length == 1))
                    {
                        NumberKind::Integer
                    } else {
                        NumberKind::Invalid
                    }
                } else if is_valid_float_in_chunk(source, int_start, dots_within, length) {
                    NumberKind::Float
                } else {
                    NumberKind::Invalid
                };
                return NumberWord {
                    length,
                    kind: Some(kind),
                };
            }
            return invalid_number_word(source, length);
        }
    }
    NumberWord {
        length: word_length(source, number_word_mask, is_number_word_character),
        kind: None,
    }
}

/// Whether `source[..length]`, which has only digits, an optional leading `-`
/// (`int_start` is 0 or 1), and non-zero `dots_within`, is a valid float.
#[inline]
fn is_valid_float_in_chunk(
    source: &[u8],
    int_start: usize,
    dots_within: u32,
    length: usize,
) -> bool {
    if dots_within & dots_within.wrapping_sub(1) != 0 {
        return false;
    }
    let dot = dots_within.trailing_zeros() as usize;
    let frac_start = dot + 1;
    let valid_int = dot > int_start && (source[int_start] != b'0' || dot == int_start + 1);
    let valid_frac =
        length > frac_start && (source[length - 1] != b'0' || length == frac_start + 1);
    valid_int && valid_frac && !(int_start == 1 && length == 4 && &source[..4] == b"-0.0")
}

/// Scans a number word whose byte at `valid_prefix` already disqualifies the
/// word from being a valid number.
#[cold]
#[inline(never)]
fn invalid_number_word(source: &[u8], valid_prefix: usize) -> NumberWord {
    let rest = word_length(
        &source[valid_prefix..],
        number_word_mask,
        is_number_word_character,
    );
    NumberWord {
        length: valid_prefix + rest,
        kind: Some(NumberKind::Invalid),
    }
}

/// Scans the enum value's word at the start of `source`, which starts with a
/// byte that `is_enum_word_character` accepts.
///
/// ```ebnf
/// enum_value = uppercase_letter, { uppercase_letter | dec | "_" } ;
/// ```
#[inline]
#[must_use]
pub(crate) fn enum_word(source: &[u8]) -> EnumWord {
    // Almost every enum value is valid and fits in one vector with the byte
    // after it, so checking only uppercase letters, digits, and `_` answers
    // both length and validity.
    if let Some(&chunk) = source.first_chunk::<WIDTH>() {
        let ends = !valid_enum_character_mask(u8x32::new(chunk));
        if ends != 0 {
            let length = ends.trailing_zeros() as usize;
            // `source[length]` is not an uppercase letter, digit, or `_`, so
            // only a lowercase letter continues the word.
            if !source[length].is_ascii_lowercase() {
                return EnumWord {
                    length,
                    is_enum_value: Some(source[0].is_ascii_uppercase()),
                };
            }
            return invalid_enum_word(source, length);
        }
    }
    EnumWord {
        length: word_length(source, enum_word_mask, is_enum_word_character),
        is_enum_value: None,
    }
}

/// Scans an enum word whose byte at `valid_prefix` already disqualifies the
/// word from being a valid enum value.
#[cold]
#[inline(never)]
fn invalid_enum_word(source: &[u8], valid_prefix: usize) -> EnumWord {
    let rest = word_length(
        &source[valid_prefix..],
        enum_word_mask,
        is_enum_word_character,
    );
    EnumWord {
        length: valid_prefix + rest,
        is_enum_value: Some(false),
    }
}

/// The length of the bytes at the start of `source` that `included_mask`
/// accepts a vector of and `is_included` accepts one of.
#[cold]
#[inline(never)]
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
    if remainder.is_empty() {
        return source.len();
    }
    let remainder_length = match source.last_chunk::<WIDTH>() {
        // Loading the last 32 bytes, which overlap bytes already scanned, is
        // faster than copying the remainder into a zeroed array.
        Some(&last_chunk) => {
            let ends = !included_mask(u8x32::new(last_chunk)) >> (WIDTH - remainder.len());
            if ends == 0 {
                remainder.len()
            } else {
                ends.trailing_zeros() as usize
            }
        }
        // For a source shorter than one vector, a byte loop is faster than
        // copying it into a zeroed array.
        None => remainder
            .iter()
            .take_while(|&&byte| is_included(byte))
            .count(),
    };
    chunks.len() * WIDTH + remainder_length
}

/// A mask of the bytes of `vector` that a valid enum value may contain:
/// uppercase letters, digits, and `_`.
#[inline]
fn valid_enum_character_mask(vector: u8x32) -> u32 {
    (in_range_vector(vector, b'A', b'Z')
        | in_range_vector(vector, b'0', b'9')
        | vector.simd_eq(u8x32::splat(b'_')))
    .to_bitmask()
}

/// A mask of the bytes of `vector` that `is_field_name_word_character`
/// accepts.
#[inline]
fn field_name_word_mask(vector: u8x32) -> u32 {
    (alphanumeric_vector(vector)
        | vector.simd_eq(u8x32::splat(b'_'))
        | in_range_vector(vector, b'-', b'.'))
    .to_bitmask()
}

/// A mask of the bytes of `vector` that `is_number_word_character` accepts.
#[inline]
fn number_word_mask(vector: u8x32) -> u32 {
    (alphanumeric_vector(vector)
        | vector.simd_eq(u8x32::splat(b'_'))
        | in_range_vector(vector, b'-', b'.')
        | vector.simd_eq(u8x32::splat(b'+')))
    .to_bitmask()
}

/// A mask of the bytes of `vector` that `is_enum_word_character` accepts.
#[inline]
fn enum_word_mask(vector: u8x32) -> u32 {
    (alphanumeric_vector(vector) | vector.simd_eq(u8x32::splat(b'_'))).to_bitmask()
}

/// A lane mask of the ASCII letters and digits in `vector`.
#[inline]
fn alphanumeric_vector(vector: u8x32) -> u8x32 {
    // Setting the bit that tells a lowercase ASCII letter from an uppercase
    // one makes every letter lowercase, and no other byte a lowercase letter.
    let lowercase = vector | u8x32::splat(0x20);
    in_range_vector(lowercase, b'a', b'z') | in_range_vector(vector, b'0', b'9')
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
                is_field_name: Some(true),
            })
        )
    }

    #[gtest]
    fn field_name_with_digits_in_one_vector() -> Result<()> {
        verify_that!(
            field_name_word(&in_long_source("level2")),
            eq(FieldNameWord {
                length: 6,
                is_field_name: Some(true),
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
                    is_field_name: Some(false),
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
                is_field_name: None,
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
                is_field_name: None,
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
                is_field_name: None,
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
    fn number_in_one_vector() {
        for (word, kind) in [
            ("0", NumberKind::Integer),
            ("42", NumberKind::Integer),
            ("-42", NumberKind::Integer),
            ("0.0", NumberKind::Float),
            ("1.0", NumberKind::Float),
            ("-12.5", NumberKind::Float),
            ("-0.05", NumberKind::Float),
            ("-", NumberKind::Invalid),
            ("-0", NumberKind::Invalid),
            ("01", NumberKind::Invalid),
            ("-0.0", NumberKind::Invalid),
            ("1.00", NumberKind::Invalid),
            ("01.5", NumberKind::Invalid),
            ("1.", NumberKind::Invalid),
            (".5", NumberKind::Invalid),
            ("1.2.3", NumberKind::Invalid),
            ("1-2", NumberKind::Invalid),
        ] {
            expect_that!(
                number_word(&in_long_source(word)),
                eq(NumberWord {
                    length: word.len(),
                    kind: Some(kind),
                })
            );
        }
    }

    #[gtest]
    fn number_with_characters_that_numbers_do_not_have() {
        for word in ["+1_0e-5x", "1_000", "123e5"] {
            expect_that!(
                number_word(&in_long_source(word)),
                eq(NumberWord {
                    length: word.len(),
                    kind: Some(NumberKind::Invalid),
                })
            );
        }
    }

    #[gtest]
    fn number_near_end_of_source() -> Result<()> {
        verify_that!(
            number_word(b"12\n"),
            eq(NumberWord {
                length: 2,
                kind: None,
            })
        )?;
        verify_that!(
            number_word(b"12"),
            eq(NumberWord {
                length: 2,
                kind: None,
            })
        )
    }

    #[gtest]
    fn number_longer_than_one_vector() -> Result<()> {
        let word = "1234567890123456789012345678901234567890";
        verify_that!(
            number_word(&in_long_source(word)),
            eq(NumberWord {
                length: word.len(),
                kind: None,
            })
        )
    }

    #[gtest]
    fn number_ending_in_last_vector_overlapping_the_one_before() -> Result<()> {
        let source = "1234567890123456789012345678901234567890 x";
        verify_that!(
            number_word(source.as_bytes()),
            eq(NumberWord {
                length: 40,
                kind: None,
            })
        )
    }

    #[gtest]
    fn number_filling_the_source_past_one_vector() -> Result<()> {
        let source = "1234567890123456789012345678901234567890";
        verify_that!(
            number_word(source.as_bytes()),
            eq(NumberWord {
                length: 40,
                kind: None,
            })
        )
    }

    #[gtest]
    fn number_filling_exact_vector_at_end_of_source() -> Result<()> {
        let source = "12345678901234567890123456789012";
        verify_that!(
            number_word(source.as_bytes()),
            eq(NumberWord {
                length: 32,
                kind: None,
            })
        )
    }

    #[gtest]
    fn enum_value_in_one_vector() -> Result<()> {
        verify_that!(
            enum_word(&in_long_source("STATUS_ACTIVE")),
            eq(EnumWord {
                length: 13,
                is_enum_value: Some(true),
            })
        )
    }

    #[gtest]
    fn enum_value_does_not_include_hyphen() -> Result<()> {
        verify_that!(
            enum_word(&in_long_source("ACTIVE-2")),
            eq(EnumWord {
                length: 6,
                is_enum_value: Some(true),
            })
        )
    }

    #[gtest]
    fn invalid_enum_values_in_one_vector() {
        for word in ["true", "Active", "STATUS_active", "1ACTIVE"] {
            expect_that!(
                enum_word(&in_long_source(word)),
                eq(EnumWord {
                    length: word.len(),
                    is_enum_value: Some(false),
                })
            );
        }
    }

    #[gtest]
    fn enum_value_near_end_of_source() -> Result<()> {
        verify_that!(
            enum_word(b"ACTIVE\n"),
            eq(EnumWord {
                length: 6,
                is_enum_value: None,
            })
        )
    }

    #[gtest]
    fn enum_value_longer_than_one_vector() -> Result<()> {
        let word = "AN_ENUM_VALUE_THAT_IS_LONGER_THAN_ONE_VECTOR";
        verify_that!(
            enum_word(&in_long_source(word)),
            eq(EnumWord {
                length: word.len(),
                is_enum_value: None,
            })
        )
    }
}
