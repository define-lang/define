# Define Language Proposal 32: Position Initialization

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** January 26, 2026
- **Date Finalized:**

## Problems

Right now, when you assign a position to a dimension point, you then have to
manually create a dimension point in that position, or you have to manually
trigger some action that creates its dimension points. This breaks
encapsulation, because you either have to know the implementation details of a
set of actions (you have to know what positions they care about) or you have to
remember to manually run some "init" action on the dimension point (plus you
would have to remember to even _assign_ that init action to the dimension
point).

This also makes it hard to guarantee anything about the state of a dimension
point based on its qualities, because different parts of the program might be
initializing it differently.

## Solution

We create a syntax and semantics for initializing positions when they are
assigned.

### Block Syntax

Inside of a `define the potential position` block, the following syntax may be
written:

```
after it is assigned {
    # Position Assignment Block
}
```

The syntax within the Position Assignment Block is identical to the allowed
syntax in an Action Statements Block, with additions as noted in this proposal.

### Referencing the Current Position

Inside a Position Assignment Block, the position being initialized can be
referenced using normal position reference syntax (e.g., `position</path>`) even
though it is not done being defined.

### Restrictions

Code in the Position Assignment Block may only refer to this position and other
qualities that this position directly depends on. This is inherently true by the
syntax of the rest of Define, but it's worth noting here that this is the
intentional design of position initialization, to ensure encapsulation.

Also, I want to clarify that positions may not refer to positions or actions
they _transitively_ depend on. They must explicitly depend on positions in order
to refer to them. This is true for all things that use the quality requirement
syntax. Just noting it here again for clarity.

### Semantics

Position initialization is considered to occur as part of quality assignment. In
other words, when I do
`assign the position<name> to position<some_dimension_point>`, initialization
completes synchronously before the assignment statement is considered to be
done.

However, any actions triggered by the Position Assignment Block still fire
asynchronously. Thus, if a Position Assignment Block needs an action to complete
in order for the position to be correctly initialized, or needs to express an
expectation for an action to run, it must use a `wait until` statement during
init in order to ensure that.

When creating a dimension point in a constrained position (a position that uses
the `it may only contain dimension points where`) syntax, position
initialization occurs in the same way as described here---immediately after the
position is assigned to the dimension point (not after all qualities are
assigned to it).

## A Real Program

### Example 1: Basic Position Initialization

This shows the simplest case: initializing a position and creating a dimension
point in it.

```
define the potential position<mv:example.com:playground:/ball> {
    it may only contain dimension points where {
        it has the position</color>.
    }
    after it is assigned {
        create a dimension point in position</ball>.
    }
}
```

### Example 2: Nested Initialization

When a position initialization assigns another position that also has
initialization, the nested initialization must complete synchronously before the
outer initialization continues.

```
define the potential position<mv:example.com:game:/health> {
    it may only contain dimension points where {
        it has a value that is an integer. # Imaginary syntax.
    }
    after it is assigned {
        create a dimension point in position</health>.
        set the value in position</health> to 100. # Imaginary syntax
    }
}

define the potential position<mv:example.com:game:/character> {
    this dimension point must have the position</health>.

    after it is assigned {
        create a dimension point in position</character>.
        # At this point, position</health> has already been assigned to this dimension
        # point (due to the dependency), and its initialization has already completed.
        # So position</health> already contains a dimension point with value 100.

        # We can reference position</health> because this position depends on it.
        set the value in position</health> to position</health> * 2. # Imaginary syntax
    }
}

# Then inside of some Action Statements Block:

define the position<player> {
    it may only contain dimension points where {
        it has the position<mv:example.com:game:/character>.
    }
}

# When this executes, the following happens in order:
# 1. position</health> is assigned (due to dependency from </character>)
# 2. position</health>'s initialization runs, creating a dimension point with value 100
# 3. position</character> is assigned
# 4. position</character>'s initialization runs, changing health to 200.
create a dimension point in position<player>.
```

### Example 3: Initialization Triggering Asynchronous Actions

This demonstrates the interaction between synchronous initialization and
asynchronous action triggering.

```
define the potential position<mv:example.com:system:/ready_flag>.

define the potential action<mv:example.com:system:/on_ready> {
    this dimension point must have the position</ready_flag>.

    it happens when {
        the position</ready_flag> has a dimension point.
    } and it does {
        # This does something when the system is ready.
    }
}

define the potential position<mv:example.com:system:/status> {
    this dimension point must have the position</ready_flag>.
    this dimension point must have the action</on_ready>.

    after it is assigned {
        create a dimension point in position</status>.
        # This creates a dimension point that will trigger the </on_ready> action.
        # However, the action fires ASYNCHRONOUSLY, so it will not complete before
        # this initialization block finishes.
        create a dimension point in position</ready_flag>.

        # If we need to wait for the action to complete, we must explicitly wait:
        # wait until {
        #     # Some condition that indicates the action completed.
        # }
    }
}
```

### Example 4: Initialization with `wait until`

This shows the pattern for ensuring an action completes during initialization.

```
define the potential position<mv:example.com:db:/connection_string> {
    it may only contain dimension points where {
        it has a value that is a string. # Imaginary syntax
    }
}

define the potential action<mv:example.com:db:/connect> {
    this dimension point must have the position</connection_string>.

    define the position<run>.
    define the position<connected>.

    it happens when {
        the position<run> has a dimension point.
        AND
        the position</connection_string> has a dimension point.
    } and it does {
        # Imagine this does actual connection work.
        create a dimension point in position<connected>.
        destroy the dimension point in position<run>.
    }
}

define the potential position<mv:example.com:db:/database> {
    this dimension point must have the position</connection_string>.
    this dimension point must have the action</connect>.

    after it is assigned {
        # Set up the connection string.
        create a dimension point in position</connection_string>.
        set the value in position</connection_string> to "localhost:5432". # Imaginary syntax

        # Trigger the connect action.
        create a dimension point in action</connect>::position<run>.

        # Wait for the connection to complete before initialization finishes.
        # This ensures the dimension point is fully initialized before it can be used.
        wait until {
            action</connect>::position<connected> has a dimension point.
        }

        # Note that this pattern is probably not a good way to connect to a
        # database in Define, as that would be a surprising side effect of
        # assigning a position. It's just here to demonstrate waiting during
        # init.
    }
}
```

## Why This is the Right Solution

The idea here is to keep position initialization encapsulated, and also to
simplify both a human's and the compiler's ability to reason about the program.
If we can ensure that positions are always in a certain state after assignment,
it becomes much easier to enforce various guarantees about a program. It also
makes programs more consistent and easier to maintain, as it allows the
maintainers of individual positions to entirely own how they are configured.

The part I'm not certain about is how much of the action statement syntax to
allow during init. Most developers should only need to create dimension points
(and set values, using some future value-setting syntax), but theoretically
there could be a need to move and destroy dimension points, as well as to write
more complex code. So for now, I'm opting for the full flexibility of allowing
all action statements, even though it allows for a lot of bad programs to be
written. (Basically, Define has the same "constructors should not do work"
principle as all other languages, but still allows it).

One of the dangers of this syntax (or even allowing it in the first place) is
that it does create multiple ways to do the same thing. You can init a position
in the Assignment Block or you can manually create dimension points outside the
block. Possibly the compiler (or linter) should recommend that you choose the
assignment block if it notices you always doing manual init.

### Why On Assignment Instead of On Creation?

Why did I choose to make this happen when this position is assigned to a
dimension point, instead of when a dimension point is created in this position?

In most situations, those are the same thing, because assignment happens during
dimension point creation, on constrained positions. However, quality assignment
can also happen outside of that context, and that quality still needs to be in
the same state as if it had been assigned during creation.

### Why Not a Syntax Like "This Position?"

Originally this proposal described a syntax for referencing the current position
via the string `this position`. However, it became very awkward to implement in
the compiler, because it was the only time we referenced a name without the
format `type<name>`. It created an inconsistency, and I also realized that it
would create a special case when you were just string-searching for every place
the position was referenced. So I chose to keep the language internally
consistent by using `position</my/name>` instead.

## Forward Compatibility

Forcing synchronicity for initialization is a decision that we can't take back
later. However, I believe it is necessary for modular constraints to work
correctly, and thus inherently can't be changed. The same for keeping triggers
async, but that's the same decision as
[DLP 26](00026-action-triggering-order.md), so no new problems there.

Otherwise, the syntax has the same forward compatibility as Action Statement
Blocks.

## Refactoring Existing Systems

I believe all constructors in object-oriented languages could be refactored into
this syntax, because they could all theoretically be expressed as positions that
depend on each other. Sometimes you need two positions to be able to update each
other as part of initialization, but you could still do that here---you just
have to specify the dependency relationship so that one updates the other or
does all the necessary calculation for both of them (provided that makes sense
in the rest of the program). It does force you to have to think about exactly
how your actions depend on positions in that case, but I think that's fine; it
leads to better software design.
