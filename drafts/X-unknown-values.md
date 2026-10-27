# Define Language Proposal X: Unknown Values

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** October 27, 2026
- **Date Finalized:**

> **Note:** This draft was extracted from DLP 55 by Claude and still needs to be
> reviewed.

## Problems

[DLP 55 (Logical Operations)](../define/proposals/00055-logical-operations.md)
says what every value operation means, as a composition of logical operations,
so that the compiler can reason about the values it produces. But not every
operation has a meaning the compiler could know.

### 1: Operations That Have No Logical Meaning

Some operations don't compute anything the compiler could know about. The
clearest example is input I/O, like reading bytes from the network. As far as
the compiler is concerned, that operation just makes data appear out of nowhere.
There might be constraints on the _shape_ of the data, but the operation doesn't
fundamentally transform some input into some knowable output using a logical
basis.

How does an operation say that its result has no logical meaning?

### 2: What the Result Depends On

An operation like reading from the network still reads its input views, like
which socket to read from and how many bytes to read.
[DLP 54 (View Direction Statements)](../define/proposals/00054-view-direction-statements.md)
requires an operation to read every view it says it reads. If its result is just
"something the compiler can't know," nothing in the operation reads those views.

How does an operation with no logical meaning say what its result depends on?

### 3: Which Values Can Be Unknown?

If a value the compiler knows nothing about can end up anywhere, then the
compiler can't prove anything about any value that might have come from one. A
natural that the compiler knows nothing about isn't very useful, and if any
natural might be one, no natural is.

Which values can be unknown, and how far can an unknown value spread?

### 4: Compiling an Operation With No Logical Meaning

DLP 55 lets the compiler compile a value operation from its logical operations.
An operation with no logical meaning has nothing for the compiler to compile.

How does such an operation get implemented?

## Solution

### Unknown Value Statements

An operation says that its result is a value the compiler can't know anything
about with an Unknown Value Statement:

```define
set the value of view<result> to an unknown value.
```

If the unknown value depends on other views, the statement lists them in a block
after `based on`:

```define
set the value of view<result> to an unknown value based on {
    the view<socket>.
    the view<length>.
}
```

An Unknown Value Statement may only appear in an Operation Statements Block, and
the view it sets must be an output view of that operation. That view's value
quality must say `it may be unknown.` (see below).

The statement reads every view listed after `based on`. So each one must be a
view that a statement could read at that point: an input view, or an output view
or local view that an earlier statement has written. Each view may only be
listed once, in the order the views are defined. This is how an operation like
reading from the network reads its input views. The compiler still knows nothing
about the result, but it knows what the result depends on.

### What the Compiler Knows About an Unknown Value

The compiler knows nothing about an unknown value except its value quality. Any
logical operation that reads an unknown value produces an unknown value, and any
constraint about an unknown value fails. (See the
[Range Constraints draft](X-range-constraints.md).)

### Value Qualities That May Be Unknown

A value quality that may be unknown says so with `it may be unknown.`, before
any Logical Operation Support Statements:

```define
define the potential value<mv:example.com:example:/sensor_reading> {
    it may be unknown.
}
```

Only a value quality that says this may be the value quality of a view in an
Unknown Value Statement. Naturals and integers, for example, may not be unknown.
A value that comes from outside the program has some other value quality first
(like bytes from the network), and turning it into a natural is a separate
operation.

An unknown value is never a valid value of a value quality that doesn't say
`it may be unknown.` Writing an unknown value to a view of any other value
quality is an error, like writing any other value that isn't valid for a view's
value quality. So unknown values can only spread through value qualities that
allow them.

### Encoding Operations

A value operation that sets an unknown value has nothing the compiler can
compile, so it must have an associated Encoding Operation (see DLP 55).

## A Real Program

### Reading a Sensor

```define
define the potential value<mv:example.com:example:/sensor_reading> {
    it may be unknown.
}

define the operation<mv:example.com:example:/read_temperature> {
    define the view<result> {
        it is written.
        it may only contain particles where {
            it has the value<mv:example.com:example:/sensor_reading>.
        }
    }

    it does {
        # The Encoding Operation reads a sensor, so the compiler can't know
        # anything about the result.
        set the value of view<result> to an unknown value.
    }
}
```

```protocol-buffer-text-format
encoding_operations: {
    operation_encodings: [
        {
            operation: "/read_temperature"
            encoding_operation: "/read_temperature/i2c"
        },
    ]
}
```

### Errors

```define
define the operation<mv:example.com:example:/bad_unknown> {
    define the view<result> {
        it is written.
        it may only contain particles where {
            it has the value<standard:/number/natural>.
        }
    }

    it does {
        # Error: value<standard:/number/natural> doesn't say
        # "it may be unknown."
        set the value of view<result> to an unknown value.
    }
}

define the operation<mv:example.com:example:/bad_read_sensor> {
    # Error: nothing reads view<sensor_id>.
    define the view<sensor_id> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/number/natural>.
        }
    }
    define the view<result> {
        it is written.
        it may only contain particles where {
            it has the value<mv:example.com:example:/sensor_reading>.
        }
    }

    it does {
        # This needs to say "based on" and list view<sensor_id>.
        set the value of view<result> to an unknown value.
    }
}
```

## Why This is the Right Solution

### Why Unknown Values Are Explicit

[DLP 54](../define/proposals/00054-view-direction-statements.md) already
requires every output view to be written in the Operation Statements Block. So
an operation can't forget to say what its output views mean. Each one is written
by a logical operation, by a value operation, or by an Unknown Value Statement.

That's the same reason
[DLP 53 (Unset Values)](../define/proposals/00053-unset-values.md) got rid of
default values: the program shouldn't do something that isn't written. An
operation that really can't be understood by the compiler says so.

For input I/O, the honest logical meaning is "the outside world gave us some
value." The compiler can't know anything more than that, so "an unknown value of
this value quality" is the right meaning. It's also the strictest one: it fails
every constraint, so nothing can accidentally rely on it.

### Why Value Qualities Say Whether They May Be Unknown

The compiler can never know anything about an unknown value, and a natural that
the compiler knows nothing about isn't very useful. Most of the time, data from
the outside world is really bytes, and making a number out of it is a separate
step that can check what it got.

### Why Unknown Values Need Encoding Operations

Operations that have no logical meaning (like I/O) were one of the reasons that
operations used to be tied to Encoding Operations. Requiring an associated
Encoding Operation for every operation with an Unknown Value Statement keeps
that tie explicit exactly where it's needed.

## Forward Compatibility

We've made the strictest choices here: unknown values fail every constraint, and
any logical operation that reads an unknown value produces an unknown value.
Either of those can be relaxed later without breaking existing programs.

When we design I/O, we'll need a way to make assertions about external data at
runtime that the compiler then guarantees after the check. That's a different
problem, and it will build on top of this one.

## Refactoring Existing Systems

For operations whose meaning isn't one of the logical operations in DLP 55
(anything on strings, for example), the statements are an Unknown Value
Statement for each output view (based on the views it reads), the operation
needs an associated Encoding Operation, and the value quality has to say
`it may be unknown.`

A wrapping add in another language is not `standard:/number/add`. Until it has
its own logical meaning, it's an unknown value when it's translated into Define.
