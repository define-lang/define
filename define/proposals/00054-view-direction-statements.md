# Define Language Proposal 54: View Direction Statements

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** September 27, 2026
- **Date Finalized:**

## Problems

When the compiler sees a Value Operation or an Encoding Operation, it does not
know if the values being looked at are read or written.

As a result, it cannot keep track of whether a particle is set or needs to be
set.

Also, understanding the read/write behavior of value operations is critical to
automatic concurrency. (It's the key input, in fact, because you can read in
parallel all you want as long as there are no writes.)

## Solution

In the definition of an interface view of a Value Operation or an Encoding
Operation, you can specify one or both of: `it is read.` or `it is written.`.
These go onto their own line before the Position Constraint Block. When both are
specified, `it is read.` must come before `it is written.`. Each may only appear
once.

Specifying at least one of these is mandatory for views on Value Operations and
Encoding Operations.

A view that reads its value is called an "input view," and a view that writes to
its value is called an "output view." A single view can be both an input view
and an output view.

We call these View Direction Statements (because they specify if it's an "input"
or "output" view).

### Operations Must Fulfill Their Read/Write Contract

If a Value Operation does `execute the encoding operation.`, or an Encoding
Operation does `execute the computer operation.`, then it is considered that the
operation reads from all input views and writes to all output views.

Otherwise, the operation must actually fulfill its contract. If it is composed
only of executing other operations, it must at least _potentially_ read from all
the views it claims to read from, and _must_ write to all the views it claims to
write to.

### Restrictions

- Literals may not be specified as values for any output view.
- For [DLP 53: Unset Values](00053-unset-values.md) any particle that is looked
  at by an output view is considered to be set according to the narrowest
  constraints combined between the particle's constraints and the output view's
  constraints.

### Transitive Executions

A Value Operation executed by another Value Operation, or an Encoding Operation
executed by another Encoding Operation, cannot violate this contract. In other
words, if I am `operation</a>` and I execute `operation</b>` inside of my
Operation Statements Block, `operation</b>` must not do something that would
violate `operation</a>`'s contract in terms of which particles `operation</a>`
reads from or writes to.

In most circumstances, this means that transitive operations must not read from
write-only views and must not write to read-only views. However, a transitive
operation _may_ read from a write-only view if another operation within this
same Operation Statements Block has already written to it (as now the state is
guaranteed to be owned by this operation).

## A Real Program

```define
define the potential value<standard:/number/integer>.

define the potential literal<standard:/integer> {
    it has the encoding<standard:/encoding/string/decimal>.
}

define the operation<standard:/number/integer/add> {
    define the view<a> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/number/integer>.
        }
    }
    define the view<b> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/number/integer>.
        }
    }
    define the view<sum> {
        it is written.
        it may only contain particles where {
            it has the value<standard:/number/integer>.
        }
    }

    it does {
        execute the encoding operation.
    }
}

define the operation<standard:/number/integer/increment_by> {
    define the view<total> {
        it is read.
        it is written.
        it may only contain particles where {
            it has the value<standard:/number/integer>.
        }
    }
    define the view<amount> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/number/integer>.
        }
    }

    it does {
        execute the encoding operation.
    }
}

define the operation<standard:/number/integer/increment> {
    define the view<number> {
        it is read.
        it is written.
        it may only contain particles where {
            it has the value<standard:/number/integer>.
        }
    }

    it does {
        execute the operation<standard:/number/integer/increment_by> {
            with view<total> looking at view<number>.
            with view<amount> looking at literal<standard:/integer>"1".
        }
    }
}

define the potential action<define-lang.org:counter:/main> {
    define the position<total> {
        it may only contain particles where {
            it has the value<standard:/number/integer>.
        }
    }

    it happens when {
        this particle is created.
    } and it does {
        define the position<first> {
            it may only contain particles where {
                it has the value<standard:/number/integer>.
            }
        }

        create a particle in position<first>.
        set the value of position<first> to literal<standard:/integer>"3".
        create a particle in position<total>.

        execute the operation<standard:/number/integer/add> {
            with view<a> looking at position<first>.
            with view<b> looking at literal<standard:/integer>"4".
            with view<sum> looking at position<total>.
        }
        execute the operation<standard:/number/integer/increment_by> {
            with view<total> looking at position<total>.
            with view<amount> looking at position<first>.
        }
        execute the operation<standard:/number/integer/increment> {
            with view<number> looking at position<total>.
        }
    }
}
```

## Why This is the Right Solution

At first I thought maybe we could somehow infer that things are read or written,
but because Encoding Operations are separated from Value Operations, there's
nothing to infer from. You can certainly infer it when you're calling other
value operations, but even then it's probably easier to prevent bugs with the
explicit declarations here.

I also wasn't sure that Encoding Operations needed this. But since they can
execute other Encoding Operations directly, it seemed prudent to be able to
verify their contracts at compile time.

The other question I had was about CRDT-like behavior---are "read" and "write"
enough? The answer is that they are enough at the moment, but in the future we
may need to know whether operations are commutative and associative so that we
can re-order or parallelize multiple updates that can actually happen
independently. Mostly I suspect such behavior would happen at a higher level in
Define (it would be represented by actions, not operations) but I'm willing to
believe we discover something where commutativity would be relevant.

Originally I used `it is set` to try to make it clear that it's always a full
overwrite, but it was just too awkward. I kept wanting to write `it is written`
to make it match `it is read` so I changed it.

### Why Require Writes?

We require operations to write to any particle that they claim they write to.
For write-only views, the reasoning is straightforward: an operation that
doesn't write to a view it claims to write to could potentially leave a value
unset when the compiler thinks it's set, breaking our soundness guarantees.

There is an argument to relax that restriction for read/write views, however,
because we already know it's set. The problem there is just bad code and fooling
the compiler---in the future, the compiler will make more decisions based on
this data, such as how to parallelize operations, and if you "fool" it by not
writing, then you're reducing the compiler's capability. Also, writing to a
value will affect its value constraints.

For now I intend to keep the rule in place even for read/write, because it's
more forward-compatible to do so, but I might change my mind in the future.

### Relaxing Aliasing Rules

One thing I wondered is if we could relax aliasing rules now that we have these
restrictions. Like, are read/read aliases okay? Should the rule become "an
output view may not point to the same position as any other view?"

I do think there are situations in which read/read aliasing could hurt us,
though. We may want to do floating-point error analysis in the future, and those
algorithms often assume that the two inputs have independent rounding errors.

There could also be a future in which we want to prove whole-program properties,
like how many times a particle is read, which aliasing here would make difficult
or intractable.

In general, my expectation is that we will instead offer operations that
read/write to single particles when aliasing would otherwise make sense. (That
is, `increment_by` and `add` would be different operations.)

## Forward Compatibility

It's actually important that we specify this now; it would be hard to figure
this out automatically in the future, so programs need to have it from the
start. Otherwise, we've generally made the most strict choices we could and
provided static clarity on what's going to happen, so we should be safe.

## Refactoring Existing Systems

This one is tricky to determine in existing programming languages if you have to
deal with arbitrary functions. However, operations are supposed to be a fairly
limited set that represent something close to hardware primitives, and for those
the definitions in existing languages are usually pretty clear here.
