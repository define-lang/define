# Define Language Proposal 24: Qualities May Not Define Qualities

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** January 20, 2026
- **Date Finalized:**

## Problems

With [DLP 21](00021-defining-machines.md) I described the machine definition
syntax, which included the ability for actions to define local positions, but
_not_ the ability to define other named actions. Why? And should we allow
position definitions to contain the definition of other positions, or not?

In essence, we have to ask ourselves: can the definition of a quality contain
the definitions of other qualities? For example, can
`define the potential position` contain a `define the potential action`
statement, and vice-versa? If so, why or why not?

## Solution

The decisions were:

Qualities may not contain the definitions of other qualities. To be clear, this
means that `define the potential` statements may not contain within them other
`define the potential` statements.

## A Real Program

N/A in this proposal, because we are only explaining and justifying decisions.

## Why This is the Right Solution

A quality is a definition of an abstract concept. Only when you apply it to a
dimension point does it become "real." A _definition_ is an abstract thing. It
doesn't make sense for a definition to define another definition. What does that
even mean? To see this concretely, look at this imaginary syntax:

```
define the potential position<mv:example.com:bank:/balance> {
    it may only contain dimension points where {
        it has a value that is a decimal.
        it has the quality<standard:/numbers/constraints/non_negative>
    }
    define the potential position<overdrafted_by_amount> {
        it may only contain dimension points where {
            it has a value that is a decimal.
            it has the quality<standard:/numbers/constraints/non_negative>
        }
    }
}
```

It _looks_ nice, because it makes it visually apparent to us as programmers that
the `overdrafted` position is related to _only_ the `balance` position. But then
we have a confusion: Does assigning the `balance` quality to a dimension point
mean that the `overdrafted_by_amount` quality will always be automatically
created? It says it's a potential position, so what happens? Super confusing.

Other languages have this mostly because it allows for access control (saying
things like "only the code for `balance` can update the `overdrafted` quality").
We plan to have a much more thorough and complete access control system that
solves that problem much better.

Essentially, allowing inner qualities gives us a bookkeeping system (these two
qualities are associated) and that's it. It is confusing because the inner
quality doesn't behave the same way as any other part of the quality definition.
All the other definitions become "part" of the dimension point when the quality
is assigned to the dimension point.

As a side note, another reason to avoid this is that you get into dangerous
territory with logical systems when you allow abstract concepts to contain the
definitions for other abstract concepts. This was a lot of the problem with
"naive set theory" that was broken by Russell's Paradox. To fix it people start
to try to introduce concepts like "universe layers" (a concept that exists in
Lean to solve some of this, as I understand it) but whenever you start trying to
"patch" a logical system to fix it, usually that means there's something
fundamentally wrong with it. In this case, what's fundamentally wrong is
allowing multiple layers of definitions that define other definitions. It is not
necessary to allow that in order to express all valid logical constructs.

## Forward Compatibility

This prevents a feature from existing that is very confusing to interpret. I'm
not confident it affects forward compatibility one way or another, but it does
prevent us from having a lot of programs where the programmer misunderstood the
semantics. Having those programs actually introduces its own unique sort of
forward-compatibility problem: "I thought I was doing something and then you
refactored it and it broke," when in reality it was always broken.

## Refactoring Existing Systems

I believe the variable and function-definition syntax of any existing
programming language could still be refactored into Define, even with this
limitation. In fact, I believe we could still keep the compiler guarantees of
every language intact.

There _are_ various difficult situations. Scala's path-dependent types are
probably the hardest to reason about, with this limitation:

```scala
class Graph {
  class Node
  var nodes: List[Node] = Nil
}

val g1 = new Graph
val g2 = new Graph

// In Scala, g1.Node and g2.Node are DIFFERENT types.
// You cannot put a g1.Node into g2's list.
```

The limitation in our system is that all our qualities have global names, and
you can't define qualities inside of other qualities. However, even here in
Scala there is really a pattern happening in the compiler implementation that we
_can_ represent, even if it's complex.

When you compile that example Scala does three things:

1. **Mangling (Globalizing the Name)**: It effectively lifts the inner class
   `Node` to the global scope. In the JVM bytecode, `Node` becomes a global
   class named `Graph$Node`.
2. **The Hidden "Outer" Field**: It silently adds a `private final` field to the
   `Node` class. This field holds a pointer back to the specific instance of
   `Graph` that created it.
3. **Erasure**: It erases the specific type distinction (`g1.Node` vs `g2.Node`)
   in the bytecode. Both just become objects of type `Graph$Node`.

And you can see that we actually could represent that in our system, even if
it's a bit tricky.

In general, almost all questions about "how do I translate this language to
Define" can be answered by: what does the compiler of that language _really do_?
