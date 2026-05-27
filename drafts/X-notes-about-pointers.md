# Define Language Proposal X: TODO

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** January 16, 2026
- **Date Finalized:**

## Problems

Programs are not just static descriptions of positions in space. Something needs
to _happen_ to those positions in space. There needs to be some way to cause
action to occur.

The [Concepts](../spec/concepts.md) describe machines---particles that do
something under certain circumstances. We need syntax for these.

Traditional programming languages describe action in terms of various
constructs:

1. Simply raw lines of code written at the top level of the program. For
   example, in Python, you can just type `print("Hello World!")` into a file and
   run it, with nothing else.
2. Functions, which are similar to mathematical concepts that have arguments and
   they somehow take action based on those arguments or transform those
   arguments and "return" something else. How functions may be defined, their
   behavior, etc. is more or less strict in different programming languages.
3. Events, where a function triggers under certain conditions.
4. Specialized types of functions such as constructors, which create new objects
   that can then have functions called on them.

Conceptually, none of those things _exist_. What exists are particles in space.
Those particles can have qualities that cause them to take action under certain
circumstances. The question is: what are those circumstances, and what actions
can they take?

### Pointers

This is the exact point at which many programming languages decide that they
need "pointers," which are essentially variables that contain the memory address
of another variable. They reason, "in order for a function to be able to affect
the world outside of itself, the function needs some way of 'pointing' to those
things and changing them where they are without moving them."

Pointers lead to almost all the extreme complexity of programming languages, as
well as extreme complexity in static analysis of programs. For example, one of
the greatest problems in static analysis and formal verification is what's
called "pointer aliasing," where you have to consider if two pointers point to
the same object. (Like you have `a` and `b` which both point to `c`.) That one
problem means static analysis systems have to consider two possible worlds
_every time_ they see two pointers in the same context: one world where they are
different, and another world where they are the same. Eventually this compounds
until the number of possibilities explodes beyond what the verifier can ever
handle.

Pointers also merge the concepts of the programming language with the concepts
of how the computer functions (the idea of a memory layout)---one of the most
fundamental things that Define is working to get away from.

Conceptually, you could think of a pointer as a machine that says "I trigger on
something _over there_," or "I modify / look at something _over there_." Then
you allow multiple machines to refer to the same point in space. Essentially,
multiple machines all "view" the same point in space.

We have to decide:

1. Are views (pointers) a real thing that exists in actual universes?
2. If so, do we actually _need_ them in order to be able to express all possible
   programs efficiently (without excessive duplication of particles)?

The "are they a real thing" comes down to a few questions:

1. Can one particle modify another without moving it? Answer: You can change its
   qualities where it is. Otherwise, the only possible modification seems to be
   moving it.
2. Can you trigger a machine without moving a particle?
3. What happens when two machines see the same point simultaneously?
