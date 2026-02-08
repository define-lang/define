# Define Language Proposal 12: Definitions in the Universe of Reflection

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** January 7, 2026
- **Date Finalized:**

## Problems

### 1: The Universe of Reflection

The [Concepts](../spec/concepts.md) discuss the idea of the universe of
reflection where the _definitions_ of things live before they are made real.

We need syntax for defining things in the universe of reflection. The most
obvious things that live in that universe are qualities, triggers, and potential
forms.

### 2: Empty Space

The [Concepts](../spec/concepts.md) mention that we also need some way of
referring to empty positions in space. Let's dive into _why_ this is necessary,
to demonstrate an interesting problem that we have to solve with syntax.

Essentially, the concept of a position must exist before one can put something
into it. Logically there's a sequence: "First there's a place I'm going to put
something, and then something is there." That involves two concepts: the
intended position and the created dimension point.

However, "an unoccupied position" has no mass; it's not really "real." It's an
idea that the view point has. In other words, "an unoccupied position" is a
concept that lives in the universe of reflection, even if we later use that name
to refer to a dimension point in the "real" universe.

There are two ways to think about an intended position: relative to the
viewpoint (it's just a dimension point that we create relative to ourselves and
we are looking at) or relative to other dimension points (a single position in a
potential form).

## Solution

Defining things in the universe of reflection will use the syntax:

`define the type<name>`

At this time, that means `quality`, `potential_form`, `trigger`, and `position`
would all use this syntax. These names create space in the universe of
reflection.

## A Real Program

Note that the only parts of this syntax that are real are the
`define the type<name>` parts. Other parts (such as the use of `{` and `}`) may
be defined or revised by later proposals.

```
define the quality<mv:example.com:example:/foo/bar> {
    define the potential_form<bar> {
        define the position<x>.
        define the position<y>.
    }

    define the trigger<add> {
        # further definition of the trigger goes here
    }
}
```

I am leaving the syntax for positions inside of potential forms intentionally
vague for now, as that needs to be more thoroughly specified by a later
proposal.

## Why This is the Right Solution

The syntax logically reads like English.

We use multiple words to allow us to use the word "define" in other syntactical
contexts in the future.

When you define a thing, that's the only instance of that thing that can exist.
That's why we use the word "the," which means "that specific thing" and not "a"
which means "one of many potential options."

I acknowledge that some human languages do not have equivalent words to "the"
and "a" and that the concept behind them is very difficult for people who speak
those languages to understand. However, that is an acceptable trade-off given
the other reasoning here.

### Alternative Syntaxes

We could have done this many other ways. For example, we could have done it just
with the name:

```
quality<mv:example.com:example:/foo/bar> {

}
```

That significantly constraints our ability to change the language syntax in the
future and makes the job of the parser a bit more complex, because it doesn't
have symbols to look for that indicate definitions. Instead it has to look for
just a name (the most common type of token that will exist in most programs)
followed by some small symbol like `{`.

We also could have done:

```
quality mv:example.com:example:/foo/bar {

}
```

Which would look a lot more like existing programming languages. However, that
would abandon the "types of names" syntax we have that simplifies the parser and
gives us strong forward compatibility for the language syntax.

## Forward Compatibility

It seems unlikely that we would want to use the keyword "define the" for any
other syntax in the future, especially in a language called Define. However, if
we do want to somehow re-use the word "define" we still can, thanks to having
the extra word after it here.

## Refactoring Existing Systems

There are no existing systems to refactor. In fact, this is the first piece of
actual _syntax_ we are defining.
