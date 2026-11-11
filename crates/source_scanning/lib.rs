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

use wide::u8x32;

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
    let (chunks, remainder) = source.as_chunks::<WIDTH>();
    let mut unprintable = 0;
    let mut continuation_bytes = 0;
    for (index, &chunk) in chunks.iter().enumerate() {
        let vector = u8x32::new(chunk);
        let stops = quoted_content_stops(vector);
        if stops != 0 {
            let length = stops.trailing_zeros() as usize;
            let within = low_bits(length);
            unprintable |= unprintable_mask(vector) & within;
            continuation_bytes += (continuation_byte_mask(vector) & within).count_ones() as usize;
            let length = index * WIDTH + length;
            return QuotedContent {
                length,
                character_count: length - continuation_bytes,
                is_printable_ascii: unprintable == 0,
            };
        }
        unprintable |= unprintable_mask(vector);
        continuation_bytes += continuation_byte_mask(vector).count_ones() as usize;
    }
    let (stops, remainder_unprintable, remainder_continuation) = match source.last_chunk::<WIDTH>()
    {
        // Loading the last 32 bytes of the source, which overlap bytes
        // already scanned, is much faster than copying the remainder into
        // a zeroed array.
        Some(&last_chunk) if !remainder.is_empty() => {
            let vector = u8x32::new(last_chunk);
            let shift = WIDTH - remainder.len();
            (
                quoted_content_stops(vector) >> shift,
                unprintable_mask(vector) >> shift,
                continuation_byte_mask(vector) >> shift,
            )
        }
        // For a source shorter than one vector, a byte loop is faster than
        // copying it into a zeroed array.
        _ => {
            let mut stops = 0;
            let mut remainder_unprintable = 0;
            let mut continuation = 0;
            for (index, &byte) in remainder.iter().enumerate() {
                stops |= u32::from(matches!(byte, QUOTE | ESCAPE | LINE_FEED)) << index;
                remainder_unprintable |= u32::from(!(b' '..=b'~').contains(&byte)) << index;
                continuation |= u32::from(byte & 0b1100_0000 == 0b1000_0000) << index;
            }
            (stops, remainder_unprintable, continuation)
        }
    };
    let remainder_length = if stops == 0 {
        remainder.len()
    } else {
        stops.trailing_zeros() as usize
    };
    let within = low_bits(remainder_length);
    let length = chunks.len() * WIDTH + remainder_length;
    QuotedContent {
        length,
        character_count: length
            - continuation_bytes
            - (remainder_continuation & within).count_ones() as usize,
        is_printable_ascii: unprintable == 0 && remainder_unprintable & within == 0,
    }
}

/// Returns a mask of the bytes in `vector` at which a scan of quoted content
/// stops: `"`, `\`, and line feed.
#[inline]
fn quoted_content_stops(vector: u8x32) -> u32 {
    byte_mask(vector, QUOTE) | byte_mask(vector, ESCAPE) | byte_mask(vector, LINE_FEED)
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
    let (chunks, remainder) = source.as_chunks::<WIDTH>();
    let mut unprintable = 0;
    for (index, &chunk) in chunks.iter().enumerate() {
        let vector = u8x32::new(chunk);
        let line_feeds = byte_mask(vector, LINE_FEED);
        if line_feeds != 0 {
            let length = line_feeds.trailing_zeros() as usize;
            unprintable |= unprintable_mask(vector) & low_bits(length);
            return RestOfLine {
                length: index * WIDTH + length,
                is_printable_ascii: unprintable == 0,
            };
        }
        unprintable |= unprintable_mask(vector);
    }
    let offset = chunks.len() * WIDTH;
    let (line_feeds, remainder_unprintable) = match source.last_chunk::<WIDTH>() {
        // Loading the last 32 bytes of the source, which overlap bytes already
        // scanned, is much faster than copying the remainder into a zeroed
        // array.
        Some(&last_chunk) if !remainder.is_empty() => {
            let vector = u8x32::new(last_chunk);
            let shift = WIDTH - remainder.len();
            (
                byte_mask(vector, LINE_FEED) >> shift,
                unprintable_mask(vector) >> shift,
            )
        }
        // For a source shorter than one vector, a byte loop is faster than
        // copying it into a zeroed array.
        _ => {
            let mut line_feeds = 0;
            let mut remainder_unprintable = 0;
            for (index, &byte) in remainder.iter().enumerate() {
                line_feeds |= u32::from(byte == LINE_FEED) << index;
                remainder_unprintable |= u32::from(!(b' '..=b'~').contains(&byte)) << index;
            }
            (line_feeds, remainder_unprintable)
        }
    };
    let length = if line_feeds == 0 {
        remainder.len()
    } else {
        line_feeds.trailing_zeros() as usize
    };
    RestOfLine {
        length: offset + length,
        is_printable_ascii: unprintable == 0 && remainder_unprintable & low_bits(length) == 0,
    }
}

/// Returns a mask of the bytes in `vector` that are not from ` ` through `~`.
#[inline]
#[must_use]
pub fn unprintable_mask(vector: u8x32) -> u32 {
    !in_range_mask(vector, b' ', b'~')
}

/// Returns a mask of the bytes in `vector` from `low` through `high`.
#[inline]
#[must_use]
pub fn in_range_mask(vector: u8x32, low: u8, high: u8) -> u32 {
    // Subtracting wraps, so the bytes in the range are exactly those that
    // become at most `high` - `low`.
    let offset = vector - u8x32::splat(low);
    offset
        .min(u8x32::splat(high - low))
        .simd_eq(offset)
        .to_bitmask()
}

/// Counts the UTF-8 characters in `text`.
#[inline]
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
    vector
        .cast_signed()
        .simd_lt(wide::i8x32::splat(-64))
        .to_bitmask()
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

#[cfg(test)]
mod tests {
    use super::*;
    use googletest::prelude::*;

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
            quoted_content(b"a\\\"b\".\ndefine the potential position<standard:/after>.\n"),
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
            quoted_content(b"abc\ndefine the potential position<standard:/after>.\n"),
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
            quoted_content("café\".\ndefine the potential position<standard:/after>.\n".as_bytes()),
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
            quoted_content(b"a\tb\".\ndefine the potential position<standard:/after>.\n"),
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
            rest_of_line(b"# a comment\ndefine the potential position<standard:/path>.\n"),
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
            rest_of_line(b"# A comment that is longer than one vector of thirty-two bytes.\nx\n"),
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
            rest_of_line("# ascii\né\n".as_bytes()),
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
}
