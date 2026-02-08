# Define Language Proposal 16: Statement Terminators

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** January 9, 2026
- **Date Finalized:**

## Problem

We need a way to clearly indicate where statements end in Define. Statements
that create new blocks (like `define` statements that open curly braces) have
their boundaries marked by the block delimiters, but statements that don't
create blocks need some terminator to indicate where they end.

## Solution

We will use the period (`.`) followed by a newline as the statement terminator
for all statements that don't require new blocks. (This means we don't allow
trailing spaces at the end of lines, which is intentional.)

For example:

```
define the position<x>.
create a dimension point in position<x>.
assign the quality<mv:example.com:example:/foo> to the dimension point in position<x>.
```

## A Real Program

See above.

## Why This is the Right Solution

Originally I chose semicolons, because they are the most visually distinct from
other punctuation. There's a problem with periods, though, which is that it's
easy to confuse them with commas in many fonts, and so the developer types a
comma, thinks they typed a period, and are confused about why the program is
misbehaving.

This is not merely a theoretical concern. COBOL used periods to terminate
statements, and had a well-documented history of bugs caused by the fact that
they look so similar to commas. I'm sure it's very frustrating to look at code
and not be able to _see_ where the missing line terminator is.

However, as I was writing more and more Define, it was just too intuitive to
type periods. Define statements read like sentences. I as the developer just
_wanted_ to end them with periods. Reading full sentences that ended with
semicolons just didn't make sense.

Since Define as a language is very strict (and doesn't rely on commas), it
should be easily possible for our parser to tell the programmer exactly where
they missed a line terminator, eliminating most of the concerns from previous
languages.

#### Alternative Syntax: Newline-Based Termination (Python/Go style)

I also considered using newlines to terminate statements, as Python and Go do. I
personally like and prefer this syntax. We may switch to it in the future.
However, it creates more complexities for the parser and does create a few
(mostly unimportant) limitations on what syntax you can have, like "curly braces
must be on the same line as the statement or we can't tell a block is starting."

One problems I've run into with the syntax over the years is that it makes it
either ugly (Python) or confusing (Go) to have multi-line statements, and you do
sometimes need multi-line statements.

Another major issue (at least with Python, less with Go) is that it makes
writing an auto-formatter that wraps code at a certain line length _way_ harder
to write. This is not a theoretical concern; I worked on an auto-formatter for
Python at Google and this was a constant source of pain, bugs, and ugly choices
we had to make in the formatter.

## Forward Compatibility

The real potential ambiguity with periods at the end of lines is if you allow a
syntax for decimal numbers like `10.`. That syntax was allowed historically in
order to save memory and speed for very early compilers. There is no reason to
allow it in a modern programming language.

As such, it will be possible to make periods as terminators completely
unambiguous in our grammar. If we ever needed to change this syntax in the
future, we could automatically transform all periods to any new terminator
syntax we might adopt, their positions are clearly defined in every part of our
grammar.

## Refactoring Existing Systems

There are no existing systems. We could refactor code that used any existing
line terminator into this syntax, although newline-based terminators are a bit
harder to parse reliably.
