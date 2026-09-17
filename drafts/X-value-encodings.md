# Define Language Proposal X: Value Encodings

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** September 16, 2026
- **Date Finalized:**

## Problems

As described in [DLP 39 (Value Types)](00039-value-types.md), we need some way
to express that values have a particular encoding when actually used in the
machine. This presents us with a few problems.

### 1: Abstraction and Cross-Platform Code

Ideally we want programmers to be able to write a program that expresses their
intended logic, and then have the compiler be able to render that into working
code for any relevant hardware that you want to run that code on. Different
hardware uses different encodings for the same logical concept. The simplest and
most common examples are big-endian systems vs little endian systems, but there
are actually a ton of representation options that you have in hardware. For
example, the different components of a floating point or fixed number can be
different sizes. We could choose to represent strings in many different bit
orders or bit packings.

Not only should programmers _usually_ not have to understand these specifics,
they ideally want to write one program and make it work on many different pieces
of hardware. In traditional software, this is relevant when building
cross-platform code that might need to run on different CPUs or in different
OSes. In the field of AI inference, it applies to writing similar logic that
runs on different inference hardware. One can imagine many different
possibilities in the future here, as well.

### 2: Efficiency

One of the problems with a computer programmer expressing the encoding directly
in the program is that there's no guarantee that the requested representation is
actually the most _efficient_ representation, both in terms of memory usage and
processing time. Even worse, what is "most efficient" can change over time as
hardware changes. Once upon a time, a 32-bit integer was the most efficient
construct, because it was the CPU's word length. That has not been true in a
long time, but it's very likely that decisions were made about the overall
_design_ of a program based on that that have lived for decades past their
usefulness.

What you want is to be able to produce the most efficient possible machine code
that still implements the logic the programmer requested.

In the age of AI models, they are quite capable of doing optimization down to
the level of hardware instructions, but often must go through extensive
experimentation to get there. There are some experiments that mostly don't need
to be done, or at least where you could give the model a much better _baseline_
to start with because you have eliminated a bunch of options you _know_ are bad
options for that hardware, in advance. So you both decrease the amount of
experimental time required and you raise the maximum ceiling of possible
optimization. This is also relevant when you don't need or want to spend
extensive time with a model doing the optimization but need rapid, iterative,
deterministic output (such as while you're actively coding and testing something
in an iteration loop).

### 3: Variability

One of the problems with actual encodings is that there are many variants of any
given encoding. While any _specific_ piece of hardware has a limited set of
actual instructions and a specific circuit design, there are two problems:

1. There are many different types of hardware, and potentially infinitely more
   in the future.
2. You can choose to pack a lot of information into any set of bits, any way you
   want.

For example, integers on real hardware have specific bit widths, but that
doesn't mean that that's all we care about. We could be packing a bunch of 8-bit
integers into a 64-bit register. We could be doing SIMD (ideally with the
compiler figuring out that it can do so).

The one universal form of variability is bit width (given our decision that all
values are binary data in [DLP 38 (Binary Values)](00038-binary-values.md)).

The real problem with variability is how do we deal with a potential
combinatorial explosion of encodings? Do we have to support every possible bit
length of integers, from 1-bit to 512-bit, plus different endian-ness, plus
different signed-ness? Will that require us to write out thousands or millions
of different encoding definitions with specific optimizations for all possible
hardware states? That's obviously impossible, not to mention a bit hard on the
compiler.

## Solution

Encodings are a new global name type, they are declared with syntax like:

```define
define the encoding<mv:example.com:example:/integer/twos_complement> {
    # Encoding Definition Block
}
```

### Options

Encodings can have _options_ that are specified like this inside the definition
of the encoding:

```define
    define the encoding_option<bits> {
        it has the constraint</bits/8to128>.
    }
```

That creates a new name type `encoding_option`. It always uses local names.

This also requires us to introduce a new `constraint` global name type that will
be fleshed out more in later proposals (and whose syntax will evolve, but for
now this is all we need):

```
define the constraint<mv:example.com:example:/bits/8to128> {
    its maximum value is 128.
    its minimum value is 8.
}
```

The maximum and minimum values may be the same. For now, the value is always an
integer. Even if constraints gain more capability in the future, constraints
specified on encoding options must still be only integer constraints.

The minimum and maximum are not necessary, but if an option exists, it must
specify at least one of them.

Encoding operations gain syntax on their views like this:

```define
    define the view<a> {
        it may only contain particles where {
            it has the encoding</integer/twos_complement> {
                it has the encoding_option<bits> {
                    it has the constraint</bits/33to64>.
                }
            }
        }
    }
```

That would make that encoding_operation only apply when the value that `view<a>`
points to is between 33 and 64 bits. (Essentially, this is a 64-bit integer
operation.) The compiler would see that the encoding that supports 8 to 128 bits
would be appropriate, and can choose to use that encoding operation there
depending on its decisions around optimality.

Note that that makes the _naming_ of encoding options significant, because the
name has to match between the encoding and the encoding_operation.

If a constraint is not specified on an encoding operation's views, that means it
accepts all possible values for that option that that encoding accepts. (You can
think of it as being "the constraint is identical to the one specified on the
encoding option itself.")

### Choosing Between Conflicting Encoding Operations

What happens when more than one encoding operation can satisfy an operation for
the same encodings and option values? This is actually a fairly common problem
for compiler backends.

Overall, our goal should be to cause this system to provide the most efficient
runtime performance. Thus, we leave this decision to the compiler backend
(especially for encoding operations that are just
`execute the computer operation`). In the future, we may allow providing signals
to the compiler that would help the compiler reason through which operation is
most optimal, but there's a ton of work already done on backends like LLVM to
make those decisions efficiently, so any work here might actually be wasted.

In essence, what I'm saying is: how we make these decisions is an implementation
detail of the compiler that we do not intend to specify and which may change
dramatically over time.

### When To Use Options?

Options are used _only_ for aspects of an encoding that have potentially
infinite variability. I expect all (or nearly all) encodings will have `bits`
because any encoding could _theoretically_ be a variable bit width. However,
when there are a fixed set of representations, and representing that set as
separate encodings does not cause an uncontrollable combinatorial explosion, we
have separate encodings.

For example, for integers, you might have:

```
encoding</integer/twos_complement/big_endian>
encoding</integer/twos_complement/little_endian>
encoding</integer/unsigned/big_endian>
encoding</integer/unsigned/little_endian>
```

Then each of those would have an option `bits` to say how long they are. Then we
would have to implement encoding operations as appropriate to deal with the
combinations that we need to be able to actually represent at code generation
time.

## A Real Program

```define
define the constraint<mv:example.com:example:/bits/8to128> {
    its minimum value is 8.
    its maximum value is 128.
}

define the constraint<mv:example.com:example:/bits/33to64> {
    its minimum value is 33.
    its maximum value is 64.
}

define the encoding<mv:example.com:example:/integer/twos_complement/little_endian> {
    define the encoding_option<bits> {
        it has the constraint</bits/8to128>.
    }
}

define the encoding_operation<mv:example.com:example:/integer/twos_complement/little_endian/add/33to64> {
    it implements the operation<standard:/number/integer/add>.

    define the view<a> {
        it may only contain particles where {
            it has the encoding</integer/twos_complement/little_endian> {
                it has the encoding_option<bits> {
                    it has the constraint</bits/33to64>.
                }
            }
        }
    }

    define the view<b> {
        it may only contain particles where {
            it has the encoding</integer/twos_complement/little_endian> {
                it has the encoding_option<bits> {
                    it has the constraint</bits/33to64>.
                }
            }
        }
    }

    define the view<sum> {
        it may only contain particles where {
            it has the encoding</integer/twos_complement/little_endian> {
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

## Why Is This the Right Solution?

In designing encodings there were a bunch of problems that I had to overcome.

### Different Versions of the Same Encoding

One of the first problems was the infinite combinatorial nature of potential
encodings that could exist, even though any acutal set that would be used in any
program was finite.

At first I considered making _everything_ about an encoding into an option, but
then the question would be why do we even have encodings? Why don't we just have
properties of binary values? The problem with _that_ is that some options are
genuinely grouped together. To have a floating point you need a significand and
a mantissa. They have separate lengths, but they have to go together. They also
have a bit width. And they are, conceptually, a single standard (IEEE 754
floating point). As we get into implementation, I may change my mind about some
of this, as there may be requirements here that are not yet clear to me.

### What Should be an Encoding Option?

Another problem I had to work with is that when you think about an encoding,
there are a bunch of variations on that encoding that seem to go with it that
are just minor variations of the same encoding. An integer can be signed,
unsigned, big-endian, or little-endian. Operations on it can saturate, wrap, or
error on overflow. Which of those should be a property of the encoding or value,
and which should be a property of the operation?

One question I had was: when a developer declares a certain value, does that
mean they expect certain operational semantics from that type of value? Or are
operational semantics purely about the _operation_ that runs on that value?

Well, there are certainly certain types of values that we expect to have certain
semantics. For example, we expect floats to be inexact, and fixed points to be
exact within a bound of limited significance. That's a property that persists
through any operation. You can't add two fixed-point numbers together and have
them become inexact.

Signedness is also another property of the number itself. An operation can
change the sign of a signed value, but it can't changed the _signedness_ of the
encoding. And it certainly can't make an unsigned number negative.

On the other hand, overflow behavior _can_ be a property of an operation. You
_could_ have a situation in which for the same two numbers, at one point you
want the calculation to saturate, and at another point you want the operation to
error. Thus, that _must_ be an option related to the _operation_, not the
encoding or value type.

### MLIR

Probably the system most similar to ours overall is
[MLIR](https://mlir.llvm.org/docs/Rationale/Rationale/#introduction-and-motivation)
which has made a few design decisions that are similar to ours and a few that
are different from ours. Their design is a nice validation of the need to be
able to associate hardware operations with logical operations without losing the
context of what logical operation is being executed, when doing optimizations.

## Forward Compatibility

## Refactoring Existing Systems
