# Define Language Proposal 41: Modular Destructor Analysis

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** April 24, 2026
- **Date Finalized:**

## Problems

[DLP 34 (Destructors)](00034-destructors.md) proposes a flexible system of
destructors. However, it creates a particularly tricky set of problems for
modular analysis.

### 1: Called Actions Don't Know About the Parent's Added Destructors

Imagine that in Action A, we have a position named `position<my_file>`with the
qualities `position</file>` and `action</destructor>`, where
`action</destructor>` deletes the file when the dimension point in
`position</file>` is destroyed.

When then take `position<my_file>` and pass it into the interface position of
Action B. That interface position only requires `position</file>`. Thus, Action
B doesn't "know" the destructor exists. When we are analyzing Action B by
itself, Action B doesn't know that the destructor runs and can't check if
running the destructor will create an invalid state in the program.

Generating the runtime code for the destructor isn't too difficult; the program
simply needs to track that a destructor is attached to a dimension point and
execute that destructor when that dimension point is destroyed. However, modular
verification that destruction is safe has potentially very complex computational
cost if not handled correctly.

### 2: Destructor Ordering

[DLP 34 (Destructors)](00034-destructors.md) specifies that destructors are
processed in LIFO order (in reverse order of assignment). This is particularly
important when considering quality-required positions and actions, where the
destructors that were added last _must_ run first because they could depend on
positions that were quality-required.

However, interface positions on actions don't have to specify their constraints
in the same _order_ that the caller did. So how do we know what order the
destructors are going to be run in, at compile time?

### 3: Callees Can Make Changes

When verifying a destructor, what matters is the state of positions at the time
of destruction. However, let's go back to the problem of "callees don't know
about destructors their callers added." Only the caller knows that it needs to
verify the destructor, but only the callee knows the actual state of dimension
points at the time of destruction---information that we need in order to verify
the safety of running a destructor. So somehow we need to be able to do modular
analysis even though the necessary information to do it is split into multiple
locations.

### 4: Destructors Can Modify Quality-Required Positions

A destructor can quality-require another position, which will automatically mean
that position gets destroyed only after the destructor runs. However, this adds
tremendous complexity to the destruction cascade, because it means that one
destructor could change what's actually going to _run_ on another destructor.

A destructor could move, create, or destroy dimension points in another
position. It could assign a new quality to any position in another position.
This includes all children of quality-required positions.

This adds a potentially enormous computational cost to calculating whether
destructors are safe, because they can change things that happen after them.

## Solution

Each action checks only the destructors that _it_ added. However, it checks them
as though they were running at the moment of destruction, not running inside of
their own action.

Thus, the action that destroys a dimension point verifies any destructors that
_it_ added immediately, acting as though the destructor action was triggered and
ran synchronously.

The complexity of the solution comes in when you have to deal with destructors
that were added by the caller.

### Forbidden Actions In Destructors

Once an action becomes a destructor (that is, it has the Destructor Condition on
it) it gains certain restrictions.

**Upon completion, a destructor must leave all quality-required positions in the
state they were in when the action started.**

Before we had this restriction, I wrote out an enormously complex algorithm to
deal with the fact that destructors could modify the state of quality-required
positions, including adding or removing destructors to positions that would get
destroyed later in the cascade. Not only was it extremely hard to reason
through, it had an unacceptable computational complexity where every action in a
call chain would have to fully recompute the safety of every destructor in the
entire cascade for every destroyed dimension point.

There are four ways that a destructor could modify the state of another
dimension point that would cause us to have to do this recomputation: they could
**create** dimension points in quality-required positions, **move** dimension
points into or out of quality-required positions, **destroy** dimension points
in quality-required positions, or **assign** new qualities to a quality-required
dimension point. Some of these actions actually can be done, as long as the
state the dimension points were in at the end of the destructor is identical to
the state they were in at the start.

Using the system of
[DLP 37 (Automatic Position Presence Constraints)](00037-automatic-position-presence-constraints.md),
we can translate this into a relatively simple requirement:

**Destructors may not create any Automated Guarantees other than "this dimension
point will be in exactly the same position as it was with the exact same
qualities it had when we started."**

### Destruction Contracts

We have to modify the action contract to contain additional data. This is only
relevant for dimension points that that are passed in through interface
positions or that are accessed as quality-required positions in an action.

These additions only occur when an action destroys one of those dimension points
explicitly or automatically.

#### Destruction Fact

Action contracts must contain the information that the relevant dimension point
was destroyed (not just that the interface position is empty, but specifically
that _that_ dimension point got destroyed). This is the only way that a caller
can know to check the verification of destructors that it added.

Destructions must be contained in the contract in the order they were executed,
so that we know that the requirements of later destructions are fulfilled by the
guarantees of earlier destructions.

#### Child State

Action contracts must contain anything known about the state of all children of
destroyed dimension points immediately before destruction started. This is
needed because a caller could add a destructor that quality-requires one of the
other children of the destroyed point, and it will need to know the state of
that position to know whether what it _does_ with that position is valid.

To be clear, this is the full state of all transitive child positions that would
be destroyed. It's not just the state of direct child dimension points. What we
need to know is whether or not there are dimension points in all transitive
child positions, right before destruction happens.

Because the action that is performing the destruction may not be aware of every
quality on the destroyed dimension point, it may not _know_ the state of every
dimension point in every child. For example, you might have an interface
position with just `value<standard:/number/integer>` on it, but really that
position also had a bunch of child positions when it was passed in. Thus, each
Action in a call chain must update the destruction contract if it knows about
the last update to a position before its parent was destroyed.

Thus, each action in the call chain actually has its own, separate cumulative
Child State for the destruction contract of that dimension point.

Note that there is a more memory-efficient version of this possible, too, where
we do a forward pass through the reference graph that lets called actions know
which positions destructors added in the callers can actually affect, and so
callees only have to return the state of those positions. (However, if you want
to ship a compiled library, you would have to expose the full data for all
positions anyway, since you can't know what destructors your callers are going
to add.)

### Destructor Requirement Verification

Destructors have automated requirements just like any other action does. Their
requirements must be checked by the compiler before they run. Thus, whenever an
action adds a destructor to a dimension point that has a destruction contract,
it must use the Child State to validate that the destructor's requirements are
fulfilled. This also happens within the action that actually does the
destruction, if the action that does the destruction either (a) created the
dimension point or (b) assigned a destructor to that dimension point.

Since we forbid destructors creating Automated Guarantees, each destructor's
requirements can be independently verified.

It is worth noting that an action might not _know_ the state of the dimension
points a destructor depends on (because they aren't yet populated in the Child
State---a caller higher up the chain needs to populate them). In this case the
destructor creates a new Automatic Requirement for the action in which it is
added, which behaves just like a normal Automatic Requirement from
[DLP 37 (Automatic Position Presence Constraints)](00037-automatic-position-presence-constraints.md).
It should, however, note in any error messages where the requirement comes from
and why (ideally indicating where the dimension point gets destroyed).

### Runtime Implementations

The above algorithm only describes the verification that the compiler must do at
compile time to prove that destructors are safe. However, the algorithm does
expose the complexity that different destructors run based on different call
chains. There are three ways a compiler could implement this in code generation:

1. **Tables**: Use some lookup mechanism to "attach" destructors to dimension
   points at runtime. When the dimension point is freed, inject code to check if
   it has destructors and do a lookup. This is inefficient and adds a mandatory
   "runtime library" to Define programs that I would like to avoid.
2. **Branching**: Use branching to say "run Destructor B if a special flag is
   set on this function" and then always pass in to that function whether it
   needs to run Destructor B. This is more efficient than the "runtime library"
   situation, but adds additional tracking and overhead at runtime to track a
   concept from the universe of reflection.
3. **Monomorphization**: Generate a separate set of functions for each call
   chain that has a different destructor stack. This should usually work but
   sometimes will result in a combinatorial blowup of functions to generate.

Thus, the compiler will need to make this trade-off intelligently, probably
between Branching and Monomorphization. This is mostly noted here as the subject
of a future proposal around compiler optimization and code generation.

## A Real Program

Note that some syntax is imaginary below, especially around dealing with
external state outside of the program or the specifics of value types. This
example demonstrates just the simplest case: a caller attaches a single
destructor the callee has no knowledge of, and that caller knows everything
about the Child State.

```
define the potential position<mv:example.com:example:/file_name> {
    it may only contain dimension points where {
        it has the value<standard:/string>.
    }
}

define the potential position<mv:example.com:example:/file> {
    it may only contain dimension points where {
        it has the position</file_name>.
    }
}

# Generic utility that destroys any DP carrying /file. It
# adds no destructors of its own and cannot see what destructors
# callers have baked into the dimension point.
define the potential action<mv:example.com:example:/close_file> {
    define the position<target> {
        it may only contain dimension points where {
            it has the position</file>.
        }
    }
    it happens when {
        the position<target> has a dimension point.
    } and it does {
        # The destruction event. We record the  Destruction Fact:
        # the DP in position<target> was destroyed.
        #
        # No Child State is recorded because this action does
        # not know anything about Child State.
        destroy the dimension point in position<target>.
    }
}

# Caller-attached destructor.
define the potential action<mv:example.com:example:/delete_file_destructor> {
    this dimension point must have the position</file>.
    it happens when {
        this dimension point is being destroyed.
    } and it does {
        # Imaginary syntax.
        delete the file at the value in position</file>::position</file_name>.
    }
}

# The caller that adds the destructor.
define the potential action<mv:example.com:example:/make_and_close> {
    define the position<run>.
    it happens when {
        the position<run> has a dimension point.
    } and it does {
        define the position<my_file> {
            it may only contain dimension points where {
                it has the position</file>.
                it has the action</delete_file_destructor>.
            }
        }
        create a dimension point in position<my_file>.
        create a dimension point in position<my_file>::position</file>.
        create a dimension point in position<my_file>::position</file>::position</file_name>.

        # We trigger /close_file which causes us to read its destruction contract,
        # indicating position<target> gets destroyed.
        #
        # We know that that dimension point had action</delete_file_destructor>
        # assigned to it. We also know that action</delete_file_destructor>
        # has a contract that says that position</file> and
        # position</file>::position</file_name> must be occupied.
        #
        # We know from our own dimension point state that those positions
        # are occupied, so the verification passes!
        move the dimension point in position<my_file> to action</close_file>::position<target>.
    }
}
```

## Why This is the Right Solution

Essentially, this algorithm uses extra memory (child state) in exchange for
tractable computation times in large programs. The other potential algorithms
that I'm aware of involve either whole-program analysis (EXPTIME-Complete) or an
O(N^2) or O(N^3) analysis that re-analyzes the original destruction context
every time. I presently believe this is the right trade-off, although there are
pathological situations in which the memory requirements of this grow beyond
what is reasonable, so we will have to see how this works over time.

### Why Forbid Destructors From Creating Guarantees?

I went through numerous other attempts at this algorithm. You can see most of
those historical attempts in the commit history of this file. I think I rewrote
nearly this whole proposal about four times across a period of weeks.

Originally I did not forbid destructors from creating Automated Guarantees, and
that led to both enormous spec complexity, implementation complexity, and
computational complexity. In general, this problem is super hard to reason
through to start with. You can see in the commit history of this file that I
kept designing algorithms where I had misunderstood the semantics of my _own
programming language_. The problem of "destructors can modify external
positions" was making it nearly impossible to solve the problem, especially to
solve it in an efficient way. The previous algorithms all involved very long
descriptions and diagrams of how actions would have to interact, and then I
would realize there was some fatal flaw in the algorithm and have to start over.

Eventually I realized: there are no legitimate cases where a destructor actually
_needs_ to create guarantees outside of itself (at least, none that I can think
of). Destructors do need to be able to trigger actions and move things around
outside of themselves, but as long as they "clean up after themselves" and put
things back just like they found them, they can do everything they actually need
to do in the real world.

So, I threw away something valueless in order to get the properties that Define
needs.

## Forward Compatibility

One of the cool things about this proposal is that destructors are independent
of each other. In fact, I'm not even sure we _need_ ordering guarantees for them
anymore. Thus, not only can we statically know everything about destructors at
compile time, we could theoretically safely reorder them in the future (at
least, from the perspective of the compiler's verifier).

## Refactoring Existing Systems

To my knowledge there is no other programming language that has a
similarly-powerful automatic destructor system. Thus, I believe that all
destructors in all languages would be able to be translated into this system.
The one tricky part will be the inability of a destructor to self-reference the
dimension point to which it is assigned, which could dictate aspects of how you
have to design Define programs when translating them from other languages.
