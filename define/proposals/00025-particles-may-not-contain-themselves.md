# Define Language Proposal 25: Particles May Not Contain Themselves

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** January 20, 2026
- **Date Finalized:**

## Problems

Theoretically, one could write this in syntax:

```
define the potential position<y>.
define the position<x> {
    it may only contain particles where {
        it has the position<y>.
    }
}
create a particle in position<x>.
move the particle in position<x> to position<x>::position<y>.
```

So what should happen when you try to do that? In a real universe, you could do
that---move a point from where it is to some other point that it defines. The
problem in Define is that it creates an impossible situation for the compiler:
`position<x>` is now empty, meaning it defines nothing. So how can the
programmer continue to refer to `position<x>::position<y>`?

## Solution

It is an error to move a particle into any position that it defines. The
compiler will forbid it.

For example, you may not do this:

`move the particle in position<x> to position<x>::position<y>.`

Nor may you do this:

`move the particle in position<x>::position<y> to position<x>::position<y>::position<z>.`

No matter how deep the nesting, if the position itself is the prefix of the
name, the particle in that position may not be moved there.

## A Real Program

The program in the Problems section would throw a compiler error.

## Why This is the Right Solution

I cannot think of any other reasonable solution. `position<y>` is logically
defined by the location of a particle in `position<x>`.

You could definitely argue that it's actually defined by the empty _position_,
and that thus the empty position still has `position<y>`. However, we consider
positions to only exist in the universe of reflection as concepts before they
are occupied, so they define nothing before they are occupied. Trying to make
them define things when they are empty would lead to numerous complexities in
the language (you would have to essentially "create" empty positions for every
position that gets defined, even when it doesn't have a particle in it, and then
have confusing semantics for what happens when a particle gets moved).

It's possible I will change my mind later and decide that "positions define
other positions" is an okay semantic, but for now it's much simpler if we don't
allow it. The concept of what happens if you move a particle into a position it
defines is also very confusing as a programmer writing the language. (Not to
mention that it's conceptually confusing---what would it mean for a shape to be
defined by the "location" of empty space?)

## Forward Compatibility

Since this is simply forbidding something, it eases forward compatibility. We
can change our mind about this later, because no valid Define programs will have
done it.

## Refactoring Existing Systems

If existing systems _did_ currently allow this, we couldn't forbid it, which is
why we have to ban it as part of the language's original design.
