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

use std::marker::PhantomData;
use std::num::NonZeroU32;
use terminals::{
    COMMENT_START, COMPONENT_SEPARATOR, LINE_FEED, NAME_CONTENT_END, PATH_SEPARATOR, SPACE,
};
use wide::u8x32;

const WIDTH: usize = 32;
/// `WIDTH` as a `u32`, for the indexes in name content, which are `u32`s so
/// that a scan's result and state fit in fewer registers.
const WIDTH_U32: u32 = 32;
const _: () = assert!(WIDTH_U32 as usize == WIDTH);

/// Where the `:`s before a global name's path are, which end the components
/// of its FQUN.
// Four `u32`s, with a count that is never zero, make an
// `Option<FqunSeparators>` as small as an `Option<usize>`, and let a scan make
// `None` without a branch.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct FqunSeparators {
    /// How many there are. An FQUN has at most three components, so more than
    /// three is an FQUN that is not valid.
    pub count: NonZeroU32,
    /// The index of the first, or of the last if there is only one.
    pub first: u32,
    /// The index of the second, or of the last if there are fewer than two.
    pub second: u32,
    /// The index of the last, which comes right before the path.
    pub last: u32,
}

/// What a scan of name content where only a global name belongs found.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct GlobalNameContent {
    /// The length in bytes of the name content, which ends before the first
    /// `>` or line feed, or at the end of the source.
    pub length: usize,
    /// The number of UTF-8 characters in the name content.
    pub character_count: usize,
    /// Whether every byte of the name content is from ` ` through `~`.
    pub is_printable_ascii: bool,
    /// Whether the name content has the shape of a global name: optional text
    /// without spaces that ends in `:`, then `/` and at least one more byte.
    pub is_global_name: bool,
    /// For a global name with an FQUN, where the `:`s before its path are.
    /// `None` for a global name without an FQUN, and for name content that is
    /// not a global name.
    pub fqun_separators: Option<FqunSeparators>,
}

/// What a scan of name content where a local name may belong found.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct NameContent {
    /// The length in bytes of the name content, which ends before the first
    /// `>` or line feed, or at the end of the source.
    pub length: usize,
    /// The number of UTF-8 characters in the name content.
    pub character_count: usize,
    /// Whether every byte of the name content is from ` ` through `~`.
    pub is_printable_ascii: bool,
    /// Whether the name content has the shape of a global name: optional text
    /// without spaces that ends in `:`, then `/` and at least one more byte.
    pub is_global_name: bool,
    /// For a global name with an FQUN, where the `:`s before its path are.
    /// `None` for a global name without an FQUN, and for name content that is
    /// not a global name.
    pub fqun_separators: Option<FqunSeparators>,
    /// Whether the name content is not empty and has no space, `:`, or `/`,
    /// which a local name may not have.
    pub is_local_name: bool,
}

/// What a scan of name content reports, which is whether the name content
/// is a local name only when `FINDS_LOCAL_NAMES` is true.
// Each scan builds its own result type on every path, so that a scan that
// skips the work for local names does not copy a larger result into a smaller
// one.
trait ScannedNameContent {
    const FINDS_LOCAL_NAMES: bool;

    fn new(
        length: usize,
        character_count: usize,
        is_printable_ascii: bool,
        is_global_name: bool,
        fqun_separators: Option<FqunSeparators>,
        is_local_name: bool,
    ) -> Self;
}

impl ScannedNameContent for GlobalNameContent {
    const FINDS_LOCAL_NAMES: bool = false;

    #[inline(always)]
    fn new(
        length: usize,
        character_count: usize,
        is_printable_ascii: bool,
        is_global_name: bool,
        fqun_separators: Option<FqunSeparators>,
        _: bool,
    ) -> Self {
        Self {
            length,
            character_count,
            is_printable_ascii,
            is_global_name,
            fqun_separators,
        }
    }
}

impl ScannedNameContent for NameContent {
    const FINDS_LOCAL_NAMES: bool = true;

    #[inline(always)]
    fn new(
        length: usize,
        character_count: usize,
        is_printable_ascii: bool,
        is_global_name: bool,
        fqun_separators: Option<FqunSeparators>,
        is_local_name: bool,
    ) -> Self {
        Self {
            length,
            character_count,
            is_printable_ascii,
            is_global_name,
            fqun_separators,
            is_local_name,
        }
    }
}

/// Scans the name content at the start of `source`, where only a global name
/// belongs.
#[inline]
#[must_use]
pub fn global_name_content(source: &[u8]) -> GlobalNameContent {
    scan_name_content(source)
}

/// Scans the name content at the start of `source`, where a local name may
/// belong.
#[inline]
#[must_use]
pub fn name_content(source: &[u8]) -> NameContent {
    scan_name_content(source)
}

// Name content is the one span whose checks happen in the scan rather than in
// the parser: its global-name shape and its last `:` come from the same
// vector load that finds its end, which is much faster than separate passes
// over the name afterward. Where only a global name belongs, the scan skips
// the work for local names, which costs about a quarter of a scan.
#[inline(always)]
fn scan_name_content<Scanned: ScannedNameContent>(source: &[u8]) -> Scanned {
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
    /// The bytes that are not from ` ` through `~`.
    unprintable: u32,
    /// The UTF-8 continuation bytes (`10xxxxxx`).
    continuation: u32,
    component_separators: u32,
    spaces: u32,
    path_separators: u32,
}

impl NameContentMasks {
    const NONE: Self = Self {
        ends: 0,
        unprintable: 0,
        continuation: 0,
        component_separators: 0,
        spaces: 0,
        path_separators: 0,
    };

    #[inline]
    fn of(vector: u8x32) -> Self {
        Self {
            ends: mask(vector, NAME_CONTENT_END) | mask(vector, LINE_FEED),
            unprintable: unprintable_mask(vector),
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
            unprintable: self.unprintable >> shift,
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
fn short_name_content<Scanned: ScannedNameContent>(source: &[u8]) -> Scanned {
    let mut masks = NameContentMasks::of(zero_padded(source));
    masks.ends |= !low_bits(source.len());
    name_content_in_vector(masks, masks.ends.trailing_zeros() as usize)
}

/// Scans the first `length` bytes of a vector with `masks`, where `length` is
/// less than 32.
#[inline]
fn name_content_in_vector<Scanned: ScannedNameContent>(
    masks: NameContentMasks,
    length: usize,
) -> Scanned {
    let within = low_bits(length);
    let component_separators = masks.component_separators & within;
    // A `/` can begin the path of a global name when it is first or follows a
    // `:`, and when at least one more byte follows it in the name content.
    let path_starts = masks.path_separators & ((component_separators << 1) | 1) & (within >> 1);
    let first_path_start = path_starts.trailing_zeros();
    let is_global_name = first_path_start < (masks.spaces & within).trailing_zeros();
    // The `:`s before the first `/` that can begin a path. A global name's
    // path follows its last `:`, if it has one.
    let fqun_separators = component_separators & !path_starts & path_starts.wrapping_sub(1);
    let last = first_path_start.wrapping_sub(1);
    // The fields are computed before the `Option` is, so that `None`, which
    // is only a count of 0, is no branch away from `Some`.
    let first = fqun_separators.trailing_zeros();
    let second = (fqun_separators & fqun_separators.wrapping_sub(1))
        .trailing_zeros()
        .min(last);
    let count = fqun_separators.count_ones() & 0u32.wrapping_sub(u32::from(is_global_name));
    Scanned::new(
        length,
        length - (masks.continuation & within).count_ones() as usize,
        masks.unprintable & within == 0,
        is_global_name,
        NonZeroU32::new(count).map(|count| FqunSeparators {
            count,
            first,
            second,
            last,
        }),
        // `&` rather than `&&`, which compiles to a branch.
        Scanned::FINDS_LOCAL_NAMES
            & (length != 0)
            & ((component_separators | masks.path_separators | masks.spaces) & within == 0),
    )
}

/// Scans name content that is at least 32 bytes long, one vector at a time.
// The scan has two loops. The first runs until the name content is known to
// be a global name or not, and is the only one that tracks what that and the
// FQUN's `:`s need. The second only counts bytes, so that neither loop carries
// more state than fits in registers.
//
// This examines the first vector again rather than taking its masks from
// `name_content`, because passing the masks would make every name store them
// in memory, while only long names need them.
#[inline(never)]
fn long_name_content<Scanned: ScannedNameContent>(source: &[u8]) -> Scanned {
    let (chunks, remainder) = source.as_chunks::<WIDTH>();
    let mut bytes = LongNameBytes::new();
    let mut undecided = UndecidedName::<Scanned>::new();
    // The full vectors and the final partial one are separate, so that the
    // loops have no branch for a partial vector.
    let mut chunks = chunks.iter();
    let decided = loop {
        let Some(&chunk) = chunks.next() else {
            let (masks, length) = last_vector_masks(source, remainder.len());
            return undecided.finish(bytes, masks, length);
        };
        let masks = NameContentMasks::of(u8x32::new(chunk));
        if masks.ends != 0 {
            return undecided.finish(bytes, masks, masks.ends.trailing_zeros() as usize);
        }
        if let Some(decided) = undecided.add(masks, bytes.offset) {
            bytes.add(masks, WIDTH);
            break decided;
        }
        bytes.add(masks, WIDTH);
    };
    for &chunk in chunks {
        let masks = NameContentMasks::of(u8x32::new(chunk));
        if masks.ends != 0 {
            return decided.finish(bytes, masks, masks.ends.trailing_zeros() as usize);
        }
        bytes.add(masks, WIDTH);
    }
    let (masks, length) = last_vector_masks(source, remainder.len());
    decided.finish(bytes, masks, length)
}

/// Returns the masks of the last vector of long name content, which runs to
/// the end of `source` and has `remainder` bytes after its full vectors, with
/// the length of the name content in it.
#[inline]
fn last_vector_masks(source: &[u8], remainder: usize) -> (NameContentMasks, usize) {
    if remainder == 0 {
        return (NameContentMasks::NONE, 0);
    }
    // Loading the last 32 bytes of the source, which overlap bytes already
    // scanned, is much faster than copying the remainder into a zeroed array.
    let Some(&last_chunk) = source.last_chunk::<WIDTH>() else {
        unreachable!("long name content is at least 32 bytes long");
    };
    let mut masks = NameContentMasks::of(u8x32::new(last_chunk)).last(remainder);
    masks.ends |= !low_bits(remainder);
    (masks, masks.ends.trailing_zeros() as usize)
}

/// What a scan of long name content has counted in all of its bytes so far.
#[derive(Clone, Copy)]
struct LongNameBytes {
    /// The index in the name content of the next vector's first byte.
    offset: u32,
    unprintable_bytes: u32,
    continuation_bytes: usize,
}

impl LongNameBytes {
    const fn new() -> Self {
        Self {
            offset: 0,
            unprintable_bytes: 0,
            continuation_bytes: 0,
        }
    }

    /// Adds the first `length` bytes of the next vector, given its `masks`.
    #[inline]
    fn add(&mut self, masks: NameContentMasks, length: usize) {
        let within = low_bits(length);
        self.unprintable_bytes |= masks.unprintable & within;
        self.continuation_bytes += (masks.continuation & within).count_ones() as usize;
        self.offset += WIDTH_U32;
    }
}

/// What a scan of long name content, which reports a `Scanned`, tracks
/// before it knows whether the name content is a global name.
struct UndecidedName<Scanned> {
    /// The spaces, `:`, and `/` found so far, which a local name may not have.
    local_name_breaks: u32,
    /// Bit 0 is set when a `/` at the start of the next vector can begin a
    /// path: at the start of the name content, or after a `:` that ended the
    /// previous vector.
    follows_component_separator: u32,
    /// How many `:`s have come before any `/` that can begin a path, so far.
    fqun_separator_count: u32,
    /// The indexes of the first two of those `:`s, or `u32::MAX` until they
    /// are found, which `min` with the index of the last `:` replaces.
    first_fqun_separator: u32,
    second_fqun_separator: u32,
    scanned: PhantomData<Scanned>,
}

/// What a scan of long name content found once it knew whether the name
/// content is a global name.
#[derive(Clone, Copy)]
struct DecidedName {
    /// Whether a `/` that can begin a path comes before any space, which makes
    /// the name content a global name if at least one byte follows the `/`.
    has_path_start: bool,
    /// The index of that `/`.
    path_start: u32,
    fqun_separator_count: u32,
    first_fqun_separator: u32,
    second_fqun_separator: u32,
}

impl<Scanned: ScannedNameContent> UndecidedName<Scanned> {
    const fn new() -> Self {
        Self {
            local_name_breaks: 0,
            follows_component_separator: 1,
            fqun_separator_count: 0,
            first_fqun_separator: u32::MAX,
            second_fqun_separator: u32::MAX,
            scanned: PhantomData,
        }
    }

    /// Adds the next full vector, which begins at `offset` and has no end of
    /// the name content in it, given its `masks`. Returns what the scan found
    /// if the vector has a space or a `/` that can begin a path.
    #[inline]
    fn add(&mut self, masks: NameContentMasks, offset: u32) -> Option<DecidedName> {
        let path_starts = self.add_separators(masks, u32::MAX, offset);
        let first_path_start = path_starts.trailing_zeros();
        let first_space = masks.spaces.trailing_zeros();
        if first_path_start < first_space {
            return Some(self.decided(true, offset + first_path_start));
        }
        if masks.spaces != 0 {
            return Some(self.decided(false, 0));
        }
        self.follows_component_separator = masks.component_separators >> (WIDTH - 1);
        None
    }

    /// Adds the `:`s before the first `/` that can begin a path in the bytes
    /// at `within` of the vector that begins at `offset`, given its `masks`,
    /// and returns the `/`s there that can begin a path.
    #[inline]
    fn add_separators(&mut self, masks: NameContentMasks, within: u32, offset: u32) -> u32 {
        let component_separators = masks.component_separators & within;
        if Scanned::FINDS_LOCAL_NAMES {
            self.local_name_breaks |=
                (component_separators | masks.path_separators | masks.spaces) & within;
        }
        let path_starts = masks.path_separators
            & ((component_separators << 1) | self.follows_component_separator)
            & within;
        let separators = component_separators & !path_starts & path_starts.wrapping_sub(1);
        let after_first = separators & separators.wrapping_sub(1);
        // The first two `:`s in this vector, or `u32::MAX` where there are
        // fewer. A later vector's indexes are all greater than an earlier one's,
        // so `min` and `max` keep the first two overall without a branch.
        let first_here =
            (offset + separators.trailing_zeros()) | 0u32.wrapping_sub(u32::from(separators == 0));
        let second_here = (offset + after_first.trailing_zeros())
            | 0u32.wrapping_sub(u32::from(after_first == 0));
        let first_before = self.first_fqun_separator;
        self.first_fqun_separator = first_before.min(first_here);
        self.second_fqun_separator = self
            .second_fqun_separator
            .min(first_before.max(first_here))
            .min(second_here);
        self.fqun_separator_count += separators.count_ones();
        path_starts
    }

    #[inline]
    const fn decided(&self, has_path_start: bool, path_start: u32) -> DecidedName {
        DecidedName {
            has_path_start,
            path_start,
            fqun_separator_count: self.fqun_separator_count,
            first_fqun_separator: self.first_fqun_separator,
            second_fqun_separator: self.second_fqun_separator,
        }
    }

    /// Adds the first `length` bytes of the vector in which the name content
    /// ends, given its `masks`, to `bytes`, and returns what the scan found.
    #[inline]
    fn finish(
        mut self,
        mut bytes: LongNameBytes,
        masks: NameContentMasks,
        length: usize,
    ) -> Scanned {
        let offset = bytes.offset;
        let within = low_bits(length);
        let path_starts = self.add_separators(masks, within, offset);
        let first_path_start = path_starts.trailing_zeros();
        let decided = self.decided(
            first_path_start < (masks.spaces & within).trailing_zeros(),
            offset + first_path_start,
        );
        let is_local_name = Scanned::FINDS_LOCAL_NAMES & (self.local_name_breaks == 0);
        bytes.add(masks, length);
        decided.scanned(bytes, offset as usize + length, is_local_name)
    }
}

impl DecidedName {
    /// Adds the first `length` bytes of the vector in which the name content
    /// ends, given its `masks`, to `bytes`, and returns what the scan found.
    #[inline]
    fn finish<Scanned: ScannedNameContent>(
        self,
        mut bytes: LongNameBytes,
        masks: NameContentMasks,
        length: usize,
    ) -> Scanned {
        let total_length = bytes.offset as usize + length;
        bytes.add(masks, length);
        // Name content with a space or a `/` that can begin a path is not a
        // local name.
        self.scanned(bytes, total_length, false)
    }

    /// Returns what a scan of name content that is `total_length` bytes long,
    /// and whose bytes are `bytes`, found.
    #[inline]
    fn scanned<Scanned: ScannedNameContent>(
        self,
        bytes: LongNameBytes,
        total_length: usize,
        is_local_name: bool,
    ) -> Scanned {
        // A global name's path is at least one byte after its first `/`.
        let is_global_name = self.has_path_start & ((self.path_start as usize) + 1 < total_length);
        // A global name's path follows its last `:`, if it has one. The fields
        // are computed before the `Option` is, so that `None`, which is only a
        // count of 0, is no branch away from `Some`.
        let last = self.path_start.wrapping_sub(1);
        let first = self.first_fqun_separator.min(last);
        let second = self.second_fqun_separator.min(last);
        let count = self.fqun_separator_count & 0u32.wrapping_sub(u32::from(is_global_name));
        Scanned::new(
            total_length,
            total_length - bytes.continuation_bytes,
            bytes.unprintable_bytes == 0,
            is_global_name,
            NonZeroU32::new(count).map(|count| FqunSeparators {
                count,
                first,
                second,
                last,
            }),
            is_local_name,
        )
    }
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
#[must_use]
pub fn rest_of_line(source: &[u8]) -> RestOfLine {
    let (chunks, remainder) = source.as_chunks::<WIDTH>();
    let mut unprintable = 0;
    for (index, &chunk) in chunks.iter().enumerate() {
        let vector = u8x32::new(chunk);
        let line_feeds = mask(vector, LINE_FEED);
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
                mask(vector, LINE_FEED) >> shift,
                unprintable_mask(vector) >> shift,
            )
        }
        // For a source shorter than one vector, a byte loop is faster than
        // copying it into a zeroed array.
        _ => {
            let mut line_feeds = 0;
            let mut unprintable = 0;
            for (index, &byte) in remainder.iter().enumerate() {
                line_feeds |= u32::from(byte == LINE_FEED) << index;
                unprintable |= u32::from(!(b' '..=b'~').contains(&byte)) << index;
            }
            (line_feeds, unprintable)
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
fn unprintable_mask(vector: u8x32) -> u32 {
    // Subtracting wraps, so the printable bytes are exactly those that become
    // at most `~` - ` `.
    let offset = vector - u8x32::splat(b' ');
    !offset
        .min(u8x32::splat(b'~' - b' '))
        .simd_eq(offset)
        .to_bitmask()
}

/// What a scan of the start of a line, or of the rest of a line after a
/// statement, found.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum LineEnd {
    /// A line feed or the end of the source, or any number of spaces and then
    /// a comment that is printable ASCII and does not end with a space. A line
    /// feed or the end of the source follows `length` bytes.
    EndOrAsciiComment {
        length: usize,
        leading_space_count: usize,
    },
    /// Any number of spaces, then a byte other than a space, `#`, or a line
    /// feed.
    Text { leading_space_count: usize },
    /// Any number of spaces, then anything else, which needs a slower look to
    /// say what it is. A line feed or the end of the source follows `length`
    /// bytes.
    Unusual {
        leading_space_count: usize,
        length: usize,
    },
}

/// Scans the start of `source` for the end of a line.
#[inline]
#[must_use]
pub fn line_end(source: &[u8]) -> LineEnd {
    let Some(&chunk) = source.first_chunk::<WIDTH>() else {
        return short_line_end(source);
    };
    line_end_in_vector(source, u8x32::new(chunk), WIDTH)
}

// A copy into a zeroed array happens only in the last 32 bytes of the source.
#[cold]
#[inline(never)]
fn short_line_end(source: &[u8]) -> LineEnd {
    line_end_in_vector(source, zero_padded(source), source.len())
}

/// Scans the start of `source`, whose first `length` bytes, at most 32, are
/// in `vector`.
#[inline]
fn line_end_in_vector(source: &[u8], vector: u8x32, length: usize) -> LineEnd {
    let bytes = low_bits(length);
    let spaces = mask(vector, SPACE) & bytes;
    let leading_space_count = (!spaces).trailing_zeros() as usize;
    if leading_space_count == length {
        return match length {
            0 => LineEnd::EndOrAsciiComment {
                length: 0,
                leading_space_count: 0,
            },
            WIDTH => line_end_after_space_vectors(source),
            _ => LineEnd::Unusual {
                leading_space_count,
                length: leading_space_count,
            },
        };
    }
    match source[leading_space_count] {
        LINE_FEED if leading_space_count == 0 => LineEnd::EndOrAsciiComment {
            length: 0,
            leading_space_count: 0,
        },
        LINE_FEED => LineEnd::Unusual {
            leading_space_count,
            length: leading_space_count,
        },
        COMMENT_START => {
            let line_feeds = mask(vector, LINE_FEED) & bytes;
            if line_feeds == 0 && length == WIDTH {
                return long_line_end(source, leading_space_count);
            }
            let end = if line_feeds == 0 {
                length
            } else {
                line_feeds.trailing_zeros() as usize
            };
            // The `#` comes before `end`, so `end` is at least 1.
            if unprintable_mask(vector) & low_bits(end) != 0 || spaces & (1 << (end - 1)) != 0 {
                return LineEnd::Unusual {
                    leading_space_count,
                    length: end,
                };
            }
            LineEnd::EndOrAsciiComment {
                length: end,
                leading_space_count,
            }
        }
        _ => LineEnd::Text {
            leading_space_count,
        },
    }
}

/// Scans the start of `source`, whose first 32 bytes are spaces.
#[cold]
#[inline(never)]
fn line_end_after_space_vectors(source: &[u8]) -> LineEnd {
    let mut offset = WIDTH;
    while let Some(&chunk) = source[offset..].first_chunk::<WIDTH>()
        && mask(u8x32::new(chunk), SPACE) == u32::MAX
    {
        offset += WIDTH;
    }
    // The rest of `source` does not start with 32 spaces, so this does not
    // come back here.
    match line_end(&source[offset..]) {
        // Spaces before a line feed or the end of the source are trailing
        // whitespace.
        LineEnd::EndOrAsciiComment { length: 0, .. } => LineEnd::Unusual {
            leading_space_count: offset,
            length: offset,
        },
        LineEnd::EndOrAsciiComment {
            length,
            leading_space_count,
        } => LineEnd::EndOrAsciiComment {
            length: offset + length,
            leading_space_count: offset + leading_space_count,
        },
        LineEnd::Text {
            leading_space_count,
        } => LineEnd::Text {
            leading_space_count: offset + leading_space_count,
        },
        LineEnd::Unusual {
            leading_space_count,
            length,
        } => LineEnd::Unusual {
            leading_space_count: offset + leading_space_count,
            length: offset + length,
        },
    }
}

/// Scans the start of `source`, `leading_space_count` spaces and then a comment
/// that is longer than one vector with them.
#[cold]
#[inline(never)]
fn long_line_end(source: &[u8], leading_space_count: usize) -> LineEnd {
    let scanned = rest_of_line(source);
    if !scanned.is_printable_ascii || source[scanned.length - 1] == SPACE {
        return LineEnd::Unusual {
            leading_space_count,
            length: scanned.length,
        };
    }
    LineEnd::EndOrAsciiComment {
        length: scanned.length,
        leading_space_count,
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
                is_printable_ascii: true,
                is_global_name: true,
                fqun_separators: Some(FqunSeparators {
                    count: NonZeroU32::new(1).unwrap(),
                    first: 8,
                    second: 8,
                    last: 8
                }),
                is_local_name: false,
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
                is_printable_ascii: true,
                is_global_name: true,
                fqun_separators: Some(FqunSeparators {
                    count: NonZeroU32::new(2).unwrap(),
                    first: 9,
                    second: 18,
                    last: 18
                }),
                is_local_name: false,
            })
        );
    }

    #[gtest]
    fn name_content_with_too_many_component_separators() {
        expect_that!(
            name_content(b"a:b:c:d:/x>.\n"),
            eq(NameContent {
                length: 10,
                character_count: 10,
                is_printable_ascii: true,
                is_global_name: true,
                fqun_separators: Some(FqunSeparators {
                    count: NonZeroU32::new(4).unwrap(),
                    first: 1,
                    second: 3,
                    last: 7
                }),
                is_local_name: false,
            })
        );
    }

    #[gtest]
    fn name_content_with_component_separator_first() {
        expect_that!(
            name_content(b":/x>.\n"),
            eq(NameContent {
                length: 3,
                character_count: 3,
                is_printable_ascii: true,
                is_global_name: true,
                fqun_separators: Some(FqunSeparators {
                    count: NonZeroU32::new(1).unwrap(),
                    first: 0,
                    second: 0,
                    last: 0
                }),
                is_local_name: false,
            })
        );
    }

    #[gtest]
    fn name_content_with_component_separators_only_in_second_vector() {
        let source = [&[b'a'; 40][..], b":b:/c>.\n"].concat();
        expect_that!(
            name_content(&source),
            eq(NameContent {
                length: 45,
                character_count: 45,
                is_printable_ascii: true,
                is_global_name: true,
                fqun_separators: Some(FqunSeparators {
                    count: NonZeroU32::new(2).unwrap(),
                    first: 40,
                    second: 42,
                    last: 42
                }),
                is_local_name: false,
            })
        );
    }

    #[gtest]
    fn name_content_with_too_many_component_separators_across_vectors() {
        let source = [&b"a:b:"[..], &[b'c'; 30][..], b":d:/e>.\n"].concat();
        expect_that!(
            name_content(&source),
            eq(NameContent {
                length: 39,
                character_count: 39,
                is_printable_ascii: true,
                is_global_name: true,
                fqun_separators: Some(FqunSeparators {
                    count: NonZeroU32::new(4).unwrap(),
                    first: 1,
                    second: 3,
                    last: 36
                }),
                is_local_name: false,
            })
        );
    }

    #[gtest]
    fn global_name_content_with_full_fqun() {
        expect_that!(
            global_name_content(b"mv:define-lang.org:parser:/my_action>.\n"),
            eq(GlobalNameContent {
                length: 36,
                character_count: 36,
                is_printable_ascii: true,
                is_global_name: true,
                fqun_separators: Some(FqunSeparators {
                    count: NonZeroU32::new(3).unwrap(),
                    first: 2,
                    second: 18,
                    last: 25
                }),
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
                is_printable_ascii: true,
                is_global_name: true,
                fqun_separators: None,
                is_local_name: false,
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
                is_printable_ascii: true,
                is_global_name: false,
                fqun_separators: None,
                is_local_name: false,
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
                is_printable_ascii: true,
                is_global_name: false,
                fqun_separators: None,
                is_local_name: false,
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
                is_printable_ascii: true,
                is_global_name: false,
                fqun_separators: None,
                is_local_name: false,
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
                is_printable_ascii: true,
                is_global_name: true,
                fqun_separators: Some(FqunSeparators {
                    count: NonZeroU32::new(1).unwrap(),
                    first: 8,
                    second: 8,
                    last: 8
                }),
                is_local_name: false,
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
                is_printable_ascii: false,
                is_global_name: true,
                fqun_separators: Some(FqunSeparators {
                    count: NonZeroU32::new(1).unwrap(),
                    first: 5,
                    second: 5,
                    last: 5
                }),
                is_local_name: false,
            })
        );
    }

    #[gtest]
    fn name_content_with_control_character() {
        expect_that!(
            name_content(b"standard:/a\x01b>.\n"),
            eq(NameContent {
                length: 13,
                character_count: 13,
                is_printable_ascii: false,
                is_global_name: true,
                fqun_separators: Some(FqunSeparators {
                    count: NonZeroU32::new(1).unwrap(),
                    first: 8,
                    second: 8,
                    last: 8
                }),
                is_local_name: false,
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
                is_printable_ascii: true,
                is_global_name: true,
                fqun_separators: Some(FqunSeparators {
                    count: NonZeroU32::new(1).unwrap(),
                    first: 8,
                    second: 8,
                    last: 8
                }),
                is_local_name: false,
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
                is_printable_ascii: true,
                is_global_name: true,
                fqun_separators: Some(FqunSeparators {
                    count: NonZeroU32::new(1).unwrap(),
                    first: 8,
                    second: 8,
                    last: 8
                }),
                is_local_name: false,
            })
        );
    }

    #[gtest]
    fn name_content_with_component_separators_in_path() {
        expect_that!(
            name_content(b"/foo::bar>.\n"),
            eq(NameContent {
                length: 9,
                character_count: 9,
                is_printable_ascii: true,
                is_global_name: true,
                fqun_separators: None,
                is_local_name: false,
            })
        );
    }

    #[gtest]
    fn name_content_longer_than_one_vector_with_component_separator_in_path() {
        expect_that!(
            name_content(b"universe:/aaaaaaaaaaaaaaaaaaaaaaaaaaaaa:b>.\n"),
            eq(NameContent {
                length: 41,
                character_count: 41,
                is_printable_ascii: true,
                is_global_name: true,
                fqun_separators: Some(FqunSeparators {
                    count: NonZeroU32::new(1).unwrap(),
                    first: 8,
                    second: 8,
                    last: 8
                }),
                is_local_name: false,
            })
        );
    }

    #[gtest]
    fn name_content_with_component_separator_in_path_in_second_vector() {
        expect_that!(
            name_content(b"universe:/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa:b>.\n"),
            eq(NameContent {
                length: 47,
                character_count: 47,
                is_printable_ascii: true,
                is_global_name: true,
                fqun_separators: Some(FqunSeparators {
                    count: NonZeroU32::new(1).unwrap(),
                    first: 8,
                    second: 8,
                    last: 8
                }),
                is_local_name: false,
            })
        );
    }

    #[gtest]
    fn global_name_content_with_fqun() {
        expect_that!(
            global_name_content(
                b"standard:/path>.\ndefine the potential position<standard:/other>.\n"
            ),
            eq(GlobalNameContent {
                length: 14,
                character_count: 14,
                is_printable_ascii: true,
                is_global_name: true,
                fqun_separators: Some(FqunSeparators {
                    count: NonZeroU32::new(1).unwrap(),
                    first: 8,
                    second: 8,
                    last: 8
                }),
            })
        );
    }

    #[gtest]
    fn global_name_content_longer_than_one_vector() {
        expect_that!(
            global_name_content(b"universe:/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa:b>.\n"),
            eq(GlobalNameContent {
                length: 47,
                character_count: 47,
                is_printable_ascii: true,
                is_global_name: true,
                fqun_separators: Some(FqunSeparators {
                    count: NonZeroU32::new(1).unwrap(),
                    first: 8,
                    second: 8,
                    last: 8
                }),
            })
        );
    }

    #[gtest]
    fn global_name_content_of_local_name() {
        expect_that!(
            global_name_content(b"run>.\n"),
            eq(GlobalNameContent {
                length: 3,
                character_count: 3,
                is_printable_ascii: true,
                is_global_name: false,
                fqun_separators: None,
            })
        );
    }

    #[gtest]
    fn name_content_of_local_name() {
        expect_that!(
            name_content(b"run>.\ndefine the potential position<standard:/other>.\n"),
            eq(NameContent {
                length: 3,
                character_count: 3,
                is_printable_ascii: true,
                is_global_name: false,
                fqun_separators: None,
                is_local_name: true,
            })
        );
    }

    #[gtest]
    fn name_content_with_component_separator_in_second_vector_is_not_local() {
        expect_that!(
            name_content(b"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa:b>.\n"),
            eq(NameContent {
                length: 36,
                character_count: 36,
                is_printable_ascii: true,
                is_global_name: false,
                fqun_separators: None,
                is_local_name: false,
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
                is_printable_ascii: true,
                is_global_name: true,
                fqun_separators: Some(FqunSeparators { count: NonZeroU32::new(3).unwrap(), first: 10, second: 28, last: 37 }),
                is_local_name: false,
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
                is_printable_ascii: true,
                is_global_name: true,
                fqun_separators: Some(FqunSeparators {
                    count: NonZeroU32::new(1).unwrap(),
                    first: 30,
                    second: 30,
                    last: 30
                }),
                is_local_name: false,
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
                is_printable_ascii: true,
                is_global_name: false,
                fqun_separators: None,
                is_local_name: false,
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
                is_printable_ascii: true,
                is_global_name: false,
                fqun_separators: None,
                is_local_name: true,
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
                is_printable_ascii: true,
                is_global_name: false,
                fqun_separators: None,
                is_local_name: false,
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
                is_printable_ascii: true,
                is_global_name: false,
                fqun_separators: None,
                is_local_name: false,
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
                is_printable_ascii: true,
                is_global_name: true,
                fqun_separators: Some(FqunSeparators {
                    count: NonZeroU32::new(1).unwrap(),
                    first: 31,
                    second: 31,
                    last: 31
                }),
                is_local_name: false,
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
                is_printable_ascii: true,
                is_global_name: false,
                fqun_separators: None,
                is_local_name: false,
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
                is_printable_ascii: false,
                is_global_name: true,
                fqun_separators: Some(FqunSeparators {
                    count: NonZeroU32::new(1).unwrap(),
                    first: 34,
                    second: 34,
                    last: 34
                }),
                is_local_name: false,
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
                is_printable_ascii: true,
                is_global_name: true,
                fqun_separators: Some(FqunSeparators {
                    count: NonZeroU32::new(1).unwrap(),
                    first: 60,
                    second: 60,
                    last: 60
                }),
                is_local_name: false,
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
                is_printable_ascii: true,
                is_global_name: true,
                fqun_separators: Some(FqunSeparators {
                    count: NonZeroU32::new(1).unwrap(),
                    first: 60,
                    second: 60,
                    last: 60
                }),
                is_local_name: false,
            })
        );
    }

    #[gtest]
    fn name_content_with_path_in_first_of_three_vectors() {
        let source = [&b"standard:/"[..], &[b'a'; 60][..], b">.\n"].concat();
        expect_that!(
            name_content(&source),
            eq(NameContent {
                length: 70,
                character_count: 70,
                is_printable_ascii: true,
                is_global_name: true,
                fqun_separators: Some(FqunSeparators {
                    count: NonZeroU32::new(1).unwrap(),
                    first: 8,
                    second: 8,
                    last: 8
                }),
                is_local_name: false,
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
                is_printable_ascii: true,
                is_global_name: true,
                fqun_separators: Some(FqunSeparators {
                    count: NonZeroU32::new(1).unwrap(),
                    first: 65,
                    second: 65,
                    last: 65
                }),
                is_local_name: false,
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
                is_printable_ascii: true,
                is_global_name: true,
                fqun_separators: Some(FqunSeparators {
                    count: NonZeroU32::new(1).unwrap(),
                    first: 62,
                    second: 62,
                    last: 62
                }),
                is_local_name: false,
            })
        );
    }

    #[gtest]
    fn line_end_at_line_feed() {
        expect_that!(
            line_end(b"\n# a comment\n"),
            eq(LineEnd::EndOrAsciiComment {
                length: 0,
                leading_space_count: 0
            })
        );
    }

    #[gtest]
    fn line_end_at_end_of_source() {
        expect_that!(
            line_end(b""),
            eq(LineEnd::EndOrAsciiComment {
                length: 0,
                leading_space_count: 0
            })
        );
    }

    #[gtest]
    fn line_end_at_comment() {
        expect_that!(
            line_end(b"# a comment\ndefine the potential position<standard:/path>.\n"),
            eq(LineEnd::EndOrAsciiComment {
                length: 11,
                leading_space_count: 0
            })
        );
    }

    #[gtest]
    fn line_end_at_comment_after_spaces() {
        expect_that!(
            line_end(b"    # a comment\ndefine the potential position<standard:/path>.\n"),
            eq(LineEnd::EndOrAsciiComment {
                length: 15,
                leading_space_count: 4
            })
        );
    }

    #[gtest]
    fn line_end_at_comment_at_end_of_source() {
        expect_that!(
            line_end(b" #"),
            eq(LineEnd::EndOrAsciiComment {
                length: 2,
                leading_space_count: 1
            })
        );
    }

    #[gtest]
    fn line_end_at_comment_longer_than_one_vector() {
        expect_that!(
            line_end(b"  # A comment that is longer than one vector of bytes.\nx\n"),
            eq(LineEnd::EndOrAsciiComment {
                length: 54,
                leading_space_count: 2
            })
        );
    }

    #[gtest]
    fn line_end_at_text() {
        expect_that!(
            line_end(b"define the potential position<standard:/path>.\n"),
            eq(LineEnd::Text {
                leading_space_count: 0
            })
        );
    }

    #[gtest]
    fn line_end_at_text_after_spaces() {
        expect_that!(
            line_end(b"    it has the position</child>.\n"),
            eq(LineEnd::Text {
                leading_space_count: 4
            })
        );
    }

    #[gtest]
    fn line_end_at_text_after_spaces_at_end_of_source() {
        expect_that!(
            line_end(b"  x"),
            eq(LineEnd::Text {
                leading_space_count: 2
            })
        );
    }

    #[gtest]
    fn line_end_at_spaces_before_line_feed() {
        expect_that!(
            line_end(b"  \n# a comment\n"),
            eq(LineEnd::Unusual {
                leading_space_count: 2,
                length: 2
            })
        );
    }

    #[gtest]
    fn line_end_at_spaces_at_end_of_source() {
        expect_that!(
            line_end(b"  "),
            eq(LineEnd::Unusual {
                leading_space_count: 2,
                length: 2
            })
        );
    }

    #[gtest]
    fn line_end_at_comment_ending_with_space() {
        expect_that!(
            line_end(b"# a comment \ndefine the potential position<standard:/path>.\n"),
            eq(LineEnd::Unusual {
                leading_space_count: 0,
                length: 12
            })
        );
    }

    #[gtest]
    fn line_end_at_comment_ending_with_space_at_end_of_source() {
        expect_that!(
            line_end(b"# "),
            eq(LineEnd::Unusual {
                leading_space_count: 0,
                length: 2
            })
        );
    }

    #[gtest]
    fn line_end_at_comment_with_control_character() {
        expect_that!(
            line_end(b"# a\tcomment\n"),
            eq(LineEnd::Unusual {
                leading_space_count: 0,
                length: 11
            })
        );
    }

    #[gtest]
    fn line_end_at_non_ascii_comment() {
        expect_that!(
            line_end("# café\n".as_bytes()),
            eq(LineEnd::Unusual {
                leading_space_count: 0,
                length: 7
            })
        );
    }

    #[gtest]
    fn line_end_at_comment_longer_than_one_vector_ending_with_space() {
        expect_that!(
            line_end(b"# A comment that is longer than one vector of bytes. \nx\n"),
            eq(LineEnd::Unusual {
                leading_space_count: 0,
                length: 53
            })
        );
    }

    #[gtest]
    fn line_end_at_comment_longer_than_one_vector_with_non_ascii_character() {
        expect_that!(
            line_end("# A comment that is longer than one vector, ending in é\n".as_bytes()),
            eq(LineEnd::Unusual {
                leading_space_count: 0,
                length: 56
            })
        );
    }

    #[gtest]
    fn line_end_at_comment_longer_than_one_vector_after_spaces_ending_with_space() {
        expect_that!(
            line_end(b"   # A comment that is longer than one vector of bytes. \nx\n"),
            eq(LineEnd::Unusual {
                leading_space_count: 3,
                length: 56
            })
        );
    }

    #[gtest]
    fn line_end_at_text_after_one_vector_of_spaces() {
        let source = [&[b' '; 32][..], b"x\n"].concat();
        expect_that!(
            line_end(&source),
            eq(LineEnd::Text {
                leading_space_count: 32
            })
        );
    }

    #[gtest]
    fn line_end_at_text_after_more_than_two_vectors_of_spaces() {
        let source = [&[b' '; 70][..], b"x\n"].concat();
        expect_that!(
            line_end(&source),
            eq(LineEnd::Text {
                leading_space_count: 70
            })
        );
    }

    #[gtest]
    fn line_end_at_comment_after_more_than_one_vector_of_spaces() {
        let source = [&[b' '; 40][..], b"# a comment\nx\n"].concat();
        expect_that!(
            line_end(&source),
            eq(LineEnd::EndOrAsciiComment {
                length: 51,
                leading_space_count: 40
            })
        );
    }

    #[gtest]
    fn line_end_at_comment_after_exactly_two_vectors_of_spaces() {
        let source = [
            &[b' '; 64][..],
            b"# a comment that is longer than one vector of bytes\n",
        ]
        .concat();
        expect_that!(
            line_end(&source),
            eq(LineEnd::EndOrAsciiComment {
                length: 115,
                leading_space_count: 64
            })
        );
    }

    #[gtest]
    fn line_end_at_two_vectors_of_spaces_before_line_feed() {
        let source = [&[b' '; 64][..], b"\nx\n"].concat();
        expect_that!(
            line_end(&source),
            eq(LineEnd::Unusual {
                leading_space_count: 64,
                length: 64
            })
        );
    }

    #[gtest]
    fn line_end_at_one_vector_of_spaces_at_end_of_source() {
        expect_that!(
            line_end(&[b' '; 32]),
            eq(LineEnd::Unusual {
                leading_space_count: 32,
                length: 32
            })
        );
    }

    #[gtest]
    fn line_end_at_more_than_one_vector_of_spaces_at_end_of_source() {
        expect_that!(
            line_end(&[b' '; 40]),
            eq(LineEnd::Unusual {
                leading_space_count: 40,
                length: 40
            })
        );
    }

    #[gtest]
    fn line_end_at_more_than_one_vector_of_spaces_before_comment_ending_with_space() {
        let source = [&[b' '; 40][..], b"# a comment \n"].concat();
        expect_that!(
            line_end(&source),
            eq(LineEnd::Unusual {
                leading_space_count: 40,
                length: 52
            })
        );
    }

    #[gtest]
    fn rest_of_line_ending_at_line_feed() {
        expect_that!(
            rest_of_line(b"# a comment\ndefine the potential position<standard:/path>.\n"),
            eq(RestOfLine {
                length: 11,
                is_printable_ascii: true,
            })
        );
    }

    #[gtest]
    fn rest_of_line_at_end_of_source() {
        expect_that!(
            rest_of_line(b"# a comment"),
            eq(RestOfLine {
                length: 11,
                is_printable_ascii: true,
            })
        );
    }

    #[gtest]
    fn rest_of_line_with_non_ascii_character() {
        expect_that!(
            rest_of_line("# café\n".as_bytes()),
            eq(RestOfLine {
                length: 7,
                is_printable_ascii: false,
            })
        );
    }

    #[gtest]
    fn rest_of_line_longer_than_one_vector() {
        expect_that!(
            rest_of_line(b"# A comment that is longer than one vector of thirty-two bytes.\nx\n"),
            eq(RestOfLine {
                length: 63,
                is_printable_ascii: true,
            })
        );
    }

    #[gtest]
    fn rest_of_line_longer_than_one_vector_at_end_of_source() {
        expect_that!(
            rest_of_line("# A comment that is longer than one vector, ending in é".as_bytes()),
            eq(RestOfLine {
                length: 56,
                is_printable_ascii: false,
            })
        );
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
    fn rest_of_line_with_non_ascii_character_after_line_feed() {
        expect_that!(
            rest_of_line("# ascii\né\n".as_bytes()),
            eq(RestOfLine {
                length: 7,
                is_printable_ascii: true,
            })
        );
    }

    #[gtest]
    fn rest_of_line_with_control_character() {
        expect_that!(
            rest_of_line(b"# a\tcomment\n"),
            eq(RestOfLine {
                length: 11,
                is_printable_ascii: false,
            })
        );
    }

    #[gtest]
    fn rest_of_line_with_delete_character_longer_than_one_vector() {
        expect_that!(
            rest_of_line(b"# A comment longer than one vector of bytes, ending in \x7f\n"),
            eq(RestOfLine {
                length: 56,
                is_printable_ascii: false,
            })
        );
    }

    #[gtest]
    fn rest_of_line_with_delete_character_in_first_vector() {
        expect_that!(
            rest_of_line(b"# \x7f comment that is longer than one vector of bytes\n"),
            eq(RestOfLine {
                length: 51,
                is_printable_ascii: false,
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
