# Define Language Proposal 19: Guaranteeing Qualities in Positions

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** January 15, 2026
- **Date Finalized:**

## Problems

In order to implement
[DLP 18 (Modular Constraints)](00018-modular-constraints.md), we first need a
way to indicate what qualities a position must have.

This can get into many complexities. For example, you can have full boolean
logic on what qualities are allowed. However, almost all real situations that
arise in programming require only knowing a list of qualities that we guarantee
are assigned to a dimension point in a position.

I will create a proposal for the other complexities in the future as I discover
they are needed, but for now we want to start with just a simple list of
required qualities.

Even with this, there are a few problems to solve.

### Open World vs Closed World

Can view points assign qualities to the dimension point that aren't in the list
of required qualities? In other words, is the universe open (view points can do
anything they want, unless a constraint tells them otherwise) or closed (view
points can only do what is allowed by the constraints and nothing else)?

### The Timing of Constraint Enforcement

When do constraints get enforced? This question is the most difficult to answer
during the creation of dimension points. When you first create a dimension
point, it has no qualities, and then you assign them in sequence. How do we know
when we need to check the constraint?

There are essentially two options:

1. You can make constraint enforcement on positions "lazy." That is, you don't
   enforce it until something else inspects the dimension point and needs to
   know what qualities it has.
2. You can create a syntax for "atomic" dimension point creation, where you
   basically turn off the constraint enforcer at the start of a block and then
   run it at the end of that block.

## Solution

### The World is Open

The world is open by default---everything is allowed unless a constraint says
otherwise. In this case, constraints only say what qualities a dimension point
in the position must have. The dimension point may also have other qualities.

### Syntax

We expand the syntax for defining a position. Positions with no constraints
still have the same syntax as before:

`define the position<name>.`

Note that that definition ends with a period. However, positions that must have
certain qualities in them are now written in this form:

```
define the position<name> {
    it may only contain dimension points where {
        it has the quality<mv:example.com:example:/foo>.
        it has the quality<mv:example.com:example:/bar>.
    }
}
```

Quality requirements are joined together with a logical AND.

### Enforcement

If the programmer attempts to move a dimension point into a different position,
and that dimension point does not have the required qualities, the compiler must
throw an error. This may _never_ be a runtime check. It must always be
statically detectable.

If we have a syntax for removing qualities, enforcement would also occur when
attempting to remove qualities from a dimension point.

Creation is slightly more complex, as noted in the problems section above. The
conceptual solution is to create an unconstrained position, assign all the
qualities you want to that position, and then move it into a constrained
position. However, that process will be _so_ common that we will need a syntax
that does it, which I will specify in a later proposal.

## A Real Program

```
define the position<green_blue_ball> {
  it may only contain dimension points where {
    it has the quality<mv:example.com:example:/green>.
    it has the quality<mv:example.com:example:/blue>.
  }
}

define the position<red_ball> {
  it may only contain dimension points where {
    it has the quality<mv:example.com:example:/red>.
  }
}

# Then you have to imagine a creation syntax here, like:
create a dimension point in position<green_blue_ball> {
  assign the quality<mv:example.com:example:/green>.
  assign the quality<mv:example.com:example:/blue>.
}

# Throws a compiler error.
move the dimension point in position<green_blue_ball> to position<red_ball>.
```

## Why This is the Right Solution

### Open World

My conceptual basis for this was: this is how most universes function---they
allow you to do everything until a specific restriction is created.

However, it also leads to many nice properties that we want in a programming
language. It allows programmers to be _more_ restrictive than the constraints
allow, if they want. You might have a library that takes any integer, but you
might know that your numbers will always be between 2 and 10, and so you could
specify that constraint _in addition_ on your own numbers in your own program.
That gets you even more safety and correctness in your own code.

Even though closed worlds are easier to "solve" in some forms of of logic
(you're checking "the qualities are exactly this set" instead of "the qualities
are a superset of this set"), open worlds are what provide the semantics that we
desire for programming.

### Syntax

The primary syntax I need to justify is the addition of
`it may only contain dimension points where` instead of just writing lines
directly like `it must have the quality<foo>`.

Basically, there are two reasons for this:

1. We want to keep it clear everywhere that we are making statements about
   dimension points, not about empty space.
2. There will have to be some way to also specify constraints on forms, and this
   keeps the wording identical between positions and forms.

The one awkward part is that you can't use the same wording for defining
constraints that a quality applies to a dimension point. Maybe that's okay,
though, because those are conceptually different things.

### Laziness vs Atomic Creation

I considered making constraint enforcement lazy. It makes some patterns easier,
such as a "builder" pattern where you want to have complex logic about what
qualities you're going to assign to a position.

However, it makes it much harder to reason about when constraints will be
enforced---it isn't intuitively what a programmer expects to happen. If there's
nothing that checks for a quality, the constraint might actually never even _be_
enforced. (That does have some advantages in dead code detection, though.)

Eventually I realized that the builder pattern can still be implemented even
with static, immediate constraint enforcement, because you can simply create
unconstrained positions, do whatever you want in them, and then move the
dimension point into the constrained position.

## Forward Compatibility

There is actually a pretty good chance we will want to expand this syntax. For
example, we will want to allow an "OR" / "XOR" condition for qualities, where
you can have multiple choices, most likely. Right now, the syntax is unambiguous
and doesn't have side effects, so we can deterministically refactor it any way
we want.

## Refactoring Existing Systems

There are no existing systems to refactor. We could refactor most languages'
type system into this. (For languages with union types, we don't yet have the
required syntax.)
