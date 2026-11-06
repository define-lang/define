# Define Language Proposal 57: Local Views in Encoding Operations

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** November 5, 2026
- **Date Finalized:**

## Problems

An Encoding Operation can be composed of other Encoding Operations. However,
imagine that you wanted to implement an Encoding Operation for `increment`:

```define
define the encoding_operation<my.domain.com:my_lib:/increment> {
    define the view<value> {
        it is read.
        it is written.
        it may only contain particles where {
            it has the encoding<standard:/number/integer/ascii>.
        }
    }

    it does {
        execute the encoding_operation<standard:/number/integer/ascii/add> {
            with view<a> looking at view<value>.
            with view<b> looking at literal<standard:/number>"1".
            with view<result> looking at view<value>.
        }
    }
}
```

That fails, because the executed encoding operation cannot reference `value`
twice (the rule that views may not alias).

Also, imagine that you wanted to implement a saturating subtraction by composing
normal subtraction and a `minimum` operation:

```define
define the encoding_operation<my.domain.com:my_lib:/subtract_saturating> {
    define the view<a> {
        it is read.
        it may only contain particles where {
            it has the encoding<standard:/number/natural/ascii>.
        }
    }
    define the view<b> {
        it is read.
        it may only contain particles where {
            it has the encoding<standard:/number/natural/ascii>.
        }
    }
    define the view<result> {
        it is written.
        it may only contain particles where {
            it has the encoding<standard:/number/natural/ascii>.
        }
    }

    it does {
        execute the encoding_operation<standard:/number/natural/ascii/minimum> {
            with view<a> looking at view<a>.
            with view<b> looking at view<b>.
            with view<result> looking at view<result>.
        }
        execute the encoding_operation<standard:/number/natural/ascii/subtract> {
            with view<a> looking at view<a>.
            with view<b> looking at view<result>.
            with view<result> looking at view<result>.
        }
    }
}
```

If we choose to apply the Single Assignment rule to Encoding Operations, that
would also fail, because `view<result>` gets written twice.

## Solution

We enforce Single Assignment and Views May Not Alias on Encoding Operations.

An Encoding Operation's Operation Statements Block may contain Local View
Definitions and View Setting Statements. They behave identically to local views
in Value Operations, with one difference: a local view in an Encoding Operation
is assigned exactly one encoding instead of exactly one value quality.

Similar to a Value Operation, an Encoding Operation may not execute an Encoding
Operation that has a read/write interface view.

Once we apply the Single Assignment rules, you can't write
`execute the computer operation` and any other statement together in the same
block, because `execute the computer operation` reads from and writes to every
view (and has to keep doing so, logically, since we can't see "inside" the
computer operation). Thus, `execute the computer operation.` now must be the
only statement in its Encoding Operation Statements Block.

## A Real Program

The smallest of three natural numbers, composed from the two-number minimum:

```define
define the encoding_operation<mv:example.com:example:/minimum_of_three> {
    define the view<a> {
        it is read.
        it may only contain particles where {
            it has the encoding<standard:/number/natural/ascii>.
        }
    }
    define the view<b> {
        it is read.
        it may only contain particles where {
            it has the encoding<standard:/number/natural/ascii>.
        }
    }
    define the view<c> {
        it is read.
        it may only contain particles where {
            it has the encoding<standard:/number/natural/ascii>.
        }
    }
    define the view<result> {
        it is written.
        it may only contain particles where {
            it has the encoding<standard:/number/natural/ascii>.
        }
    }

    it does {
        define the view<smaller> {
            it may only contain particles where {
                it has the encoding<standard:/number/natural/ascii>.
            }
        }
        execute the encoding_operation<standard:/number/natural/ascii/minimum> {
            with view<a> looking at view<a>.
            with view<b> looking at view<b>.
            with view<result> looking at view<smaller>.
        }
        execute the encoding_operation<standard:/number/natural/ascii/minimum> {
            with view<a> looking at view<smaller>.
            with view<b> looking at view<c>.
            with view<result> looking at view<result>.
        }
    }
}
```

Without `view<smaller>`, the first execution would have to write `view<result>`,
and the second would then read and write `view<result>` in the same execution.

## Why This is the Right Solution

Seems pretty obvious. The alternatives didn't make sense:

- We could have forced all compositions to be computer operations, forcing a
  custom implementation for almost all compositions and making it pointless to
  have the syntax for composing them.
- We could have relaxed Single Assignment or our aliasing rules, which would
  have just introduced something that we couldn't statically analyze.

## Forward Compatibility

Same as the syntax in Value Operations.

## Refactoring Existing Systems

Same as the syntax in Value Operations.
