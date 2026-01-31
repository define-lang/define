# Define Language Proposal 36: Allowed Name Characters

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** January 30, 2026
- **Date Finalized:**

## Problems

### 1: Allowed Characters

[DLP 1](00001-types-of-names.md), [DLP 2](00002-universes.md),
[DLP 3](00003-authorities.md), [DLP 4](00004-multiverses.md), and
[DLP 5](00005-global-names-local-names-and-scopes.md) discuss the general format
of names, including what characters are allowed in the multiverse, authority,
and universe portion of global names. However, no previous proposal discusses
what characters are allowed in the "name" portion of a local or global name.

### 2: Naming Conventions

Most languages have some sort of convention for how things ought to be named. In
those languages, this is a polite request---you ought to name things this way.
Unfortunately, that tends to lead to some libraries or programs written in a way
that violates those conventions just because some programmer wasn't familiar
with what the conventions were supposed to be.

We solved most of these problems via
[DLP 1 (Types of Names)](00001-types-of-names.md). However, it still leaves a
decision up to the programmer that doesn't really matter---what format am I
supposed to type names in? It causes different programs to look different for no
reason.

Also (and this is less important) it makes naive static analysis (done by grep,
string searches, or regular expressions) a little bit harder because you can't
really know what format names will be in or what a name format will be.

### 3: Different Conventions Across Languages

One of my goals for Define is to be able to translate other languages into
Define. However, every language has different naming conventions. Is there some
way to enforce naming conventions differently for different codebases?
Traditionally people use linters, which are optional tools that provide optional
feedback. This leads to a lot of fragmentation in how these conventions are
enforced, even between developers on the same team, unless you _choose_ to
enforce the linter's requirements on the repository.

### 4: Unicode

Unicode causes all sorts of trouble in source code. One of the problems is that
you can insert all sorts of characters that "hide" injected code by making
text-rendering tools hide things that are actually characters but have real
meaning in the program. Another one is that you can write the same letter using
multiple different byte sequences (see
[UAX #15](https://unicode.org/reports/tr15/)). There are numerous difficulties
and complexities to correctly parsing and dealing with Unicode in source code
files.

## Solution

Even though this sounds simple ("say what format names should be in") the full
solution actually has multiple parts.

### Idiomatic Define

We introduce a concept called "Idiomatic Define." This is the style and
structure that Define programs should have when written natively in Define (not
as translations of other programming languages).

When feasible, the compiler will, by default, enforce the rules and restrictions
of Idiomatic Define. However, it will also provide configuration values via
configuration files in `.define` to override that enforcement with other
options.

### Default Allowed Characters and Name Format

In Idiomatic Define, the "name" portion of a local name or fully-qualified
universe name may only contain lowercase ASCII letters, ASCII digits, `_`, and
`/`. Local names in Idiomatic Define may not start with a digit, and global
names may not have a digit as the first character to appear after the last `/`.

All names in Idiomatic Define are written using `snake_case`, with all lowercase
characters and underscores between words. So the name "this is a B train"
becomes `this_is_a_b_train`. Define cannot actually enforce that underscores are
used correctly between words, but a linter may attempt to determine when
underscores are not placed properly and warn the programmer.

### Also Affects Directories

Because names can map to directory paths, directory paths on the disk that we
have to search through for code have the same name restrictions and behavior as
names, except that directory names (obviously) may not contain `/` by default.

### Naming Configuration

The compiler allows configuring that additional characters are allowed in names,
via Define Configuration Language files within the `.define` directory. This
exists in order to be able to translate existing programs (from other languages
that may have other naming rules) into Define.

The specifics of the configuration format will be reserved for another proposal.

### Cross-Universe Names

Each universe may have a different configuration for what names it allows, and
universes will often have to refer to names in other universes. As such, the
compiler will only enforce the naming rules of any particular universe on names
defined in that universe.

### Banned Characters

Certain Unicode codepoints are banned and may never be used in names, no matter
what any configuration says:

- `U+0000` through `U+001F` (control characters)
- `U+007F` through `U+009F` (extended control characters)
- `U+00A0` (non-breaking space)

Unicode codepoints below decimal 31 (ASCII control characters) are never allowed
in names (they cannot be specified in the compiler configuration as being
allowed).

### Character Escapes

If certain characters are allowed by the configuration, they must be escaped in
order to appear in names, by prefixing them with `\`. Characters that require
escaping are: `\`, `>`, `<`, and `:`.

### Name Security

If the compiler configuration allows characters that would cause names to
violate [Unicode Standard Annex #31](https://www.unicode.org/reports/tr31/)
(specifically the definitions of `ID_Start` and `ID_Continue`) an additional
compiler configuration value must be specified indicating that the user is aware
that they have allowed unsafe letters in names.

### Unicode Normalization

If the compiler configuration allows characters that must be normalized per
[Unicode Standard Annex #15](https://unicode.org/reports/tr15/), then any
identifier containing those characters will be normalized into Normalization
Form C and the compiler will internally use the name only in that form. This
also means when matching files on the filesystem for global names, if the path
contains Normalization Form D characters, it must be normalized into
Normalization Form C to be correctly compared with the global name we are
searching for. Note that this is more complex as some file systems (such as
MacOS today) tend to return filesystem paths using Normalization Form D.

This normalization will most likely happen in the lexer or parser, meaning the
rest of the compiler will never "see" names that are not in Normalization Form
D. However, this means that tools that do automatic refactoring of Define may
rewrite the bytes of names in source code into Normalization Form C when writing
out changes to code.

## A Real Program

Nearly every example program in every proposal is already written in this
format.

## Why This is the Right Solution

### Name Formatting

Other options are things like `lowerCamelCase`, `UpperCamelCase`,
`UPPER_SNAKE_CASE`, or just pushing all the words together `likethis`.

CamelCase frequently produces weird names that are hard to read, like `HTTPURL`.
Yes, there is a good solution to that, which is to name it `HttpUrl`, but
programmers often don't do that. Also see my example above about "this is a B
train," which in CamelCase becomes `ThisIsABTrain`, causing many readers to
wonder, "what's an Ab Train?"

`UPPER_SNAKE_CASE` is usually used for constants in most languages. It's
definitely not a good default because it requires holding Shift or hitting Caps
Lock for all names, which is weird when the rest of the language is all
lowercase. There's a chance we want to make that a convention in the future in
some situation, so maybe we will allow that, but let's wait until we need it.

If you have to choose only one name format for every name, `lower_snake_case`
wins. The one debate I had was about using underscores, since they require
hitting Shift on a normal keyboard. I eventually decided that it's natural
enough, and it looks more like a space than hyphens do (that was the other
option).

### Forbidding Starting Names with Digits

Idiomatic Define forbids starting names with digits because many other
programming languages cannot have identifiers that start with digits. Thus,
starting a name with a digit would prevent Define from translating into many
other languages.

### Name Configurations

I didn't want to just allow a free-for-all in most programs. I want every single
program written in Idiomatic Define to guarantee that it's using the same name
format. But there will be programs that _need_ an escape hatch. I want
developers to be able to specify exactly what the rules are for their codebase,
and then have the compiler hard-enforce those rules. I even want to allow for
libraries with non-standard names to exist in the multiverse.

If you just leave this up to a linter, you end up with a fragmented ecosystem
one way or another.

### Character Escapes

We need those escapes because of how fully-qualified universe names work. If we
want to add more escapes in the future, it's as simple as refactoring existing
programs to use those escapes.

### Unicode

I wanted to forbid Unicode in names by default in most programs. There are so
many complexities to working with Unicode that I wanted the parser and compiler
to potentially be able to optimize some of those complexities away if they
_know_ there aren't going to be any instances of Unicode in the syntax.

I specified the UAX#31 point because violating UAX#31 can lead to security
issues where attackers inject code that the developer does not notice, into a
program. The structure of define will make it harder for such code to take
effect, but I still imagine it's possible to attack Define in this way. However,
we do allow people to choose to do this, as long as they acknowledge the danger,
because I expect there will be _some_ programs that cannot be translated into
Define unless we allow UAX#31 violations.

In terms of choosing Normalization Form C, that's what basically every
programming language has chosen in the world. It is the more compact canonical
form to choose. I considered simply banning decomposed characters in identifiers
and never doing any normalization, but what really convinced me is that we are
going to have to deal with decomposed characters in things like filesystems,
anyway. Also, when a developer copies and pastes, they have no idea what
Normalization Form the characters are in. Plus, different text editors can
choose to use different forms. Banning decomposed characters creates complexity
for developers for no value.

## Forward Compatibility

Picking and enforcing a name format generally helps with forward compatibility,
though we do still allow a _lot_ of other potential characters in names, so we
have to watch out for that. Denying Unicode in most programs makes it more
likely that we avoid weird Unicode parsing errors that accidentally break
compatibility.

## Refactoring Existing Systems

There are no existing Define programs, but if there were, changing these name
formats can _sort_ of be done. You can easily convert from `lower_snake_case` to
any other format, but you can't reliably convert `CamelCase` because of the
`HTTPURL` problem where you don't know where words are supposed to be split.

In terms of refactoring existing programs in other languages, this is why we
allow name configurations.
