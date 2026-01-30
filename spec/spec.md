<!--
Instructions for humans and AI agents modifying this file:

This is a concise description of exactly what the compiler needs to do in
order to correctly implement Define's syntax and semantics. It is a specification
for a programming language called Define.

Nothing may be added to this spec unless there is first a Define Language Proposal
for that aspect of the language.

This file does not contain justifications or reasons for why decisions were made.
Instead, sections link to the relevant Define Language Proposals, like this:

## Naming

Proposals:
- [DLP 1: Types of Names](../proposals/00001-types-of-names.md)
- [DLP 2: Universes](../proposals/00002-universes.md)
- [DLP 3: Authorities](../proposals/00003-authorities.md)

Then after that the section contains concise wording, EBNF specifications, and
whatever else is needed to convey the precise details the compiler needs to know.

If a parent header lists a Define Language Proposal, the subheaders do not also
need to list that proposal. However, some DLPs will only be relevant to a subheader,
and so would be listed there.

This comment may not be modified by AI agents.
-->

# The Define Language Specification

## Introduction

This specification defines the syntax and semantics needed to compile Define
programs.

Every aspect of this specification is covered by a
[Define Language Proposal](../proposals/). Sections of this doc link to those
proposals, which contain the rationale behind Define's language decisions. This
specification contains only the specifics required for the compiler to correctly
implement Define.

The concepts behind Define are described in
[The Conceptual Basis of Define](concepts.md). It is expected that the reader
has at least a general understanding of the concepts described there.

At a high level, the language's design is guided also by our
[Principles](principles.md) and [Requirements](requirements.md).

## A Note About Undefined Behavior

Define is intended to be a very strict language. Any syntax or semantics not
specified in this spec is an error.

Define has no "undefined behavior." If the compiler encounters a situation not
described in this spec, it will provide an error and refuse to compile the
program.

In the case that there is a bug in the compiler and it does not behave according
to the spec, future versions of Define may fix that bug even if it causes
existing programs to fail to compile (that is, even if it breaks backward
compatibility).

## Parsing Define Source Code

Proposals:

- [DLP 35: Parsing Define Files](../proposals/00035-parsing-define-files.md)

Define conforms to
[Unicode Technical Standard #55 (Unicode Source Code Handling)](https://www.unicode.org/reports/tr55/).
When Define is less restrictive than UTS #55, that is a bug.

### Encoding

- Define source code is written in UTF-8.
- Define uses Unicode 17.0.0.
- Byte-order marks are forbidden.
- Invalid Unicode sequences are forbidden.

### Newlines

- The only valid line terminator is `U+000A` (line feed).
- A source file must end with a newline.
- There may not be a space (`U+0020`) immediately before a newline.
- Unless otherwise specified, a newline must immediately follow a statement
  terminator, `{`, or `}`.

### Invisible Characters

The only invisible characters allowed in Define source code files are:

- Space (`U+0020`)
- Line feed (`U+000A`)
- Characters necessary for correctly rendering visible Unicode text, provided
  their use conforms to UTS #55 (especially for BiDi handling).

An invisible character is necessary for rendering visible text if and only if it
is part of an extended grapheme cluster (per
[UAX #29](https://www.unicode.org/reports/tr29/) Section 3.1.1, Grapheme Cluster
Boundary Rules) that contains at least one character with a visible glyph.

### Allowed Syntax Characters

Syntax with semantics may use only these Unicode codepoints:

- `U+0020` through `U+0040`
- `U+005B` through `U+007E`

Exceptions:

- Names have their own rules.
- Comments allow all characters except those restricted elsewhere; UTS #55
  applies to comments.

### Spaces in Syntax

- When syntax specifies a space, the parser requires exactly one space
  (`U+0020`) in that position.

## Comments

Proposals:

- [DLP 11: Comments](../proposals/00011-comments.md)

Define supports single-line comments. A `#` character starts a comment;
everything from that `#` to the end of the line is ignored by the parser. A `#`
inside a string literal does not start a comment.

```ebnf
comment      = "#", comment_text ;
comment_text = { ? any character allowed per Define parsing rules, excluding U+000A ? } ;
```

## Types of Names

Proposals:

- [DLP 1: Types of Names](../proposals/00001-types-of-names.md)

Define reserves all words and symbols for its own use in syntax.

Names defined by the programmer are only allowed when prefixed by a name type
and surrounded by angle brackets (`<` and `>`).

The valid name types are currently:

- `position`
- `action`

```ebnf
name       = name_type, "<", name_content, ">" ;
name_type  = "position" | "action" ;
```
