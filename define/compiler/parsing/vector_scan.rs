//! Scans of Define source that compare 32 bytes at a time.
//!
//! Each scan answers everything the parser needs to know about a span from as
//! few vector loads as possible.
//!
//! The width of 32 bytes was chosen by benchmarking 16-, 32-, and 64-byte
//! vectors on an AVX-512 machine. The benchmarks scanned spans sampled from
//! the repository's Define test data and from the source that
//! `//tools/generators:generate_large_define_source` generates, in a loop that
//! walked source lines the way the parser does:
//!
//! - Names are short. In the test data, half of them were at most 9 bytes and
//!   99% at most 50, so 32 bytes holds almost every name in one load. 16 bytes
//!   sent about a quarter of them to the slower path for spans longer than one
//!   vector.
//! - For names, 32 bytes was the fastest width or close to it, and about four
//!   times as fast as `memchr` followed by separate checks. 64 bytes was
//!   slower, because on short spans the wider vector costs more than it saves.
//! - For comments, 64 bytes was also slightly slower than 32.
//!
//! 32 bytes is also the native width of AVX2, which almost every x86-64
//! machine has; `wide` builds wider vectors from narrower ones on machines
//! without AVX-512.

// Everything in this module is optimized for performance, not readability
// (other than the tests). That's why the Scanner and other structs are in
// other files.

use wide::u8x32;

pub const NAME_CONTENT_END: u8 = b'>';
pub const COMPONENT_SEPARATOR: u8 = b':';
pub const PATH_SEPARATOR: u8 = b'/';
pub const SPACE: u8 = b' ';
pub const LINE_FEED: u8 = b'\n';

const WIDTH: usize = 32;

/// What a scan of name content found.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct NameContent {
    /// The length in bytes of the name content, which ends before the first
    /// `>` or line feed, or at the end of the source.
    pub length: usize,
    /// The number of UTF-8 characters in the name content.
    pub character_count: usize,
    pub is_ascii: bool,
    /// Whether the name content has the shape of a global name: optional text
    /// without spaces that ends in `:`, then `/` and at least one more byte.
    pub is_global_name: bool,
    /// The index of the last `:` in the name content.
    pub last_component_separator: Option<usize>,
}

/// Scans the name content at the start of `source`.
// Name content is the one span whose checks happen in the scan rather than in
// the parser: its global-name shape and its last `:` come from the same
// vector load that finds its end, which is much faster than separate passes
// over the name afterward.
#[inline]
#[must_use]
pub fn name_content(source: &[u8]) -> NameContent {
    let Some(&chunk) = source.first_chunk::<WIDTH>() else {
        return short_name_content(source);
    };
    let masks = NameContentMasks::of(u8x32::new(chunk));
    if masks.ends == 0 {
        return long_name_content(source);
    }
    name_content_in_vector(masks, masks.ends.trailing_zeros() as usize)
}

/// Masks of the bytes in one vector that a scan of name content looks for,
/// with one bit per byte.
#[derive(Clone, Copy)]
struct NameContentMasks {
    /// The `>` and line feed bytes, either of which ends name content.
    ends: u32,
    non_ascii: u32,
    /// The UTF-8 continuation bytes (`10xxxxxx`).
    continuation: u32,
    component_separators: u32,
    spaces: u32,
    path_separators: u32,
}

impl NameContentMasks {
    const NONE: Self = Self {
        ends: 0,
        non_ascii: 0,
        continuation: 0,
        component_separators: 0,
        spaces: 0,
        path_separators: 0,
    };

    #[inline]
    fn of(vector: u8x32) -> Self {
        Self {
            ends: mask(vector, NAME_CONTENT_END) | mask(vector, LINE_FEED),
            // The bitmask of a vector is the high bit of each of its bytes,
            // which is clear exactly for ASCII bytes.
            non_ascii: vector.to_bitmask(),
            continuation: continuation_byte_mask(vector),
            component_separators: mask(vector, COMPONENT_SEPARATOR),
            spaces: mask(vector, SPACE),
            path_separators: mask(vector, PATH_SEPARATOR),
        }
    }

    /// Returns the masks of the last `count` bytes of the vector, moved to the
    /// lowest bits, where `count` is from 1 to 31.
    #[inline]
    const fn last(self, count: usize) -> Self {
        let shift = WIDTH - count;
        Self {
            ends: self.ends >> shift,
            non_ascii: self.non_ascii >> shift,
            continuation: self.continuation >> shift,
            component_separators: self.component_separators >> shift,
            spaces: self.spaces >> shift,
            path_separators: self.path_separators >> shift,
        }
    }
}

/// Scans name content that starts fewer than 32 bytes before the end of the
/// source.
// A separate function, so that copying into a zeroed array, which is slow,
// happens only near the end of the source, and so that the vector in
// `name_content` stays in a register instead of passing through memory.
#[cold]
#[inline(never)]
fn short_name_content(source: &[u8]) -> NameContent {
    let mut masks = NameContentMasks::of(zero_padded(source));
    masks.ends |= !low_bits(source.len());
    name_content_in_vector(masks, masks.ends.trailing_zeros() as usize)
}

/// Scans the first `length` bytes of a vector with `masks`, where `length` is
/// less than 32.
#[inline]
const fn name_content_in_vector(masks: NameContentMasks, length: usize) -> NameContent {
    let within = low_bits(length);
    let component_separators = masks.component_separators & within;
    // A `/` can begin the path of a global name when it is first or follows a
    // `:`, and when at least one more byte follows it in the name content.
    let path_starts = masks.path_separators & ((component_separators << 1) | 1) & (within >> 1);
    NameContent {
        length,
        character_count: length - (masks.continuation & within).count_ones() as usize,
        is_ascii: masks.non_ascii & within == 0,
        is_global_name: path_starts.trailing_zeros() < (masks.spaces & within).trailing_zeros(),
        last_component_separator: if component_separators == 0 {
            None
        } else {
            Some((u32::BITS - 1 - component_separators.leading_zeros()) as usize)
        },
    }
}

/// Whether the name content scanned so far has the shape of a global name.
#[derive(Clone, Copy, PartialEq, Eq)]
enum GlobalNameShape {
    /// No `/` that can begin a path and no space has been found yet.
    Undecided,
    /// The last byte of the previous vector is a `/` that can begin a path, so
    /// the name content is a global name if any byte follows it.
    PathStartAtPreviousEnd,
    Global,
    NotGlobal,
}

/// Scans name content that is at least 32 bytes long, one vector at a time.
// This examines the first vector again rather than taking its masks from
// `name_content`, because passing the masks would make every name store them
// in memory, while only long names need them.
#[inline(never)]
fn long_name_content(source: &[u8]) -> NameContent {
    let mut scan = LongNameContentScan::new();
    // The full vectors and the final partial one are separate, so that the
    // loop has no branch for a partial vector and its state stays in
    // registers.
    let (chunks, remainder) = source.as_chunks::<WIDTH>();
    for &chunk in chunks {
        let masks = NameContentMasks::of(u8x32::new(chunk));
        if masks.ends != 0 {
            return scan.finish(masks, masks.ends.trailing_zeros() as usize);
        }
        scan.add(masks, WIDTH, false);
    }
    if remainder.is_empty() {
        return scan.finish(NameContentMasks::NONE, 0);
    }
    // Loading the last 32 bytes of the source, which overlap bytes already
    // scanned, is much faster than copying the remainder into a zeroed array.
    let Some(&last_chunk) = source.last_chunk::<WIDTH>() else {
        unreachable!("long name content is at least 32 bytes long");
    };
    let mut masks = NameContentMasks::of(u8x32::new(last_chunk)).last(remainder.len());
    masks.ends |= !low_bits(remainder.len());
    scan.finish(masks, masks.ends.trailing_zeros() as usize)
}

/// What a scan of name content longer than one vector has found so far.
struct LongNameContentScan {
    /// The index in the name content of the next vector's first byte.
    offset: usize,
    non_ascii_bytes: u32,
    continuation_bytes: usize,
    /// One more than the index of the last `:`, or 0 if there is none yet,
    /// which fits in one register where an `Option<usize>` needs two.
    last_component_separator_end: usize,
    shape: GlobalNameShape,
    /// Bit 0 is set when a `/` at the start of the next vector can begin a
    /// path: at the start of the name content, or after a `:` that ended the
    /// previous vector.
    follows_component_separator: u32,
}

impl LongNameContentScan {
    const fn new() -> Self {
        Self {
            offset: 0,
            non_ascii_bytes: 0,
            continuation_bytes: 0,
            last_component_separator_end: 0,
            shape: GlobalNameShape::Undecided,
            follows_component_separator: 1,
        }
    }

    /// Adds the first `length` bytes of the next vector of the name content,
    /// given its `masks`. `is_last` is whether the name content ends in this
    /// vector.
    #[inline]
    fn add(&mut self, masks: NameContentMasks, length: usize, is_last: bool) {
        let within = low_bits(length);
        self.non_ascii_bytes |= masks.non_ascii & within;
        self.continuation_bytes += (masks.continuation & within).count_ones() as usize;
        let component_separators = masks.component_separators & within;
        if component_separators != 0 {
            self.last_component_separator_end =
                self.offset + (u32::BITS - component_separators.leading_zeros()) as usize;
        }
        self.shape = match self.shape {
            GlobalNameShape::Undecided => {
                let spaces = masks.spaces & within;
                let path_starts = masks.path_separators
                    & ((component_separators << 1) | self.follows_component_separator)
                    & within;
                let first_path_start = path_starts.trailing_zeros();
                if first_path_start >= spaces.trailing_zeros() {
                    if spaces == 0 {
                        GlobalNameShape::Undecided
                    } else {
                        GlobalNameShape::NotGlobal
                    }
                } else if (first_path_start as usize) + 1 < length {
                    GlobalNameShape::Global
                } else if is_last {
                    GlobalNameShape::NotGlobal
                } else {
                    GlobalNameShape::PathStartAtPreviousEnd
                }
            }
            GlobalNameShape::PathStartAtPreviousEnd => {
                if length == 0 {
                    GlobalNameShape::NotGlobal
                } else {
                    GlobalNameShape::Global
                }
            }
            decided => decided,
        };
        self.follows_component_separator = component_separators >> (WIDTH - 1);
        self.offset += WIDTH;
    }

    /// Adds the first `length` bytes of the vector in which the name content
    /// ends, given its `masks`, and returns what the scan found.
    #[inline]
    fn finish(mut self, masks: NameContentMasks, length: usize) -> NameContent {
        let total_length = self.offset + length;
        self.add(masks, length, true);
        NameContent {
            length: total_length,
            character_count: total_length - self.continuation_bytes,
            is_ascii: self.non_ascii_bytes == 0,
            is_global_name: self.shape == GlobalNameShape::Global,
            last_component_separator: self.last_component_separator_end.checked_sub(1),
        }
    }
}

/// Counts the UTF-8 characters in `text`.
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
fn continuation_byte_mask(vector: u8x32) -> u32 {
    // As signed bytes, the continuation bytes are exactly the values below -64.
    vector
        .cast_signed()
        .simd_lt(wide::i8x32::splat(-64))
        .to_bitmask()
}

/// Returns a mask with a bit set for each byte of `vector` that is `byte`.
#[inline]
fn mask(vector: u8x32, byte: u8) -> u32 {
    vector.simd_eq(u8x32::splat(byte)).to_bitmask()
}

/// Returns the bytes of `bytes`, which has fewer than 32, followed by zeros.
#[inline]
fn zero_padded(bytes: &[u8]) -> u8x32 {
    let mut chunk = [0; WIDTH];
    chunk[..bytes.len()].copy_from_slice(bytes);
    u8x32::new(chunk)
}

/// Returns a mask of the lowest `count` bits, where `count` is at most 32.
#[inline]
const fn low_bits(count: usize) -> u32 {
    if count >= WIDTH {
        u32::MAX
    } else {
        (1 << count) - 1
    }
}

// These tests cover the scans' own logic: what each scan reports, and the
// separate paths for spans near the end of the source and for spans longer
// than one vector. They are not tests of Define syntax, which the parser
// tests cover.
#[cfg(test)]
mod tests {
    use super::*;
    use googletest::prelude::*;

    #[gtest]
    fn name_content_with_fqun() {
        expect_that!(
            name_content(b"standard:/path>.\ndefine the potential position<standard:/other>.\n"),
            eq(NameContent {
                length: 14,
                character_count: 14,
                is_ascii: true,
                is_global_name: true,
                last_component_separator: Some(8),
            })
        );
    }

    #[gtest]
    fn name_content_with_several_component_separators() {
        expect_that!(
            name_content(b"authority:universe:/a/b>.\ndefine the potential position<x>.\n"),
            eq(NameContent {
                length: 23,
                character_count: 23,
                is_ascii: true,
                is_global_name: true,
                last_component_separator: Some(18),
            })
        );
    }

    #[gtest]
    fn name_content_with_path_only() {
        expect_that!(
            name_content(b"/path>.\ndefine the potential position<standard:/other>.\n"),
            eq(NameContent {
                length: 5,
                character_count: 5,
                is_ascii: true,
                is_global_name: true,
                last_component_separator: None,
            })
        );
    }

    #[gtest]
    fn name_content_with_space_before_path_is_not_global() {
        expect_that!(
            name_content(b"a b:/c>.\ndefine the potential position<standard:/other>.\n"),
            eq(NameContent {
                length: 6,
                character_count: 6,
                is_ascii: true,
                is_global_name: false,
                last_component_separator: Some(3),
            })
        );
    }

    #[gtest]
    fn name_content_with_empty_path_is_not_global() {
        expect_that!(
            name_content(b"standard:/>.\ndefine the potential position<standard:/other>.\n"),
            eq(NameContent {
                length: 10,
                character_count: 10,
                is_ascii: true,
                is_global_name: false,
                last_component_separator: Some(8),
            })
        );
    }

    #[gtest]
    fn name_content_with_slash_after_letter_is_not_global() {
        expect_that!(
            name_content(b"x/y>.\ndefine the potential position<standard:/other>.\n"),
            eq(NameContent {
                length: 3,
                character_count: 3,
                is_ascii: true,
                is_global_name: false,
                last_component_separator: None,
            })
        );
    }

    #[gtest]
    fn name_content_ends_at_line_feed() {
        expect_that!(
            name_content(b"standard:/path\ndefine the potential position<standard:/other>.\n"),
            eq(NameContent {
                length: 14,
                character_count: 14,
                is_ascii: true,
                is_global_name: true,
                last_component_separator: Some(8),
            })
        );
    }

    #[gtest]
    fn name_content_with_non_ascii_character() {
        expect_that!(
            name_content("café:/x>.\ndefine the potential position<standard:/other>.\n".as_bytes()),
            eq(NameContent {
                length: 8,
                character_count: 7,
                is_ascii: false,
                is_global_name: true,
                last_component_separator: Some(5),
            })
        );
    }

    #[gtest]
    fn name_content_at_end_of_source() {
        expect_that!(
            name_content(b"standard:/path"),
            eq(NameContent {
                length: 14,
                character_count: 14,
                is_ascii: true,
                is_global_name: true,
                last_component_separator: Some(8),
            })
        );
    }

    #[gtest]
    fn name_content_before_end_of_source() {
        expect_that!(
            name_content(b"standard:/path>.\n"),
            eq(NameContent {
                length: 14,
                character_count: 14,
                is_ascii: true,
                is_global_name: true,
                last_component_separator: Some(8),
            })
        );
    }

    #[gtest]
    fn name_content_longer_than_one_vector() {
        expect_that!(
            name_content(
                b"multiverse:authority.example:universe:/a/very/long/path>.\ndefine the potential position<x>.\n"
            ),
            eq(NameContent {
                length: 55,
                character_count: 55,
                is_ascii: true,
                is_global_name: true,
                last_component_separator: Some(37),
            })
        );
    }

    #[gtest]
    fn name_content_with_path_starting_at_last_byte_of_vector() {
        expect_that!(
            name_content(b"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa:/b>.\n"),
            eq(NameContent {
                length: 33,
                character_count: 33,
                is_ascii: true,
                is_global_name: true,
                last_component_separator: Some(30),
            })
        );
    }

    #[gtest]
    fn name_content_longer_than_one_vector_with_space_before_path() {
        expect_that!(
            name_content(b"this name content has spaces in it:/x>.\n"),
            eq(NameContent {
                length: 37,
                character_count: 37,
                is_ascii: true,
                is_global_name: false,
                last_component_separator: Some(34),
            })
        );
    }

    #[gtest]
    fn name_content_longer_than_one_vector_without_path() {
        expect_that!(
            name_content(b"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa>.\n"),
            eq(NameContent {
                length: 36,
                character_count: 36,
                is_ascii: true,
                is_global_name: false,
                last_component_separator: None,
            })
        );
    }

    #[gtest]
    fn name_content_with_empty_path_at_last_byte_of_vector() {
        expect_that!(
            name_content(b"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa:/>.\n"),
            eq(NameContent {
                length: 32,
                character_count: 32,
                is_ascii: true,
                is_global_name: false,
                last_component_separator: Some(30),
            })
        );
    }

    #[gtest]
    fn name_content_with_empty_path_in_second_vector() {
        expect_that!(
            name_content(b"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa:/>.\n"),
            eq(NameContent {
                length: 35,
                character_count: 35,
                is_ascii: true,
                is_global_name: false,
                last_component_separator: Some(33),
            })
        );
    }

    #[gtest]
    fn name_content_with_component_separator_at_last_byte_of_vector() {
        expect_that!(
            name_content(b"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa:/b>.\n"),
            eq(NameContent {
                length: 34,
                character_count: 34,
                is_ascii: true,
                is_global_name: true,
                last_component_separator: Some(31),
            })
        );
    }

    #[gtest]
    fn name_content_with_space_in_second_vector() {
        expect_that!(
            name_content(b"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa a:/b>.\n"),
            eq(NameContent {
                length: 38,
                character_count: 38,
                is_ascii: true,
                is_global_name: false,
                last_component_separator: Some(35),
            })
        );
    }

    #[gtest]
    fn name_content_with_non_ascii_character_in_second_vector() {
        expect_that!(
            name_content("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaé:/x>.\n".as_bytes()),
            eq(NameContent {
                length: 37,
                character_count: 36,
                is_ascii: false,
                is_global_name: true,
                last_component_separator: Some(34),
            })
        );
    }

    #[gtest]
    fn name_content_of_exactly_two_vectors() {
        let source = [&[b'a'; 60][..], b":/bc>.\n"].concat();
        expect_that!(
            name_content(&source),
            eq(NameContent {
                length: 64,
                character_count: 64,
                is_ascii: true,
                is_global_name: true,
                last_component_separator: Some(60),
            })
        );
    }

    #[gtest]
    fn name_content_of_exactly_two_vectors_at_end_of_source() {
        let source = [&[b'a'; 60][..], b":/bc"].concat();
        expect_that!(
            name_content(&source),
            eq(NameContent {
                length: 64,
                character_count: 64,
                is_ascii: true,
                is_global_name: true,
                last_component_separator: Some(60),
            })
        );
    }

    #[gtest]
    fn name_content_longer_than_two_vectors() {
        let source = [&[b'a'; 65][..], b":/b>.\n"].concat();
        expect_that!(
            name_content(&source),
            eq(NameContent {
                length: 68,
                character_count: 68,
                is_ascii: true,
                is_global_name: true,
                last_component_separator: Some(65),
            })
        );
    }

    #[gtest]
    fn name_content_with_path_starting_at_last_byte_of_second_vector() {
        let source = [&[b'a'; 62][..], b":/b>.\n"].concat();
        expect_that!(
            name_content(&source),
            eq(NameContent {
                length: 65,
                character_count: 65,
                is_ascii: true,
                is_global_name: true,
                last_component_separator: Some(62),
            })
        );
    }

    #[gtest]
    fn character_count_of_empty_text() {
        expect_that!(character_count(b""), eq(0));
    }

    #[gtest]
    fn character_count_of_ascii_text() {
        expect_that!(character_count(b"abc"), eq(3));
    }

    #[gtest]
    fn character_count_of_two_byte_characters() {
        expect_that!(character_count("café".as_bytes()), eq(4));
    }

    #[gtest]
    fn character_count_of_three_byte_characters() {
        expect_that!(character_count("日本語".as_bytes()), eq(3));
    }

    #[gtest]
    fn character_count_of_exactly_one_vector() {
        expect_that!(character_count("éééééééééééééééé".as_bytes()), eq(16));
    }

    #[gtest]
    fn character_count_of_comment_shorter_than_one_vector() {
        expect_that!(character_count("# Ça coûte 3 € 🎉".as_bytes()), eq(16));
    }

    #[gtest]
    fn character_count_of_comment_longer_than_two_vectors() {
        expect_that!(
            character_count(
                "# Kommentar über die Größe: 日本語のコメント 🎉 und mehr Text.".as_bytes()
            ),
            eq(53)
        );
    }

    #[gtest]
    fn character_count_with_character_crossing_vectors() {
        expect_that!(
            character_count("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa🎉b".as_bytes()),
            eq(32)
        );
    }

    #[gtest]
    fn character_count_of_exactly_two_vectors() {
        expect_that!(character_count("é".repeat(32).as_bytes()), eq(32));
    }

    #[gtest]
    fn character_count_of_text_longer_than_two_vectors() {
        expect_that!(character_count("é".repeat(40).as_bytes()), eq(40));
    }

    #[gtest]
    fn character_count_of_text_longer_than_one_vector() {
        expect_that!(character_count("éééééééééééééééééééé".as_bytes()), eq(20));
    }
}
