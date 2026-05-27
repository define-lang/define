# Define Language Proposal 35: Parsing Define Files

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** January 30, 2026
- **Date Finalized:**

## Problems

Source code files are text, and there are numerous basic problems involved in
simply parsing text.

### Byte Format

Most languages have settled on UTF-8 as the format for source code, but many
languages did not standardize on this or went some other direction.

### Unicode Byte Order Mark

When you use UTF-8, there is an optional "byte order mark" that can appear as
the first three bytes at the start of files. Do we allow it? Do we ignore it? Do
we respect it?

### Invalid Unicode Sequences

There are sequences of bytes that are not valid Unicode characters. Do we
replace them with a "placeholder character?" Do we simply ignore them? Do we ban
them?

### Case-sensitivity

Is `DEFINE` the same as `define` in syntax? Are any parts of the source code
case-insensitive?

### Newlines

Different operating systems have long used different byte sequences to end
lines. (Either CR + LF or just LF.) Do we allow both? Do we require just one?
What happens when we see one we don't allow?

### Trailing Newlines

Do we require that a source code file end with a newline or not?

### Syntax vs Comments

While you can be very restrictive with syntax, comments also appear in source
code, and you can't restrict as much what appears in them.

### Spaces

When syntax specifies a space between characters, does that also mean we can put
a newline there, or multiple spaces? Also, what about spaces at the end of
lines, are they meaningful?

## Solution

### Guiding Standard

It is the intention of Define to conform to
[Unicode Technical Standard #55 (Unicode Source Code Handling)](https://www.unicode.org/reports/tr55/).
We may choose to be _more_ restrictive than that standard. However, when we are
_less_ restrictive than that standard, that should be considered to be a bug in
the specification and/or Define tooling.

### General Unicode Parsing Rules

- **Byte Format**: Define files are in UTF-8. Define strives to use the latest
  version of the Unicode database and standards, but will include in its
  documentation what current versions are being used.
- **BOM**: Byte-order marks are banned. The compiler will throw an error if it
  encounters one when reading a source code file.
- **Invalid Sequences**: Define forbids invalid Unicode sequences in files. All
  Define tooling must throw an error if it encounters such sequences.

### Newlines

The only valid line terminator ("newline") that Define recognizes is `U+000A`
(line feed). When syntax is defined as appearing on multiple lines, it means
those lines end with this newline.

Define source files must have a newline as their last character.

### Trailing Spaces

Trailing spaces in Define files are forbidden. In other words, there may not be
a space before a newline. However, multiple newlines in a row may be written in
Define files.

### Allowed Syntax Characters

Define syntax may only be written using lowercase ASCII characters and symbols.
To be clear, this means that only the following Unicode codepoints are allowed
in any syntax that has semantics:

- `U+0020` through `U+0040`
- `U+005B` through `U+007E`

There are two exceptions:

- **Names** have their own rules defined in a later proposal that override these
  rules.
- **Comments** allow all characters except those we restrict elsewhere in this
  proposal. (Note that this means UTS #55 is still the guiding standard for
  comments.)

### Spaces and Newlines in Syntax

When the Define Language Specification or a Define Language Proposal specifies
spaces in syntax, the parser requires exactly one space (`U+0020`) in that
position.

Unless otherwise specified in syntax, a newline must always immediately follow a
statement terminator, a `{`, or a `}` in syntax.

### Invisible Characters

Any invisible characters are forbidden in Define source files other than space,
line feed, and characters necessary for correctly rendering visible Unicode text
(provided the use of those characters conforms to UTS #55, especially for BiDi
handling).

For example, some languages need Unicode's Zero-Width Joiners in order to render
correctly. For example, the "Family" emoji (👨‍👩‍👦) is made of `Man` + `ZWJ` +
`Woman` + `ZWJ` + `Boy`, and is allowed. However, a Zero-Width Joiner in a
location that is not necessary for rendering visible text would be banned.

[UAX #29](https://www.unicode.org/reports/tr29/) is the controlling standard for
whether characters are necessary for rendering visible text.

Note that this explicitly and intentionally bans tab characters and carriage
returns. It also intentionally bans all forms of space characters other than
`U+0020`.

## A Real Program

### Valid Program

```
define the potential position<mv:example.com:example:/bank> {
    it may only contain particles where {
        it has the action</do_transfers>.
    }
}
```

### Invalid Programs

- Uppercase letters in syntax (`Define` instead of `define`):

```
Define the potential position<mv:example.com:example:/bank> {
    it may only contain particles where {
        it has the action</do_transfers>.
    }
}
```

- Two spaces where exactly one is required:

```
define  the potential position<mv:example.com:example:/bank> {
    it may only contain particles where {
        it has the action</do_transfers>.
    }
}
```

It's hard to show most other invalid programs, because they involve invisible
characters.

## Why This is the Right Solution

### UTF-8

UTF-8 is pretty much the obvious choice for Unicode parsing. It's the most
widely-implemented standard. It's concise for ASCII characters, and most of our
source code is ASCII characters. It allows for non-ASCII characters in comments
(and in names when necessary). It will also be useful in literal strings when we
have those in a future proposal.

### Forbidding BOMs

There are a few good reasons to forbid BOMs.

1. If Define is ever used for scripting, a BOM often kills the ability of
   Unix-based systems to find the "shebang" (`#!`) at the start of files that
   says what binary to use for the script.
2. When you concatenate files together (which Define intends to support) you end
   up putting a BOM in the middle of a file, which then parses like an invalid
   Unicode character.
3. It's never actually necessary for parsing a file.

### Forbidding Invalid Sequences

There's no reason to try to render or parse invalid Unicode. You just open
yourself up for weird parsing bugs and probably security issues, too.

### Restricting Newlines to LF

I have been tripped up many times in my programming career by files that have
different newlines in them than I was expecting. You're trying to parse some
file and it suddenly doesn't work on some machines, and you can't figure out
why, only to discover after hours of debugging that it's because the file is
using CRLF to end lines.

This is the worst for literal strings, where all of the sudden you change what
your program is outputting based on what some text editor decides to stick in
your files.

### Trailing Newlines at the End of Files

The reason we enforce trailing newlines is that it simplifies diffs. Without a
trailing newline in a file, two things happen:

1. You often see diffs that simply add a trailing newline or remove a trailing
   newline, causing merge conflicts for no good reason.
2. When you add new code at the end of the file, if there was no trailing
   newline, the diff looks like you modified the last line, when really you
   didn't.

### Banning Trailing Spaces

I expect this one to sometimes be annoying, but allowing trailing spaces in
source code files leads to several issues:

1. It can cause confusing parsing bugs when you're trying to write some script
   on your own to parse the file (not using the compiler's parser). You expect
   the newline to be right after the statement terminator, because that's how
   source code looks visually to you, the programmer, but it's not actually that
   way on the disk.
2. It leads to diffs that are meaningless, where one programmer has just added
   or removed trailing spaces on some lines.
3. It leads to unnecessary merge conflicts.
4. Once you have literal strings, if you allow those strings to contain literal
   newlines, you can be outputting different bytes than you think you are.

It is very easy to have editors or other tools automatically strip all trailing
spaces.

### Lowercase ASCII for All Syntax

This both simplifies parsing and speeds up typing the language. It also sets a
standard and removes a decision that future language designers have to make.

### Requiring Exact Spacing and Newlines

When you're trying to grep or search through code files yourself, nothing is
more frustrating than discovering that your search didn't work because sometimes
a programmer wrote more spaces or used different line breaks than you were
expecting.

The only reason to allow this to be different is to allow long lines to break
over multiple lines, for readability. We may in the future define explicit
breakpoints where this is allowed, but for now, most monitors are large and so
line length is not a huge problem on modern computers.

There is no good reason to allow multiple spaces where the syntax expects one.

When this is annoying for the programmer, it's pretty easy to automatically fix
their source code.

### Banning Tabs

There's no reason to allow tabs in Define files.

In other languages, what often ends up happening is that programmers indent some
lines with tabs and others with spaces, and they can't tell they did that
because in their editor, the tab they used on one line is the same width as the
number of spaces they used on another line. But then another programmer opens up
the file with different settings in their editor, and the indentation is all
over the place.

It also creates frustrating parsing problems when you are expecting all
indentation to be spaces only to suddenly remember that you have to also parse
out tabs.

### Banning Invisible Characters

Not only do I want Define source code files to have one canonical
representation, and I really don't want them to change on the disk (or worse,
change their behavior) because of something invisible, there are real security
concerns here. [Trojan Source](https://en.wikipedia.org/wiki/Trojan_Source) is
one example, and I would not be surprised to discover later that there are other
reasons.

## Forward Compatibility

We have been very strict here, which should help us ensure that Define files
stay easy to parse in the future. It's much easier to start this way than to
deal with all the migration challenges that other languages have gone through to
deal with things that they probably never should have allowed in the first
place.

The one concern I have is that the algorithm for detecting invisible characters
could be computationally expensive and complex, so that's one area where we
might start off with a less-strict implementation and then break a small number
of programs in the future when we become more strict.

## Refactoring Existing Systems

There are no existing systems where we would have to think about how to migrate
them to this proposal.
