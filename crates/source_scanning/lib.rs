//! Scans of source text that compare 32 bytes at a time, which the Define
//! compiler and the Define Configuration Language share, and the masks that
//! scans build on.
//!
//! The width of 32 bytes was chosen by benchmarking 16-, 32-, and 64-byte
//! vectors on an AVX-512 machine for Define's scans, as Define's
//! `vector_scan` module describes. 32 bytes is also the native width of AVX2,
//! which almost every x86-64 machine has; `wide` builds wider vectors from
//! narrower ones on machines without AVX-512.

// Everything in this crate is optimized for performance, not readability
// (other than the tests).

use wide::{i8x32, u8x32};

/// The number of bytes that a scan compares at a time.
pub const WIDTH: usize = 32;

const QUOTE: u8 = b'"';
const ESCAPE: u8 = b'\\';
const LINE_FEED: u8 = b'\n';

/// What a scan of quoted content found.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct QuotedContent {
    /// The length in bytes of the quoted content before its first `"`, `\`,
    /// or line feed, or before the end of the source.
    pub length: usize,
    /// The number of UTF-8 characters in those bytes.
    pub character_count: usize,
    /// Whether every one of those bytes is from ` ` through `~`.
    pub is_printable_ascii: bool,
}

/// Scans the quoted content at the start of `source`, up to its first `"`,
/// `\`, or line feed.
// The scan stops at a `\` as well as at the end of the content, so that
// content without escapes, which is almost all of it, needs nothing more than
// this one scan.
#[inline]
#[must_use]
pub fn quoted_content(source: &[u8]) -> QuotedContent {
    let Some(&chunk) = source.first_chunk::<WIDTH>() else {
        return short_quoted_content(source);
    };
    let vector = u8x32::new(chunk);
    let stops = quoted_content_stops(vector);
    if stops == 0 {
        return long_quoted_content(source);
    }
    let length = stops.trailing_zeros() as usize;
    let within = low_bits_before(stops);
    let is_printable_ascii = unprintable_mask(vector) & within == 0;
    // Printable ASCII has no UTF-8 continuation bytes, so counting continuation
    // bytes happens only when the content has another byte.
    let character_count = if is_printable_ascii {
        length
    } else {
        length - (continuation_byte_mask(vector) & within).count_ones() as usize
    };
    QuotedContent {
        length,
        character_count,
        is_printable_ascii,
    }
}

/// Scans quoted content that starts fewer than 32 bytes before the end of the
/// source.
#[cold]
#[inline(never)]
fn short_quoted_content(source: &[u8]) -> QuotedContent {
    let mut length = 0;
    let mut continuation_bytes = 0;
    let mut is_printable_ascii = true;
    for &byte in source {
        if matches!(byte, QUOTE | ESCAPE | LINE_FEED) {
            break;
        }
        is_printable_ascii &= (b' '..=b'~').contains(&byte);
        continuation_bytes += usize::from(byte & 0b1100_0000 == 0b1000_0000);
        length += 1;
    }
    QuotedContent {
        length,
        character_count: length - continuation_bytes,
        is_printable_ascii,
    }
}

/// Scans quoted content that is at least 32 bytes long.
#[inline(never)]
fn long_quoted_content(source: &[u8]) -> QuotedContent {
    let (chunks, remainder) = source.as_chunks::<WIDTH>();
    let mut unprintable = 0;
    for (index, &chunk) in chunks.iter().enumerate() {
        let vector = u8x32::new(chunk);
        let stops = quoted_content_stops(vector);
        if stops != 0 {
            let length = index * WIDTH + stops.trailing_zeros() as usize;
            unprintable |= unprintable_mask(vector) & low_bits_before(stops);
            return finish_quoted_content(source, length, unprintable == 0);
        }
        unprintable |= unprintable_mask(vector);
    }
    if remainder.is_empty() {
        return finish_quoted_content(source, source.len(), unprintable == 0);
    }
    // Loading the last 32 bytes of the source, which overlap bytes already
    // scanned, is much faster than copying the remainder into a zeroed array.
    let Some(&last_chunk) = source.last_chunk::<WIDTH>() else {
        unreachable!("long quoted content is at least 32 bytes long");
    };
    let vector = u8x32::new(last_chunk);
    let shift = WIDTH - remainder.len();
    let stops = quoted_content_stops(vector) >> shift;
    let remainder_length = if stops == 0 {
        remainder.len()
    } else {
        stops.trailing_zeros() as usize
    };
    unprintable |= (unprintable_mask(vector) >> shift) & low_bits(remainder_length);
    finish_quoted_content(
        source,
        chunks.len() * WIDTH + remainder_length,
        unprintable == 0,
    )
}

/// Builds a `QuotedContent` for the first `length` bytes of `source`, counting
/// UTF-8 characters only when `is_printable_ascii` is false.
#[inline]
fn finish_quoted_content(source: &[u8], length: usize, is_printable_ascii: bool) -> QuotedContent {
    // Printable ASCII has as many characters as bytes.
    let character_count = if is_printable_ascii {
        length
    } else {
        character_count(&source[..length])
    };
    QuotedContent {
        length,
        character_count,
        is_printable_ascii,
    }
}

/// Returns a mask of the bytes in `vector` at which a scan of quoted content
/// stops: `"`, `\`, and line feed.
#[inline]
fn quoted_content_stops(vector: u8x32) -> u32 {
    (vector.simd_eq(u8x32::splat(QUOTE))
        | vector.simd_eq(u8x32::splat(ESCAPE))
        | vector.simd_eq(u8x32::splat(LINE_FEED)))
    .to_bitmask()
}

/// What a scan of the rest of a line found.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct RestOfLine {
    /// The length in bytes of the line's text, which ends before the first
    /// line feed, or at the end of the source.
    pub length: usize,
    /// Whether every byte of the line's text is from ` ` through `~`.
    pub is_printable_ascii: bool,
}

/// Scans the rest of the line at the start of `source`.
#[inline]
#[must_use]
pub fn rest_of_line(source: &[u8]) -> RestOfLine {
    let Some(&chunk) = source.first_chunk::<WIDTH>() else {
        return short_rest_of_line(source);
    };
    let vector = u8x32::new(chunk);
    let line_feeds = byte_mask(vector, LINE_FEED);
    if line_feeds == 0 {
        return long_rest_of_line(source);
    }
    RestOfLine {
        length: line_feeds.trailing_zeros() as usize,
        is_printable_ascii: unprintable_mask(vector) & low_bits_before(line_feeds) == 0,
    }
}

/// Scans the rest of a line that starts fewer than 32 bytes before the end of
/// the source.
#[cold]
#[inline(never)]
fn short_rest_of_line(source: &[u8]) -> RestOfLine {
    let mut length = 0;
    let mut is_printable_ascii = true;
    for &byte in source {
        if byte == LINE_FEED {
            break;
        }
        is_printable_ascii &= (b' '..=b'~').contains(&byte);
        length += 1;
    }
    RestOfLine {
        length,
        is_printable_ascii,
    }
}

/// Scans the rest of a line that is at least 32 bytes long.
#[inline(never)]
fn long_rest_of_line(source: &[u8]) -> RestOfLine {
    let (chunks, remainder) = source.as_chunks::<WIDTH>();
    let mut unprintable = 0;
    for (index, &chunk) in chunks.iter().enumerate() {
        let vector = u8x32::new(chunk);
        let line_feeds = byte_mask(vector, LINE_FEED);
        if line_feeds != 0 {
            unprintable |= unprintable_mask(vector) & low_bits_before(line_feeds);
            return RestOfLine {
                length: index * WIDTH + line_feeds.trailing_zeros() as usize,
                is_printable_ascii: unprintable == 0,
            };
        }
        unprintable |= unprintable_mask(vector);
    }
    if remainder.is_empty() {
        return RestOfLine {
            length: source.len(),
            is_printable_ascii: unprintable == 0,
        };
    }
    // Loading the last 32 bytes of the source, which overlap bytes already
    // scanned, is much faster than copying the remainder into a zeroed array.
    let Some(&last_chunk) = source.last_chunk::<WIDTH>() else {
        unreachable!("long rest of line is at least 32 bytes long");
    };
    let vector = u8x32::new(last_chunk);
    let shift = WIDTH - remainder.len();
    let line_feeds = byte_mask(vector, LINE_FEED) >> shift;
    let length = if line_feeds == 0 {
        remainder.len()
    } else {
        line_feeds.trailing_zeros() as usize
    };
    unprintable |= (unprintable_mask(vector) >> shift) & low_bits(length);
    RestOfLine {
        length: chunks.len() * WIDTH + length,
        is_printable_ascii: unprintable == 0,
    }
}

/// Returns a mask of the bytes in `vector` that are not from ` ` through `~`.
#[inline]
#[must_use]
pub fn unprintable_mask(vector: u8x32) -> u32 {
    !in_range_mask(vector, b' ', b'~')
}

/// Returns a lane mask of the bytes in `vector` from `low` through `high`,
/// where `high - low` is less than 255.
#[inline]
#[must_use]
pub fn in_range_vector(vector: u8x32, low: u8, high: u8) -> u8x32 {
    // Shifting `low` to `i8::MIN` makes signed comparison check the unsigned
    // distance from `low` in two vector instructions on AVX2 and NEON as well
    // as AVX-512.
    let shifted = (vector - u8x32::splat(low.wrapping_add(0x80))).cast_signed();
    let limit = i8x32::splat((high - low).wrapping_sub(0x7F).cast_signed());
    shifted.simd_lt(limit).cast_unsigned()
}

/// Returns a mask of the bytes in `vector` from `low` through `high`, where
/// `high - low` is less than 255.
#[inline]
#[must_use]
pub fn in_range_mask(vector: u8x32, low: u8, high: u8) -> u32 {
    in_range_vector(vector, low, high).to_bitmask()
}

/// Counts the UTF-8 characters in `text`.
#[inline(never)]
#[must_use]
pub fn character_count(text: &[u8]) -> usize {
    let (chunks, remainder) = text.as_chunks::<WIDTH>();
    let mut continuation_bytes = 0;
    for &chunk in chunks {
        continuation_bytes += continuation_byte_mask(u8x32::new(chunk)).count_ones() as usize;
    }
    if !remainder.is_empty() {
        continuation_bytes += match text.last_chunk::<WIDTH>() {
            // Loading the last 32 bytes of the text, which overlap bytes
            // already counted, is much faster than copying the remainder
            // into a zeroed array.
            Some(&last_chunk) => (continuation_byte_mask(u8x32::new(last_chunk))
                >> (WIDTH - remainder.len()))
            .count_ones() as usize,
            // For text shorter than one vector, a byte loop is faster than
            // copying the text into a zeroed array.
            None => remainder
                .iter()
                .filter(|&&byte| byte & 0xC0 == 0x80)
                .count(),
        };
    }
    // Every UTF-8 character has exactly one byte that is not a continuation
    // byte.
    text.len() - continuation_bytes
}

/// Returns a mask of the UTF-8 continuation bytes (`10xxxxxx`) in `vector`.
#[inline]
#[must_use]
pub fn continuation_byte_mask(vector: u8x32) -> u32 {
    // As signed bytes, the continuation bytes are exactly the values below -64.
    vector.cast_signed().simd_lt(i8x32::splat(-64)).to_bitmask()
}

/// Returns a mask with a bit set for each byte of `vector` that is `byte`.
#[inline]
#[must_use]
pub fn byte_mask(vector: u8x32, byte: u8) -> u32 {
    vector.simd_eq(u8x32::splat(byte)).to_bitmask()
}

/// Returns the bytes of `bytes`, which has fewer than 32, followed by zeros.
#[inline]
#[must_use]
pub fn zero_padded(bytes: &[u8]) -> u8x32 {
    let mut chunk = [0; WIDTH];
    chunk[..bytes.len()].copy_from_slice(bytes);
    u8x32::new(chunk)
}

/// Returns a mask of the lowest `count` bits, where `count` is at most 32.
#[inline]
#[must_use]
pub const fn low_bits(count: usize) -> u32 {
    if count >= WIDTH {
        u32::MAX
    } else {
        (1 << count) - 1
    }
}

/// Returns a mask of the bits below the lowest set bit of `mask`, or all ones
/// if `mask` is zero.
#[inline]
#[must_use]
pub const fn low_bits_before(mask: u32) -> u32 {
    !mask & mask.wrapping_sub(1)
}

#[cfg(test)]
mod tests {
    use super::*;
    use googletest::prelude::*;
    use indoc::indoc;

    #[gtest]
    fn quoted_content_ending_at_delimiter_near_end_of_source() -> Result<()> {
        verify_that!(
            quoted_content(b"abc\".\n"),
            eq(QuotedContent {
                length: 3,
                character_count: 3,
                is_printable_ascii: true,
            })
        )
    }

    #[gtest]
    fn quoted_content_ending_at_delimiter() -> Result<()> {
        verify_that!(
            quoted_content(b"hello world\". # define the potential position<standard:/after>.\n"),
            eq(QuotedContent {
                length: 11,
                character_count: 11,
                is_printable_ascii: true,
            })
        )
    }

    #[gtest]
    fn quoted_content_ending_at_escape() -> Result<()> {
        verify_that!(
            quoted_content(indoc! {b"
                a\\\"b\".
                define the potential position<standard:/after>.
            "}),
            eq(QuotedContent {
                length: 1,
                character_count: 1,
                is_printable_ascii: true,
            })
        )
    }

    #[gtest]
    fn quoted_content_ending_at_line_feed() -> Result<()> {
        verify_that!(
            quoted_content(indoc! {b"
                abc
                define the potential position<standard:/after>.
            "}),
            eq(QuotedContent {
                length: 3,
                character_count: 3,
                is_printable_ascii: true,
            })
        )
    }

    #[gtest]
    fn quoted_content_with_non_ascii_character() -> Result<()> {
        verify_that!(
            quoted_content(
                indoc! {"
                    café\".
                    define the potential position<standard:/after>.
                "}
                .as_bytes()
            ),
            eq(QuotedContent {
                length: 5,
                character_count: 4,
                is_printable_ascii: false,
            })
        )
    }

    #[gtest]
    fn quoted_content_with_unprintable_character() -> Result<()> {
        verify_that!(
            quoted_content(indoc! {b"
                a\tb\".
                define the potential position<standard:/after>.
            "}),
            eq(QuotedContent {
                length: 3,
                character_count: 3,
                is_printable_ascii: false,
            })
        )
    }

    #[gtest]
    fn quoted_content_at_end_of_short_source() -> Result<()> {
        verify_that!(
            quoted_content(b"abc"),
            eq(QuotedContent {
                length: 3,
                character_count: 3,
                is_printable_ascii: true,
            })
        )
    }

    #[gtest]
    fn quoted_content_longer_than_one_vector() {
        let source = [&[b'a'; 40][..], b"\".\n"].concat();
        expect_that!(
            quoted_content(&source),
            eq(QuotedContent {
                length: 40,
                character_count: 40,
                is_printable_ascii: true,
            })
        );
    }

    #[gtest]
    fn quoted_content_ending_in_second_vector() -> Result<()> {
        let source = [&[b'a'; 40][..], b"\"", &[b'b'; 32][..]].concat();
        verify_that!(
            quoted_content(&source),
            eq(QuotedContent {
                length: 40,
                character_count: 40,
                is_printable_ascii: true,
            })
        )
    }

    #[gtest]
    fn quoted_content_with_non_ascii_near_end_of_source() -> Result<()> {
        verify_that!(
            quoted_content("café\"".as_bytes()),
            eq(QuotedContent {
                length: 5,
                character_count: 4,
                is_printable_ascii: false,
            })
        )
    }

    #[gtest]
    fn quoted_content_longer_than_one_vector_at_end_of_source() -> Result<()> {
        verify_that!(
            quoted_content(&[b'a'; 40]),
            eq(QuotedContent {
                length: 40,
                character_count: 40,
                is_printable_ascii: true,
            })
        )
    }

    #[gtest]
    fn quoted_content_with_non_ascii_character_after_first_vector() {
        let source = [&[b'a'; 33][..], "é\".\n".as_bytes()].concat();
        expect_that!(
            quoted_content(&source),
            eq(QuotedContent {
                length: 35,
                character_count: 34,
                is_printable_ascii: false,
            })
        );
    }

    #[gtest]
    fn quoted_content_with_non_ascii_characters_filling_first_vector() {
        let source = ["é".repeat(20).as_bytes(), b"\".\n"].concat();
        expect_that!(
            quoted_content(&source),
            eq(QuotedContent {
                length: 40,
                character_count: 20,
                is_printable_ascii: false,
            })
        );
    }

    #[gtest]
    fn quoted_content_with_unprintable_character_in_first_vector() {
        let source = [b"a\t", &[b'a'; 38][..], b"\".\n"].concat();
        expect_that!(
            quoted_content(&source),
            eq(QuotedContent {
                length: 40,
                character_count: 40,
                is_printable_ascii: false,
            })
        );
    }

    #[gtest]
    fn quoted_content_of_exactly_one_vector_at_end_of_source() -> Result<()> {
        verify_that!(
            quoted_content(&[b'a'; 32]),
            eq(QuotedContent {
                length: 32,
                character_count: 32,
                is_printable_ascii: true,
            })
        )
    }

    #[gtest]
    fn character_count_of_empty_text() -> Result<()> {
        verify_that!(character_count(b""), eq(0))
    }

    #[gtest]
    fn character_count_of_ascii_text() -> Result<()> {
        verify_that!(character_count(b"abc"), eq(3))
    }

    #[gtest]
    fn character_count_of_two_byte_characters() -> Result<()> {
        verify_that!(character_count("café".as_bytes()), eq(4))
    }

    #[gtest]
    fn character_count_of_three_byte_characters() -> Result<()> {
        verify_that!(character_count("日本語".as_bytes()), eq(3))
    }

    #[gtest]
    fn character_count_of_exactly_one_vector() -> Result<()> {
        verify_that!(character_count("éééééééééééééééé".as_bytes()), eq(16))
    }

    #[gtest]
    fn character_count_of_comment_shorter_than_one_vector() -> Result<()> {
        verify_that!(character_count("# Ça coûte 3 € 🎉".as_bytes()), eq(16))
    }

    #[gtest]
    fn character_count_of_comment_longer_than_two_vectors() -> Result<()> {
        verify_that!(
            character_count(
                "# Kommentar über die Größe: 日本語のコメント 🎉 und mehr Text.".as_bytes()
            ),
            eq(53)
        )
    }

    #[gtest]
    fn character_count_with_character_crossing_vectors() -> Result<()> {
        verify_that!(
            character_count("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa🎉b".as_bytes()),
            eq(32)
        )
    }

    #[gtest]
    fn character_count_of_exactly_two_vectors() -> Result<()> {
        verify_that!(character_count("é".repeat(32).as_bytes()), eq(32))
    }

    #[gtest]
    fn character_count_of_text_longer_than_two_vectors() -> Result<()> {
        verify_that!(character_count("é".repeat(40).as_bytes()), eq(40))
    }

    #[gtest]
    fn character_count_of_text_longer_than_one_vector() -> Result<()> {
        verify_that!(character_count("éééééééééééééééééééé".as_bytes()), eq(20))
    }

    #[gtest]
    fn rest_of_line_ending_at_line_feed() -> Result<()> {
        verify_that!(
            rest_of_line(indoc! {b"
                # a comment
                define the potential position<standard:/path>.
            "}),
            eq(RestOfLine {
                length: 11,
                is_printable_ascii: true,
            })
        )
    }

    #[gtest]
    fn rest_of_line_at_end_of_source() -> Result<()> {
        verify_that!(
            rest_of_line(b"# a comment"),
            eq(RestOfLine {
                length: 11,
                is_printable_ascii: true,
            })
        )
    }

    #[gtest]
    fn rest_of_line_with_non_ascii_character() -> Result<()> {
        verify_that!(
            rest_of_line("# café\n".as_bytes()),
            eq(RestOfLine {
                length: 7,
                is_printable_ascii: false,
            })
        )
    }

    #[gtest]
    fn rest_of_line_longer_than_one_vector() -> Result<()> {
        verify_that!(
            rest_of_line(indoc! {b"
                # A comment that is longer than one vector of thirty-two bytes.
                x
            "}),
            eq(RestOfLine {
                length: 63,
                is_printable_ascii: true,
            })
        )
    }

    #[gtest]
    fn rest_of_line_longer_than_one_vector_at_end_of_source() -> Result<()> {
        verify_that!(
            rest_of_line("# A comment that is longer than one vector, ending in é".as_bytes()),
            eq(RestOfLine {
                length: 56,
                is_printable_ascii: false,
            })
        )
    }

    #[gtest]
    fn rest_of_line_of_exactly_one_vector_at_end_of_source() -> Result<()> {
        verify_that!(
            rest_of_line(&[b'#'; 32]),
            eq(RestOfLine {
                length: 32,
                is_printable_ascii: true,
            })
        )
    }

    #[gtest]
    fn rest_of_line_of_exactly_two_vectors() {
        let source = [&[b'#'; 64][..], b"\nx"].concat();
        expect_that!(
            rest_of_line(&source),
            eq(RestOfLine {
                length: 64,
                is_printable_ascii: true,
            })
        );
    }

    #[gtest]
    fn rest_of_line_with_non_ascii_character_after_line_feed() -> Result<()> {
        verify_that!(
            rest_of_line(
                indoc! {"
                    # ascii
                    é
                "}
                .as_bytes()
            ),
            eq(RestOfLine {
                length: 7,
                is_printable_ascii: true,
            })
        )
    }

    #[gtest]
    fn rest_of_line_with_control_character() -> Result<()> {
        verify_that!(
            rest_of_line(b"# a\tcomment\n"),
            eq(RestOfLine {
                length: 11,
                is_printable_ascii: false,
            })
        )
    }

    #[gtest]
    fn rest_of_line_with_delete_character_longer_than_one_vector() -> Result<()> {
        verify_that!(
            rest_of_line(b"# A comment longer than one vector of bytes, ending in \x7f\n"),
            eq(RestOfLine {
                length: 56,
                is_printable_ascii: false,
            })
        )
    }

    #[gtest]
    fn rest_of_line_with_delete_character_in_first_vector() -> Result<()> {
        verify_that!(
            rest_of_line(b"# \x7f comment that is longer than one vector of bytes\n"),
            eq(RestOfLine {
                length: 51,
                is_printable_ascii: false,
            })
        )
    }

    #[gtest]
    fn low_bits_before_boundaries() {
        expect_that!(low_bits_before(0), eq(u32::MAX));
        expect_that!(low_bits_before(1), eq(0));
        expect_that!(low_bits_before(0b10100), eq(0b11));
        expect_that!(low_bits_before(1 << 31), eq(0x7FFF_FFFF));
    }

    #[gtest]
    fn in_range_mask_boundaries() -> Result<()> {
        let mut bytes = [0u8; WIDTH];
        bytes[0] = 0;
        bytes[1] = b'a' - 1;
        bytes[2] = b'a';
        bytes[3] = b'z';
        bytes[4] = b'z' + 1;
        bytes[5] = 254;
        bytes[6] = 255;
        let vector = u8x32::new(bytes);
        verify_that!(in_range_mask(vector, b'a', b'z'), eq(0b1100))?;
        verify_that!(in_range_mask(vector, 0, 254), eq(!(1u32 << 6)))
    }
}
