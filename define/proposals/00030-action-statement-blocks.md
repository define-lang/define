# Define Language Proposal 30: Action Statement Blocks

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** January 24, 2026
- **Date Finalized:**

## Problems

Once you trigger an action, what happens? What statements are allowed in an
Action Statements Block?

## Solution

Action Statement Blocks may define positions. To be clear, this means they
define concrete positions with local names, not potential positions.

Action Statement Blocks may create, move, and destroy particles.

Action Statement Blocks may contain quality assignment statements.

Conceptually, when executing an Action Statements Block, all the code is
considered to execute instantaneously in sequence.

## A Real Program

```
define the potential action<mv:example.com:bank:/account/transfer_to> {
    it also assigns the position</account/balance>.
    it also assigns the action</account/withdraw>.

    define the position<run>.
    define the position<to> {
        it may only contain particles where {
            it has the action</account/deposit>.
        }
    }
    define the position<amount> {
        it may only contain particles where {
            # Imaginary syntax.
            it has a value that is a decimal.
            it has the constraint</positive>.
        }
    }

    it happens when {
        the position<run> has a particle.
        AND
        the position<to> has a particle.
        AND
        the position<amount> has a particle.
    } and it does {
        define the position<original_balance> {
            it may only contain particles where {
                it has a value that is a decimal.
            }
        }
        create a particle in position<original_balance>.
        set the value in position<original_balance> to position</account/balance>.

        create a particle in action</account/withdraw>::position<amount>.
        set the value in action</account/withdraw>::position<amount> to position<amount>. # Imaginary syntax
        create a particle in action</account/withdraw>::position<run>.

        create a particle in position<to>::action</account/deposit>::position<amount>.
        set the value in position<to>::action</account/deposit>::position<amount> to position<amount>.
        create a particle in position<to>::action</account/deposit>::position<run>.

        destroy the particle in position<run>. # Imaginary syntax.
    }
}
```

## Why This is the Right Solution

There's not a lot to justify here. This is simply the proposal that explains how
you actually execute code in Define.

Actions need "local variables" so you have to be able to define positions.

You can't define potential qualities in an Action Statements Block because that
doesn't make any sense. That would be exactly the sort of nonsensical mixing of
the universe of reflection and the program's universe that we are explicitly
avoiding in Define.

The point about actions executing instantaneously in sequence is necessary for
paradox detection and helps guide the compiler about when it needs to guarantee
certain sequencing in the program at runtime.

## Forward Compatibility

So far, all the syntax we allow in Action Statements Blocks are all individually
unambiguous, and there's nothing about combining them here that changes that.
Yes, the statements are written in order and, for the most part, we can't
re-order them. However, that's the fundamental nature of programming---that
programmers specify instructions to execute in some sequence.

One of the interesting things about Define is that we actually _could_ trace the
dependency tree of some lines of code to see which ones _actually_ have to be
sequenced that way, and we _could_ re-sequence them, in many cases where we
could prove the new ordering is equivalent in functionality to the previous
ordering.

## Refactoring Existing Systems

It should be possible to refactor the variable definition and movement syntax of
almost all languages into this format. Otherwise, there are no existing Define
programs with action statements in them before this proposal.
