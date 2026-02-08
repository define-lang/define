# Define Language Proposal 14: Assigning Qualities

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** January 8, 2026
- **Date Finalized:**

## Problem

We need syntax for assigning qualities to dimension points.

## Solution

The syntax will be:

`assign the quality<name> to the dimension point in position<x>`

We are not yet defining what happens if you do this more than once to the same
dimension point. For now, this proposal assumes that you can only do this once
to a dimension point. That will likely change in the future, as points can
logically have more than one quality.

## A Real Program

```
define the position<x>.
create a dimension point in position<x>.
assign the quality<mv:example.com:example:/foo> to the dimension point in position<x>.
```

Note that the `.` ending the statements is not yet real, as it has not been
proposed at the time this proposal is being written.

## Why This is the Right Solution

As with other syntax in Define, we use multiple words. This protects our forward
compatibility and also reads intuitively for both humans and AI agents.

The downside of this syntax is that it is _incredibly_ verbose, even for Define.
Do we really need "to the dimension point?" I think we do, unfortunately. There
may be other syntax in the future that allows specifying constraints on
_positions_, and I think the language should make it clear that you're not
changing the position, you're changing the dimension point. You could move the
point to another position and it would still be the same dimension point, and
its qualities would go with it.

### Alternatives Discarded

#### Shorter

Most of the examples in the [Concepts](../spec/concepts.md) do something like
this: `assign the quality<bar> to position<x>`.

That's way shorter. It means exactly the same thing as above. It is unambiguous.
However, it is untrue---one is not assigning a quality to the position (empty
space). One is assigning the quality to the dimension point. Is this pedantic?
Probably. My present belief is that saying "to the dimension point" helps with
intuitive understanding.

#### One Line

We could have done:
`create a dimension point in position<foo> with quality<bar>`.

However, that removes the possibility of empty positions and dimension points
with no quality, or it requires us to have more than one way to do the same
thing.

#### Assignment at Definition

You could do something like:

```
define the position<foo> {
    it contains a dimension point.
    the dimension point has the quality<bar>.
}
```

or:

```
define the position<foo>.
create a dimension point in position<foo> {
    it has the quality<bar>.
}
```

That is certainly more convenient, in many ways, than the syntax I chose.
However, it breaks flexibility and seems likely to create more than one way to
do the same thing. In particular, I imagine that we will be able to both assign
qualities and remove them, and it would be nice to have some consistency in how
that is done.

#### Traditional Programming Syntax

We could use a syntax that looks more like other programming languages:

```
position<foo> := new quality<bar>
```

This would be intuitive for many existing programmers, as well as being much
more concise, but it has all the same problems that we discussed in
[DLP 13](00013-creating-dimension-points.md). It's actually even worse, here: it
dramatically limits your ability to change how qualities get assigned and how
objects get created and defined in the universe.

I expect that we will never transition to a syntax like this, because of how
limiting it is.

## Forward Compatibility

Because we have followed our general principle of multi-word keywords, it should
be easily possible to change our minds. There is no ambiguity in the language
between this assignment statement and any other statement.

## Refactoring Existing Systems

There are no existing systems to refactor. However, I believe we could refactor
the constructor / type-assignment syntax of many programming languages into this
syntax.
