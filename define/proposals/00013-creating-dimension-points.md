# Define Language Proposal 13: Creating Dimension Points

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** January 8, 2026
- **Date Finalized:**

## Problem

We need syntax for creating dimension points.

We have no way to refer to dimension points other than by their position.

## Solution

As described in [DLP 12](00012-definitions-in-the-universe-of-reflection.md),
first a position must exist and then we can put something there. Positions are
concepts in the universe of reflection, but dimension points exist in the
universe of the program.

Thus, our syntax for creating a dimension point looks like this:

```
define the position<foo>.
create a dimension point in position<foo>.
```

At the moment, that syntax is real other than the `.` at the end of the
statements, which would be decided by another proposal.

It is an error to create a dimension point in a position already occupied by a
dimension point.

## A Real Program

See above. There isn't enough syntax yet defined to make an actual real program
here.

## Why This is the Right Solution

As with other syntax in Define, we use multiple words. This protects our forward
compatibility and also reads intuitively for both humans and AI agents.

For now we require separate syntax for defining the position and creating the
dimension point. This is because of the "one right way" principle of Define.
This is the only way to allow the options of creating empty positions _and_
filled positions, but keeping the syntax totally consistent either way.

One downside of our solution is that it puts the name at the end of the line,
even though the name is probably the most significant part of that sentence, for
the programmer.

### Alternatives Discarded

#### One Line

We could have simply just done: `create a dimension point in position<foo>`.
Many of the examples written before this proposal do exactly that, for the sake
of simplicity. However, that removes the possibility of defining empty
positions.

#### Creation at Definition

We could have a syntax like:

```
define the position<foo> {
    it contains a dimension point.
}
```

and:

```
define the position<foo> {
    it is empty.
}
```

I really like that syntax. It's intuitive and explicit. My current concerns are:

- It doesn't allow you to easily create the dimension point much later than you
  define the position, in the program. That may or may not be necessary; I
  haven't yet thought that through all the way.
- It may become confusing when we have a different syntax for defining potential
  forms and creating forms. My current experiments with syntax indicate that the
  form I've chosen is the most likely to consistently mean the same thing across
  different parts of a program.
- It feels less imperative, like you're talking about something that _could_
  exist rather than actually _doing_ something.
- Related to the previous point, it's confusing that you're defining something
  in the universe of reflection, but then causing something to exist in the real
  universe of the program inside of that block.

All of that said, I may still come back to this. It would be more consistent
with how we intend to define qualities, potential forms, and triggers.

#### Assignment-Like Syntax

We could use a syntax that looks more like other programming languages:

```
define the position<foo>.
position<foo> = new dimension point.
```

Or even more concisely:

```
position<foo> := new dimension point.
```

This would be intuitive for many existing programmers, as well as being much
more concise, but it has a few problems:

1. What `=` means is a constant source of confusion for new programmers. This is
   why many modern languages use `:=` for assignment and `=` for comparison.
2. We likely want to use `=` elsewhere in future syntax (such as constraints).
3. This syntax is much harder to prove forward compatibility for. It really
   limits our options for changing the syntax in the future.
4. It gets weird if we do want to add something like a local name context to
   `define the position<foo>`. How would we add that to that syntax? It would
   start to look very different from all the other syntax in Define.

#### Position-First Creation

We could put the position first to emphasize where we're creating:

```
define the position<foo>.
position<foo> now contains a dimension point.
```

However, see our explanation of why we don't start statements with names in the
[requirements](../spec/requirements.md).

## Forward Compatibility

By following our general principle of multi-word keywords, it should be easily
possible to change our minds. There is no ambiguity in the language between this
creation statement and any other statement.

## Refactoring Existing Systems

There are no existing systems to refactor. However, I believe we could refactor
the declaration syntax of most programming languages into this syntax.
