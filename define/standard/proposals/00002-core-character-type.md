# Define Standard Library Proposal 2: Core Character Type

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** October 12, 2026
- **Date Finalized:**

## Problems

One of the most complex things that a programming language has to deal with is
the digital representations of human-written characters. In a simple encoding
like ASCII, this is very straightforward. But when you get into the full set of
written human language available on Earth, then Unicode starts to provide you
with a huge number of options for encodings, algorithms, etc.

To keep things simple, we are not going to start off by defining a "string," but
instead just by defining what Define thinks of as a "character." For this there
are numerous problems.

### 1: Many Different Encodings

Unicode has many different encodings. UTF-8 has become the dominant standard,
but UTF-16 and UTF-32 also exist.

There also used to be UCS-2, which evolved into UTF-16 in 1996. However, many
systems existed before 1996 and have strange behaviors where they either produce
or accept invalid UTF-16 for historical reasons. (Fun fact: technically the SMS
standard is still UCS-2, although most systems interpret it as UTF-16 so it can
carry emojis.) There's also UCS-4, which is similar to (and superseded by)
UTF-32.

There are even more weird situations. For example, MySQL's `utf8` is actually
`utf8mb3`, meaning at most 3 bytes per character.

### 2: Scalars, Surrogates, and Graphemes

This problem is understandable by reading the following definitions:

**Scalar**: Any Unicode code point except the surrogates. In numbers, that's
`U+0000–U+D7FF` plus `U+E000–U+10FFFF`.

**Surrogates**: The range `U+D800–U+DFFF` is reserved for a hack in UTF-16.
UTF-16 uses 16-bit units, which can't hold anything above `U+FFFF`. To represent
those higher code points, it writes two units from the surrogate range (a
"surrogate pair"), and together they encode one code point. So 😀 (`U+1F600`)
becomes the two surrogates `D83D DE00` in UTF-16. The surrogate numbers never
stand for characters themselves. They exist only as halves of a pair.

**Grapheme**: The human concept of a single readable character. This is actually
a concept from linguistics, not Unicode.

**Grapheme Cluster**: A sequence of scalars that make up a grapheme. (There are
a few exceptions, where one logical character is actually _multiple_ grapheme
clusters, but most human-visible characters are a single one.) While most
graphemes are represented by a single scalar, some are represented by many, and
the number of scalars it takes to represent a grapheme can vary widely. A family
emoji is several scalars joined with "zero-width joiners," special Unicode
scalars that help make complex grapheme clusters. Some graphemes can even be
composed of different sequences of scalars and yet be the same character,
visually, to a human. For example, `é` can be written as one scalar (`U+00E9`)
or two (`e` + `U+0301`, a combining accent) but those will both render as the
exact same character.

As a result of the above definitions, graphemes aren't a singular piece of data
in Unicode. Instead, they are the _result of an algorithm_.

One of the more complex decisions a programming language has to make is: when we
say "character" in this language, do we mean a Unicode scalar, or a Unicode
grapheme cluster? Different languages make this decision differently. Rust's
`char` is a scalar, but Swift's `Character` is a grapheme cluster.

If you choose grapheme clusters as your base type, the compiler may have a
difficult time emitting optimal code, because of how complex they are, and
because even determining what _is_ a grapheme requires a complex algorithm.

Scalars alone don't let you slice strings in the way that humans logically want
to do so (you can cut off a multi-scalar grapheme in the middle, for example).

Regardless of whether you choose scalars or graphemes, _comparing_ strings in
the way that a human would compare them still requires Unicode normalization
(UAX #15). However, with scalars it's a bit more logically apparent to the
programmer that you just have a bunch of code points. Saying that your
characters "are graphemes" can make programmers believe they should do canonical
comparisons in the way that normalized Unicode would. (In fact, in Swift, the
language designers had to choose a fully-canonicalizing algorithm for the `==`
operator because of this.)

Every real encoding and interchange format for characters is defined via scalars
or bytes, not graphemes.

### 3: Variable Width Encodings

A scalar is never more than 21 bits to actually represent by itself. ASCII fits
in 7 bits, Latin-1 in 8 bits, the Unicode Basic Multilingual Plane in 16 bits,
and the full set of Unicode in 21 (a limit which has not changed since 2003
despite a significant increase in the total number of graphemes since that
time). So actually, that theoretically fits in 3 bytes, but doesn't always need
them.

Even then, "3 bytes" is a size that basically no computing hardware cares about.
It is smaller for _storage_ than 4 bytes (32 bits) but usually the minimal
compute unit you're going to get there is 32 bits, and sometimes even 64
depending on what operation you're trying to do. All that said, 21 bits can be a
relevant size for packing characters into SIMD operations, because you can pack
three sets of 21 bits into a 64-bit lane.

UTF-8 writes characters in a variable number of bytes depending on which Unicode
code point it's representing. So UTF-8 characters are usually only 1 byte
(because most UTF-8 in the world is just ASCII), but they _could_ be up to 4
bytes for a single scalar.

### 4: Operations Can Return Sequences

One of the weirder aspects of Unicode is that certain operations that you might
expect to return just one scalar can actually return more than one. One of the
simplest examples is uppercasing a character: `ß` becomes `SS` when upper-cased.

### 5: Encoding and Decoding

If you do have a sequence of UTF-8 bytes, the algorithm to decode them into
Unicode scalars is relatively straightforward. The first byte of each scalar
says how many bytes follow, so you just do a single forward pass decode. The
same in reverse---you always know how many bytes any given scalar will take and
how to encode it without knowing anything else about the sequence of characters
you're encoding.

There are a few caveats, though, around _validating_ bytes as being UTF-8:

- **Overlong encodings.** Using more bytes than necessary, such as `C0 AF` for
  `/`. These must be rejected. Accepting them caused real security holes, most
  famously directory traversal in IIS, where `..%c0%af` got past path checks.
- **Surrogates**. `ED A0 80` through `ED BF BF` would decode to `U+D800–U+DFFF`,
  which aren't scalar values.
- **Values above U+10FFFF**. `F4 90` and up, and leading bytes `F5–FF`.
- **Broken sequences**. A truncated sequence, or a continuation byte where a
  leading byte should be.

There is a single-pass algorithm that both decodes and validates as it goes, but
that work still has to be done.

However, after you've done that, you know that you have valid UTF-8. You don't
have to keep wondering or re-checking throughout a program if the input bytes
are truly UTF-8.

## Solution

Define chooses to be explicit. We do not have a type called "character" and
instead we start with `value</text/unicode/scalar>` as our simplest
character-like type. This can then have multiple different encodings, such as
`encoding</text/unicode/scalar/utf8>`, which will be the default and most common
encoding when dealing with input/output strings. But it can also be encoded into
some `/binary` encoding directly, or represented in the backend by an unsigned
32-bit integer, as necessary and most appropriate for optimization.

Define does not presently intend to make any promises about exactly how scalars
are encoded, because that would limit our optimization options in the future.
(Some operations are faster with UTF-8, others with UTF-32.)

### Graphemes

In the future we may have a "grapheme cluster" concept, but it will be
represented as a sequence of scalars, not as a single coherent value, most
likely. Or if it is represented as a single coherent value, it will always be
possible to interact with it as though it were a sequence of scalars.

### Operations that Return a Sequence

Any operation that _could_ return more than one scalar must be specified such
that it returns a sequence of scalars (Define syntax that will exist in the
future).

### Validation

Define programs accepting any bytes that could be invalid UTF-8 must validate
them at that boundary, and the language should provide facilities to do so. Once
data claims to be `encoding</text/unicode/utf8>` then all parts of the program
can assume it is valid. The same would be true of any other input Unicode
encoding that comes from outside the program.

## A Real Program

### Value and Literal

```define
define the potential value<standard:/text/unicode/scalar>.

define the potential literal<standard:/text> {
    it has the encoding</text/unicode/utf8>.
}
```

The literal parser rejects any literal content that is not exactly one scalar.
For example, `literal<standard:/text>"é"` is an error when the `é` is written as
`e` followed by `U+0301`.

### Operations

```define
define the operation<standard:/text/unicode/scalar/less_than> {
    define the view<a> {
        it is read.
        it may only contain particles where {
            it has the value</text/unicode/scalar>.
        }
    }
    define the view<b> {
        it is read.
        it may only contain particles where {
            it has the value</text/unicode/scalar>.
        }
    }
    define the view<result> {
        it is written.
        it may only contain particles where {
            it has the value</boolean>.
        }
    }

    it does {
        execute the encoding operation.
    }
}
```

`standard:/text/unicode/scalar/equal` has the same views. `less_than` compares
scalars by their position in Unicode, not by how any human language sorts its
characters.

```define
define the operation<standard:/text/unicode/scalar/lowercase_simple> {
    define the view<value> {
        it is read.
        it is written.
        it may only contain particles where {
            it has the value</text/unicode/scalar>.
        }
    }

    it does {
        execute the encoding operation.
    }
}
```

`standard:/text/unicode/scalar/uppercase_simple` has the same views.

These use Unicode's _simple_ case mappings, which always map one scalar to
exactly one scalar. Scalars whose full case mapping produces a sequence are left
unchanged, so `uppercase_simple` leaves `ß` as `ß`. The full case mappings, like
`ß` to `SS`, will be separate operations once Define has sequences.

### Menu Quit Key

A terminal menu reads one key press at a time. Pressing `q` quits, whether or
not Caps Lock is on.

In this program, `/menu/key` has the value `standard:/text/unicode/scalar` and
`/menu/quit_requested` has the value `standard:/boolean`.

```define
define the potential action<define-lang.org:menu:/menu/read_key> {
    it also assigns the position</menu/key>.
    it also assigns the position</menu/quit_requested>.

    define the position<run>.

    it happens when {
        the position<run> has a particle.
    } and it does {
        define the position<lowercase_key> {
            it may only contain particles where {
                it has the value<standard:/text/unicode/scalar>.
            }
        }
        create a particle in position<lowercase_key>.
        set the value of position<lowercase_key> from position</menu/key>.
        execute the operation<standard:/text/unicode/scalar/lowercase_simple> {
            with view<value> looking at position<lowercase_key>.
        }

        execute the operation<standard:/text/unicode/scalar/equal> {
            with view<a> looking at position<lowercase_key>.
            with view<b> looking at literal<standard:/text>"q".
            with view<result> looking at position</menu/quit_requested>.
        }

        destroy the particle in position<run>.
    }
}
```

## Why This is the Right Solution

So, if I was making a programming language purely for humans, forcing them to
reason about Unicode scalar behavior would be absolutely obnoxious. With coding
agents, though, they understand the Unicode specification pretty deeply and can
understand how and when to specify a scalar, and how to use them.

What eventually convinced me here is that a grapheme just can't be reasoned
about as a point of data---it's subject to an algorithm and can only be
interpreted in the context of all the other scalars around it. It also could
grow without bound. Scalars are fully interpretable by themselves, in a void,
and have a fixed maximum size. That said, once you have an _encoding_ for a
scalar (like UTF-8) you do also need some algorithm to reason about it, but at
least the algorithm is a straightforward, single-pass decode (even validation
can be done in that pass).

Another question here is why start with characters instead of with strings? The
reasoning is simply that the character is the atomic logical unit from which a
string is built. Theoretically we could just define a string as a sequence of
characters, and let the compiler determine the most optimal representation for
it. However, many languages do have different string behavior compared to their
individual character behavior (for example, 32-bit integer storage for
characters but UTF-8 representation for strings). My belief is that Define will
simply be able to determine the correct storage format for these things by
itself and that we won't have to specify it up front and thus may not need
separate data types.

## Forward Compatibility

Defining a Unicode scalar as being...a Unicode scalar provides us with a
standard that has not changed in a very long time, and appears to have no reason
to change in the future. While grapheme cluster behavior could vary widely as
time goes on, scalar behavior and UTF-8 seems to have settled for a very long
time. At the very least, by being super-explicit about exactly what we are
supporting, we won't break programs in the future if some day we want to support
some other character type.

Some scalar behavior can change over time, like uppercasing behavior. However,
that's something that can be documented as part of operations. The general facts
of scalars as an object should remain stable.

## Refactoring Existing Systems

No Define systems exist in the wild today that must be refactored. However,
other languages do exist. One of the problems with converting those languages
into Define will be that they have all specified different behavior for their
strings and character classes, sometimes even somewhat implicitly (or at least,
most programmers aren't aware of the decisions that the language designers have
made, there). At the very least, by explicitly saying "this is a Unicode scalar"
we know _how_ to translate behavior from the other language---it just might be
awkward when all we can know about the other language is "a grapheme might be
here" and we suddenly have to represent that as a sequence of scalars even when
it's probably usually just one byte.
