# Define Language Proposal 11: Comments

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** January 3, 2026
- **Date Finalized:**

## Problems

### 1: Context That Inherently Exists Outside Code

One of the goals of Define is to make everything relevant to the program be
expressed in code, in the program itself. That means all structure, all actions,
all intentions, and all constraints should be expressed in code. However, that
does still leave some valid things that should be expressed in comments:

- Opinions about the system or code ("This is an ugly hack.")
- The reason _why_ something was done the way it was done ("We do this this way
  because we discovered that our users want the data formatted in this way,
  through research.")
- Notes about external human factors related to the code, especially future
  plans ("We will delete this in January 2024 when Joe fixes his library.")

Conceptually, you can think of comments as "the thoughts of the view point that
do not cause dimension points to be created, changed, or destroyed in the
universe, and which do not assign, change, or remove qualities from those
dimension points."

### 2: Temporarily Disabling Lines of Code

Developers commonly need to disable just one line of code or a block of code
while they are developing, temporarily.

### 3: Misusing Comments to Create a Meta-programming Language

In some languages, some frameworks try to use comments or similar structures to
design some sort of meta-programming language, where you change something about
the code due to how comments are structured. However, comments are inherently
free-form and so trying to do this almost always causes some sort of trouble.

## Solution

Define supports single-line comments using the `#` character. Everything from
the `#` character to the end of the line is treated as a comment and is
completely ignored by the parser. The `#` character is allowed within literal
strings, however, and does not represent a comment there.

Define does not support block comments (such as `/* */` or `<!-- -->`). If a
developer needs to write a multi-line comment, they must use multiple
single-line comments, one per line.

When compiling Define programs, the parser fully ignores comments as though the
entire comment did not exist. They do not appear in the AST during compilation.

Refactoring and static analysis tools for Define may set a parser mode that
includes comments so that they can preserve comments appropriately. How that
interacts with the AST or the specifics of how comments are preserved is
reserved for later proposals.

## A Real Program

Here are two example Define programs with comments:

```
# This quality is implemented in a particular, performance-sensitive fashion
# because the other approaches caused performance issues with large datasets.
# See issue #123 for details.
define the quality<example.com:my_project:/data_processor> {
  # TODO(issue/3476): Consider adding caching here in the future
  define the potential_form<process> {
    # The data structure below was chosen after benchmarking three alternatives.
    # See Issue #4763 for a record of that investigation.
    it has a dimension point in position<x> {
    }
  }
}
```

```
# Note: This was added to support the legacy API. We plan to remove it
# once all clients have migrated to the new API (estimated: Q2 2026).
define the quality<example.com:my_project:/legacy_handler> {
}
```

## Why This is the Right Solution

Using `#` for single-line comments is a simple, widely-understood convention
that matches many other programming languages (Python, shell scripts, etc.).
This means most editors will recognize them as comments even without advanced
Define-specific syntax highlighting.

I do not presently imagine a syntax that requires the # character to be used in
syntax otherwise.

### Why Not `//`?

It's a bit harder to parse (because `/` is valid syntax in many places, so you
have to look ahead further) and there's a chance that `//` is part of syntax we
would want to use, some day. For example, some languages use it to mean
something like "do integer division here instead of floating point division" or
other things.

### Why Not Block Comments?

Basically because they introduce two different ways to do the same thing, and
"there is one right way" is a core principle of Define.

Block comments do introduce parsing complexity, mostly around the question of
what happens when a block comment contains another block comment.

Nowadays, IDEs and editors allow developers to specify that they want to
comment-out a whole block of code and the editor will automatically add # marks
to the start of each line. So it's not even as much of an inconvenience as it
used to be. We may change our minds (I really do personally prefer languages
that allow block comments) but for now we are going with simplicity.

## Forward Compatibility

If we needed to change comment syntax in the future, we could deterministically
transform all `#` comments to any new syntax we might adopt, or remove them
entirely if we decided to eliminate comments.

The one thing you can't do is transform comments that have some significance to
the program or other tool. This is why they are ignored entirely by the parser,
so that the default Define tooling does not enable the ability to make comments
meaningful to the program.

## Refactoring Existing Systems

Since Define is a new language, there are no existing Define programs to
refactor. Programs without comment syntax wouldn't require transformation; this
would be a new feature.
