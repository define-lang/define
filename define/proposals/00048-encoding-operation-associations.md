# Define Language Proposal 48: Encoding Operation Associations

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** September 18, 2026
- **Date Finalized:**

## Problems

Just like with
[DLP 47 (Value Encoding Associations)](00047-value-encoding-associations.md), we
need to be able to associate encoding operations to logical operations. In fact,
it has nearly the exact same set of problems.

There are a few additional facts about encoding operations that are different
than just encodings.

For an encoding operation to work, its whole interface has to be compatible with
the operation's constraints. With encodings, we simply _asserted_ that they were
a representation of that value type.

Another point is that this has much more concrete implementation considerations.
Encoding operations are where "the rubber meets the road" for encodings. They
are the translation layer into hardware operations, which are really what
interpret bits.

The most concrete problem is that incorrect or ambiguous encoding operation
specifications can lead to unnecessary conversions at runtime. For example,
imagine that there are two encodings that could satisfy `/number/decimal` but
one has `sqrt` available and the other doesn't, but `add` and `subtract` are
much faster in the representation that lacks `sqrt`. What is the compiler
supposed to do in the situation where the same particle is used in `add`,
`subtract`, and `sqrt`? It has to convert to make `sqrt` possible, but when does
it do that? Does it always pick the slow encoding for a million `add` and
`subtract` calls just because there is one `sqrt` call? That doesn't seem
optimal. What if there are a million `sqrt` calls and just a few `add` and
`subtract`? What if there are a million of all three?

Conversion often isn't free at runtime, so there are real trade-offs to make
there.

There's also an optimization problem. "multiply and add" is an optimization
that's available for combining operations, but it doesn't cleanly map to either
the multiply or add operations.

## Solution

Unless otherwise specified, this has an identical solution to
[DLP 47 (Value Encoding Associations)](00047-value-encoding-associations.md),
with some of the names changed.

Config goes into `.define/encodings/encoding_operations.defcl`. It has the
format:

```protocol-buffer-text-format
encoding_operations: {
    operation_encodings: [
        # We define both the operation and the encoding operation, in this project.
        {
            operation: "/number/integer/add"
            encoding_operation: "/number/integer/64bit/add"
        },
    ]
}
```

The compiler validates that any loaded encoding operation is a valid match for
the operation it's specified to implement, but attempts to do this lazily while
still guaranteeing correctness of the configuration file.

### Project Root Config

The new field in the project root config is `has_encoding_operations`, like
this:

```protocol-buffer-text-format
    encodings: {
        has_encoding_operations: TRUE
    }
```

`has_encoding_operations` defaults to false.

### Ambiguity and Performance

The resolution of the "multiple possible encodings for the same value" problem
described in the Problems section is resolved in a few ways.

The first is that if there is no possibly resolvable encoding operation for a
requested logical operation, the compiler will throw an error.

The rest of the problem is resolved by framing it basically as a backend
optimization. The backend has multiple possible ways to deal with this:

1. It can convert values at the last possible moment before the rarest
   operation.
2. It can convert eagerly before a set of operations and then convert back
   later.
3. It can choose, on a permanent or temporary basis, to maintain two encodings
   side by side, possibly calculated in parallel (though of course cache
   coherency would have to be taken into account in a real backend).

All of these decisions would take into account the cost of conversion in the
context of the operation and the rest of the code, of course, compared to the
cost of not converting and running the slower operation instead.

Ideally the compiler would also allow (but not mandate) exposing this
inefficiency to the programmer and allowing them to make a different explicit
decision based on their intent.

### Optimization

Similarly to the ambiguity problem, for now we are leaving the "multiply and
add" optimization and other similar optimizations as a compiler backend problem.
My belief is that there are potentially infinite optimizations available based
on the exact context of the situation, and so the compiler will have to be able
to look at the graph of operations and make optimization decisions
appropriately.

## A Real Program

```bash
# .define/project/config.defcl
project: {
    universe_name: "mv:example.com:numbers"
    encodings: {
        has_encodings: TRUE
        has_encoding_operations: TRUE
    }
}
```

```bash
# .define/encodings/encodings.defcl
encodings: {
    value_encodings: [
        {
            value: "/number/integer"
            encoding: "/number/integer/twos_complement"
        },
    ]
}
```

```bash
# .define/encodings/encoding_operations.defcl
encoding_operations: {
    operation_encodings: [
        {
            operation: "/number/integer/add"
            encoding_operation: "/number/integer/64bit/add"
        },
    ]
}
```

```define
define the potential value<mv:example.com:numbers:/number/integer>.

define the constraint<mv:example.com:numbers:/bits/8to128> {
    its minimum value is 8.
    its maximum value is 128.
}

define the constraint<mv:example.com:numbers:/bits/33to64> {
    its minimum value is 33.
    its maximum value is 64.
}

define the encoding<mv:example.com:numbers:/number/integer/twos_complement> {
    define the encoding_option<bits> {
        it has the constraint</bits/8to128>.
    }
}

define the operation<mv:example.com:numbers:/number/integer/add> {
    define the view<a> {
        it may only contain particles where {
            it has the value</number/integer>.
        }
    }
    define the view<b> {
        it may only contain particles where {
            it has the value</number/integer>.
        }
    }
    define the view<sum> {
        it may only contain particles where {
            it has the value</number/integer>.
        }
    }

    it does {
        execute the encoding operation.
    }
}

define the encoding_operation<mv:example.com:numbers:/number/integer/64bit/add> {
    define the view<a> {
        it may only contain particles where {
            it has the encoding</number/integer/twos_complement> {
                it has the encoding_option<bits> {
                    it has the constraint</bits/33to64>.
                }
            }
        }
    }
    define the view<b> {
        it may only contain particles where {
            it has the encoding</number/integer/twos_complement> {
                it has the encoding_option<bits> {
                    it has the constraint</bits/33to64>.
                }
            }
        }
    }
    define the view<sum> {
        it may only contain particles where {
            it has the encoding</number/integer/twos_complement> {
                it has the encoding_option<bits> {
                    it has the constraint</bits/33to64>.
                }
            }
        }
    }

    it does {
        execute the computer operation.
    }
}
```

## Why This is the Right Solution

Identical to DLP 47, for the most part.

On the ambiguity and optimization problems, we are more or less saying "leave it
up to the backend," with a few recommendations for how the backend might choose
to resolve this. In general my belief is that that problem is complex enough and
implementation-specific enough that we should just leave it as implementation
details of the compiler.

## Forward Compatibility

Identical to DLP 47.

## Refactoring Existing Systems

Identical to DLP 47.
