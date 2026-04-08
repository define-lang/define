# Define Language Proposal X: Modular Destructor Analysis

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** April 8, 2026
- **Date Finalized:**

## Problems

[DLP 34 (Destructors)](00034-destructors.md) proposes a flexible system of
destructors. However, it creates a particularly tricky problem for modular
analysis.

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
cost.

## Solution

For any dimension point that is passed into an action via one of its interface
positions (including children of such positions) or any dimension point that is
in (or is a child of) a quality-required position, if an action destroys that
dimension point (either explicitly or by moving it into a local and not passing
that local back out of the program), the action must expose two pieces of data
in its contract:

1. That the relevant dimension point was destroyed.
2. The qualities that the action was aware of the dimension point having
   immediately before its destruction.

This allows callers to do multiple things. We will imagine a call tree like
Action A -> Action B -> Action C for the sake of this explanation. We will
imagine that Action B knows about a destructor named Destructor B and Action C
knows about a destructor named Destructor C, for the same position.

First, Action B checks if it knows about any qualities that Action C did not
know about for that dimension point. If all qualities are the same, Action B
does not need to do anything. Action C already handled the destructor.

If Action B knows about more qualities for that dimension poont, it adds the
list of qualities _it_ knows about for that destroyed dimension point, and puts
that into its contract ("I, Action B, know that Action C destroyed a dimension
point with these qualities."). It also adds any guarantees created by Destructor
B into its contract as it normally would, if necessary (there's nothing special
about that statement, that's what would be happening even without this
proposal).

Then Action B checks to see if any of those new qualities are a _destructor_
that Action C did not know about, because that means we might have to do
analysis to see if the new destructor has safe behavior.

Now at this point, keep in mind that a destructor can only reference
quality-required positions on the _same dimension point_. It can affect only
that dimension point and its children (in particular, the children that the
destructor knows exist via constraints---a fact we can determine statically, if
necessary).

Also keep in mind that a destruction statement is guaranteed to destroy every
dimension point in all of those children and the dimension point itself. This
means that all actions taken on the position itself (and its children) _after_
destruction in Action C are always safe. Destruction returns things to a fixed,
known state---they don't exist.

Also, we know the deterministic order in which destructors run: destructors that
were added to a dimension point later always run before destructors that were
added earlier. Last in, first out. Thus, Destructor C always runs before
Destructor B.

This leaves us with only two problems to solve:

1. **During Destruction**: If Action C added a destructor that Action B did not
   have, and Destructor B's requirements are violated by Destructor C running
   first. For example, Destructor C moved a dimension point from some
   quality-required position that Destructor B expects to be filled.
2. **After Destruction**: If Action B's destructor creates a state in _sibling_
   positions that violates later requirements inside of Action C. For example,
   the destructor from Action B moves some dimension point out of a
   quality-required position that Action C's internal code expects to be filled.

Thus we can optimize a little further. If Destructor B does not affect positions
that Action C interacts with during or after destruction (either via Destructor
C or via its own code), no more work is required.

Conflicts **during destruction** are easily calculated. We can see the contract
of Destructor C and know if running it creates a requirements violation for
Destructor B. If Action A adds its own Destructor A, it basically runs with
propagated requirements from Destructor C and B, just like we normally propagate
requirements between actions, except that these are only propagated for these
destructors in this specific call chain (Action A -> Action B -> Action C). The
solution is somewhat memory intensive, but not deeply compute-intensive.

Conflicts **after destruction** are more complex. In order to understand their
safety, action must expose additional metadata about destructions. In
particular, they must expose any operations taken on _sibling_ positions
(positions that have the same parent as the destroyed position) of the destroyed
position after the position is destroyed that could lead to conflicts. For
example, the first time a create or move statement is taken on a sibling
position or any transitive child of a sibling position. Then Action B must run
checks agaisnt those operations to make sure that Destructor B does not create
an invalid state in Action C, though this is only necessary to check against
quality-required positions that Destructor B interacts with thus and creates
guarantees about. This is likely to be the computationally expensive part of
this proposal.

For auto-destruction at the end of an action, the "after destruction" checks are
not necessary. Because of the order in which they are specified to occur, they
will always be safe. Only "during destruction" conflicts can occur during
auto-destruction.

One additional complexity to keep in mind is that destructors could add
qualities to dimension points which could themselves be destructors. So this
analysis sometimes must be done recursively, to some degree, if destructors add
destructors to other dimension points.

## A Real Program

## Why This is the Right Solution

## Forward Compatibility

## Refactoring Existing Systems
