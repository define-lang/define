# Define Language Proposal 20: Atomic Creation

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** January 15, 2026
- **Date Finalized:**

## Problems

### 1: Atomic Creation of Dimension Points and Assignment of Qualities

In [DLP 19](00019-guaranteeing-qualities-in-positions.md), I decided that we
needed a syntax that, in essence, atomically creates a dimension point and then
assigns qualities to it. Since nothing like that is truly "atomic," what that
really means is we need a syntax that automatically creates a dimension point
with no constraints, assigns qualities to it, and then moves it into a position
that does have constraints.

### 2: Duplication

Also, in writing Define programs, one thing I discovered was that there is a lot
of potential for human error when you write a set of constraints and then a set
of quality-assignment statements. You write the quality name in the position
definition, and then you have to write the same quality name again in the
assignment statements. While we don't care about verbosity, we do care about
unnecessary duplication that can lead to human error and difficulty in the
correct maintenance of systems.

### 3: More Than One Way To Do It

When we create this new syntax, there's a danger of giving the programmer a set
of confusing options for how they are supposed to assign qualities to a
dimension point. That is, we could create more than one way to accomplish the
same thing, without a clear reason for a developer to choose one or the other.

## Solution

We do not change the syntax for creating dimension points. Instead, we simply
say that dimension points will always be created with any mandatory qualities
required by their position.

When creating a dimension point, the compiler will look at the position
definition and then go through the qualities listed in order and assign those
qualities in that sequence. However, the
`it may only contain dimension points where` constraint on that position will
not be checked until the end of the block.

Conceptually, what is happening here is that a dimension point is being created
in an anonymous position, and then being moved into the position that has the
constraint. The compiler could (and perhaps should) implement this exactly that
way.

### Optimization

In reality, the compiler doesn't need to check the constraint after assigning
the qualities, because it knows for sure that the dimension point has exactly
the qualities assigned.

### Parallelization

If the compiler can prove that it is safe to do so, the compiler may choose to
apply qualities to the dimension point concurrently. "Safe" means that applying
them concurrently would have the same outcome as applying them in sequence.

### Recursion

In the future, we will have syntax that causes quality assignment to create
other dimension points and assign them qualities. That happens exactly the same
way as this syntax and resolves in the same way. Each creation resolves and
constraints are enforced when each block ends.

In order to guarantee logical constraint safety, we _may_ have to enforce that
all such triggers happen synchronously and atomically in sequence, but we will
cross that bridge when we get there.

### Implications for Position Definitions

Note that there's an important point here: this gives semantics and side effects
to the way that position constraints are defined, because this creation syntax
relies on the ordering of the `it has the` statements in the position
definition. However, these semantics and side effects apply _only_ to the
creation statement. In other words, the compiler may choose to _check_ the
constraint in any order. It's only _creation_ that happens in a specific order
based on what's written in the position definition.

## A Real Program

```
define the position<ball> {
    it may only contain dimension points where {
        it has the quality<mv:example.com:example:/red>.
        it has the quality<mv:example.com:example:/blue>.
    }
}

create a dimension point in position<ball>.
```

That creates a dimension point in `position<ball>`, assigns it the quality red,
assigns it the quality blue, and then checks that it has the right qualities.
(In reality, since the compiler knows exactly what it's doing, it doesn't have
to check the constraint, in this situation.)

## Why This is the Right Solution

This eliminates duplication between the position definition and creation syntax
in almost all situations.

It does _not_ create multiple ways to do the same thing, because this is the
_only_ way you can successfully apply a quality to a constrained position.
Trying to create the dimension point and then assigning it a quality will fail
because you will momentarily have a dimension point without the required
qualities.

The one thing I don't like about it is that it hides the fact that those
qualities will be assigned in a particular order. However, the order is still
_knowable_: it's the order listed in the position definition. It does make it
hard to re-order the `it must have the` statements in code in the future, but I
think that's an acceptable trade-off.

This syntax _does_ mean that the compiler has to know the full definition of a
position when it creates a dimension point in it. That should be fine, since all
dimension points must be defined before you can put something into them. The one
thing we would have to address is: what happens if you want to call an API but
you don't have the full source code for the API? We will perhaps need "interface
definition" files in the future that contain the interfaces without the contents
of the triggers.

### Alternative: Explicitly Note That You're Assigning Qualities

This proposal originally proposed the syntax:

```
create a dimension point in position<foo> {
    with the required qualities.
}
```

The problem is: you _always_ want to do that. You literally _can't_ create a
dimension point in that position any other way. All this does is add two more
lines with no value.

### Alternative: "Assign" Statements Inside of the Block

Another way we could have done this is:

```
create a dimension point in position<ball> {
    assign the quality<mv:example.com:example:/red>.
    assign the quality<mv:example.com:example:/blue>.
}
```

We may need _something_ like that in the future, but right now I really want to
keep this limited to just the syntax we actually know that we _need_. Plus, that
syntax _definitely_ creates more than one way to do the same thing. It opens up
programmers to arguments about whether you should always assign qualities in the
atomic creation block or whether you should assign optional qualities outside of
it. There should just be one way to do that.

The largest future concern is what happens when we need things like "one of
these types" or "any of these types." We could change the syntax if we really
needed to, when we get there, but I have an idea of how we can keep this
existing syntax and still solve the problems. (Basically, just indicate which of
the "options" you choose, during creation.)

## Forward Compatibility

It is forward compatible except that it prevents us from re-ordering
`it has the` statements in code. Otherwise, it provides only one way to do
something and has unambiguous syntax.

## Refactoring Existing Systems

A syntax _did_ exist before this:

```
create a dimension point in position<ball>.
assign the quality<mv:example.com:example:/red> to the dimension point in position<ball>.
assign the quality<mv:example.com:example:/blue> to the dimension point in position<ball>.
```

As long as the assignment statements are in the same order as the position
constraints, we could refactor this. Realistically, we have to consider
[DLP 19](00019-guaranteeing-qualities-in-positions.md) and this proposal to be
tied together, because what we would have to do in order to refactor this is
define the position constraints in that order, not re-order the assignments.
