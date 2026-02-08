# Define Language Proposal 21: Defining Machines

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** January 16, 2026
- **Date Finalized:**

## Problems

Programs are not just static descriptions of positions in space. Something needs
to _happen_ to those positions in space. There needs to be some way to cause
action to occur.

The [Concepts](../spec/concepts.md) describe machines---dimension points that do
something under certain circumstances. We need syntax for these.

There are numerous problems involved in creating machines. We will solve them
across multiple proposals. The problem we need to solve here is simply the
top-level syntax for machine definition, and then other proposals can go deeper
into the details.

At the highest-level, we need two things: a way to indicate what triggers an
action, and a way to say what happens when that trigger occurs.

## Solution

The high level syntax for a machine action will be:

```
define the action<name> {
    # This is called an Action Definition Block.
    # Other definitions go here

    it happens when {
        # This is called the Trigger Conditions Block.
        # Conditions go here.
    } and it does {
        # This is called the Action Statements Block.
        # Statements about what occurs go here.
    }
}
```

In the "other definitions" block, positions may be defined.

The blocks must be specified in the order above: first the definition block,
then the Trigger Conditions Block, and then the Action Statements Block. The
formatting of the block opening lines must be exactly as above (in terms of
what's all on one line).

### May Not Be Global

Actions cannot be defined in the global name scope. Doing so does not match our
[Concepts](../spec/concepts.md). _What_ would be taking the action, empty space?
Empty space can't take actions.

If you want to model a pure functional universe (a functional programming
language) you would create qualities that do nothing but each define a single
action, and then assign those qualities to dimension points.

### Local Name Scopes

The Action Definition Block is a local name scope. In other words, the statement
`define the action<name> {` starts a new local name scope.

The Action Statements Block is also a local name scope. In other words, the
statement `and it does {` starts a new local name scope.

The Trigger Conditions Block does not at this time create a new local name
scope, as we don't anticipate defining new names in that scope.

### Name Is Optional

In actions, unlike most definitions, the `<name>` is optional. So you can also
write:

`define the action {`

However, there is no way to refer to that action in any other part of the
program.

## A Real Program

We have to imagine a bunch of syntax that isn't yet defined, but a real program
here might look like:

```
define the quality<mv:example.com:example:/car> {
    define the position<car_location> {
        it may only contain dimension points where {
            it has the quality<mv:example.com:example:/coordinates>
        }
    }

    define the action<start_car> {
        define the position<key_slot> {
            it only contains dimension points where {
                it has the quality<mv:example.com:example:/key>
            }
        }

        it happens when {
            the position<key_slot> is not empty.
        } and it does {
            create a dimension point in position<car_location> {
                with the required qualities.
            }
            set the value in position<car_location> to 0.
        }
    }
}
```

## Why This is the Right Solution

In our [Concepts](../spec/concepts.md), machines are basically the consideration
that when some set of things occur, some other set of things occur as a result.
Thus we need this core syntax that indicates those two concepts.

In experimenting with actions, I discovered they needed to be able to define
positions that are part of the trigger itself, so that you can represent the
concept of "function arguments" that other programming languages have. It also
significantly simplifies reasoning about the program, because you know that
there are certain positions that are only known about by that action, not by
anything else.

## Forward Compatibility

All of the syntax is unambiguous. Given that we haven't defined semantics for
any of the syntax yet, we don't yet have to worry about that. Since we enforce
even the location of all statements, it should be possible to refactor this into
any other syntax in the future.

## Refactoring Existing Systems

There are no existing systems to refactor. The function syntax of every language
I'm familiar with could be refactored deterministically into this syntax,
however, as they all involve named arguments and a trigger (a function call) and
actions they do. Return values would be converted into positions that the
function knows about, with the caller moving dimension points out of that
position and into a position for their own use.
