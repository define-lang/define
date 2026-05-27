# Define Language Proposal 28: Triggering Actions

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** January 22, 2026
- **Date Finalized:**

## Problems

How do actions actually get triggered?

We need some basic syntax for the Trigger Conditions Block and semantics for
what that block means.

## Solution

First we need some very basic syntax for triggering actions. The simplest
condition that an action can trigger on is: "is there any particle at all in the
named position?"

Trigger Conditions Blocks express this with the statement:

`the position<name> has a particle.`

This is a trigger condition statement. There will be other types of trigger
condition statements in the future.

### Actions Trigger When Their Conditions Become True

Actions trigger whenever their conditions _become_ true. They do not
continuously fire after their conditions are true; they are basically "watching"
for their conditions to happen and then they trigger once when that becomes
true. If it ceases to be true and then becomes true again, the action will
trigger again.

### Actions Only Trigger On Something Changing

Conditions for a trigger are only checked after assignment of the action is
complete on a particle, and only checked when the state of particles change in
the program.

In other words, if an action would trigger upon the presence of a particle, and
that particle is already present when the action is assigned, the action does
not _check_ its conditions unless that particle becomes empty and then filled
again. Thus, the action does not fire when it is first assigned.

## A Real Program

```
define the potential action<mv:example.com:bank:/account/deposit> {
    it also assigns the position</account/balance>.

    define the position<run>.
    define the position<amount> {
        it may only contain particles where {
            # Imaginary syntax.
            it has a value that is a decimal.
            it has the constraint</positive>.
        }
    }

    it happens when {
        the position<amount> has a particle.
    } and it does {
        # Imaginary syntax.
        set the value in position</account/balance> to position</account/balance> plus position<amount>.
    }
}
```

## Why This is the Right Solution

My original syntax for this was `the position<name> is not empty.` However, I
generally prefer that all boolean statements be positive---it makes programs
much easier to read. So I switch it to the positive `has a particle`.

This matches our `has the [quality]<name>` syntax for constraints.

As far as actions triggering only once when their conditions become true, that's
the only rational way to build a universe. If you want something to trigger
continuously, have two functions that trigger each other.

## Forward Compatibility

The syntax is unambiguous and the guarantees of the language so far guarantee
perfect static analysis.

## Refactoring Existing Systems

It's very straightforward to refactor the trigger conditions of almost every
function and event in any language into this syntax.

For example, this Python code:

```Python
def increment(value: int) -> int {
    return value + 1
}
```

Translates directly into this:

```
define the potential action<mv:example.com:bank:/increment> {
    define the position<value> {
        it may only contain particles where {
            # Imaginary syntax.
            it has a value that is a integer.
        }
    }
    define the position<return> {
        it may only contain particles where {
            # Imaginary syntax
            it has a value that is an integer.
        }
    }

    it happens when {
        the position<value> has a particle.
    } and it does {
        create a particle in position<return>.
        # Imaginary syntax.
        set the value in position<return> to position<value> plus 1.
    }
}
```

To handle _every_ possibility, we simply need more conditions and ways to
specify multiple conditions, which will come in later proposals.
