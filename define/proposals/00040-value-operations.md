# Define Language Proposal 40: Value Operations

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** April 22, 2026
- **Date Finalized:**

## Problems

In [DLP 39 (Value Types)](00039-value-types.md) I laid out a system for how we
want to deal with the fact that there are different logical types of values and
different ways of encoding those values, in a programming language. However,
each component of that proposal requires its own separate proposal to talk about
the details of the implementation.

Surprisingly, I think it's easiest to start with a piece that's in the middle:
operations. So let's talk about some of the specific problems that operations
need to solve.

### 1: Logical Operations

In a traditional programming language, I write `x = 2 + 3` and then I expect the
compiler to magically figure out how to translate that into machine code.

This is all fine, until we get into a situation where what I _logically expect_
to happen isn't what the computer actually does. This is most often encountered
by programmers with IEEE 754 Floating Point numbers. If you do `x = 0.1 + 0.2`
in Python, the resulting value in `x` will actually be `0.3000000000004`.

This has two real issues for programming in general:

1. When people think of writing a test or a verified program, they tend to
   expect numbers to behave like numbers do in math.
2. That extra `0.0000000000004` almost never matters in any real, practical
   situation. Logically, it's essentially "noise."

For Define, it creates an especially difficult problem, because the compiler
needs to prove aspects of the behavior of these numbers at compile
time---behavior that differs logically from what the hardware does. Also in
Define, some operations are actually being performed by the compiler (the parts
that prove the program's validity) while others are being performed at runtime.

So first and most obviously, this tells us is that there are two separate
concepts we have to deal with: (1) how the programmer and the compiler "think"
of operations logically, ideally in some way that makes sense across platforms,
and (2) how operations actually work in the hardware.

### 2: Physical Operations

Operations on values need to translate to actual hardware instructions. They
need to be able to do so efficiently, and in a way that allows for maximum
optimization by the compiler. The ideal is that the programming language
translates into the most optimal instructions to the hardware, and that the
compiler has sufficient information to be able to make that transformation.

This is complicated greatly by the fact that different hardware targets behave
very differently, need different optimizations, etc.

### 3: Varying Behavior of Similar Operations

Adding two integers may seem like a logically simple operation, but even that
operation has many different _options_ attached to it. For example, the overflow
mode: do overflows trigger an error, do they saturate, or do they wrap around to
the smallest number again? For floating point operations, the number of options
are even larger.

While some aspects of a number are properties of its _encoding_, there are also
many properties that an _operation_ may have, even though all those different
options mostly produce logically the same operation.

For operations with many different options, it would be difficult, impossible,
or incomprehensible to produce a separate operation for every possible
combination of these options. There has to be some way to specify behavior on a
per-operation basis.

In order to keep the normal behavior of Define programs consistent (and to avoid
making the developer specify the same obvious fact over and over) there also
have to be default settings for every option.

### 4: Allowing New Operations

Many programming languages define the valid set of operations on values in the
language specification and then _only_ allow those operations. Developers using
the language cannot create new operations. They must write custom C / Assembly
code if they wish to take advantage of hardware features not available normally
in the language.

If you want to create new logical operations that behave identically to a
language's real operations (like implementing BigInt addition, for example) you
have to use higher-level constructs in most languages (functions, objects) to
implement those. That is often the right move, logically, especially with how
languages are designed.

Other languages let you "override" addition so that the `+` operator actually
means something different everywhere you use it. This is such a frequent source
of bugs, confusion, and optimization issues that it becomes a non-recommended
practice in most languages that support it.

## Solution

We introduce a new name type, `operation`, which always uses global names.

An operation is somewhat similar to an action, with the following differences:

1. It operates only on values.
2. It may only call other operations.
3. It is considered to always execute synchronously.
4. It is considered logically to execute atomically (though it may not actualy
   execute atomically on the hardware, the compiler guarantees its logical
   behavior is as though it were so executed).

To be clear, this means an operation cannot interact with dimension points
outside of itself in any way other than by interacting with their _values_. It
cannot trigger actions under any circumstances.

An operation exists entirely in the abstract universe of symbols, not in the
"concrete" universe of dimension points. It is the thing that an action _does_
with symbols; it is not an action itself.

### Syntax for Logical Operations

An operation that operates on logical `value` qualities is defined via:

```
define the operation<mv:example.com:example:/path> {
    # Operation Definition Block

    it does {
        # Operation Statements Block
    }
}
```

That is a definition in the global scope only. The contents of its blocks are
defined below.

#### Specifying Values for a Logical Operation

To keep syntax and the logical model of Define consistent, operations are
specified as acting on positions. You can imagine that there's a setup like
this:

```
A             B

    machine

       C
```

Where `A` and `B` are dimension points that each have a value, and `C` is a
dimension point that will store the result of some operation or set of
operations. The operation "looks" at the values on `A` and `B` and then "sets"
the value on `C`.

In Define's model of the universe, what is actually happening is that the
machine is looking at the qualities on A and B and setting or changing a quality
on C.

This is the one place in Define where we _reference_ positions without _moving_
them, because we need some way to talk about the positions we are modifying.

We define a new name type, `view` that uses only _local_ names. It is defined
only inside of `operation` and `encoding_operation` definitions. It has syntax
identical to a local position definition except that its constraints may not
contain other positions or actions.

Collectively, these are called the "Interface Views" for the operation (similar
to how we name an action's interface positions). They are defined only in the
Definition Block of an `operation` or `encoding_operation` before the Statements
Block.

#### The Operations Statement Block of a Logical Operation

The Operations Statement Block may contain only two types of statements:

1. Executions of other logical operations (as described in a later section).
2. The statement `execute the encoding operation.` which can be logically
   considered to determine the correct encodings for the inputs and execute the
   correct encoding operation, passing all of the Interface Views with their
   exact same names down to the encoding operation.

### Concrete Operations on Encodings

The actual operation that the computer executes is a separate definition from
the logical operation that the programmer writes. We refer to these as "encoding
operations," as they are operations that only know about and operate on values
that have concrete encodings. The syntax for an encoding operation looks like:

```
define the encoding_operation<mv:example:example:/my/operation/encoded> {
    # Operation Definition Block
    it implements the operation<mv:example.com:example:/my/operation>.

    # Interface View
    define the view<name> {
        it may only contain dimension points where {
            it has the encoding<mv:example.com:example:/my/integer>.
        }
    }

    it does {
        # Operation Statements Block
        execute the computer operation.
    }
}
```

This has a few different pieces.

#### Implementation Statement

Every encoding operation must indicate what logical operation or operations it
is intended to implement. It may say that it implements more than one logical
operation. The syntax for this is:

`it implements the operation<mv:example.com:example:/path>.`

An encoding_operation must have at least one Implementation Statement in its
Operation Definition Block.

Implementation Statements must come before Interface View definitions.

#### Encoding Operation Interface Views

Encoding Operation Interface Views must:

1. Have the exact same names as the views in the implemented operation or
   operations. (In the future, we will probably allow encoding operations to say
   their view names alias to the names in logical operations so that logical
   operations can use different namess where it makes sense.)
2. Specify encodings as their only explicit constraints.
3. Be defined in the same number and order as the logical operation. That is,
   there has to be one interface view definition for every interface view
   definition in the logical operation being implemented and no more. (In the
   future, we may allow for some views to have default values so that a single
   encoding operation can implement multiple logical operations.)

#### Encoding Operation Statements Block

Encoding operation statements blocks may only contain:

1. Execution statements for other encoding_operations. These are written just
   like a normal operation execution statement, except with an
   `encoding_operation` instead of an `operation`.
2. The statement `execute the computer operation.` which executes special native
   code that the compiler understands how to execute for this operation. (In the
   future there will be an extension mechanism for this so that developers can
   also write their own "compiler-defined" operations.)

### Executing an Operation

From an Action Statements Block, an operation is executed using syntax like:

```
execute the operation<mv:example.com:example:/my/operation> {
    with view<a> looking at position<my_local>.
    with view<b> looking at position<result>.
}
```

When the compiler encounters this, it either uses the encoding type of each
viewed position as specified or it infers the correct encoding of each viewed
position using an algorithm that will be described in a later proposal. It then
converts the values on the viewed positions to the appropriate encodings
necessary to perform the operation and executes the actual encoding operation.

### Views May Not Alias

Two views in an operation may not point to the same dimension point. Views must
point to distinct dimension points. This is very important for making
verification computationally feasible.

### This Solution is Incomplete

There are missing pieces of this solution that must be specified in later
proposals. I separated them out because this proposal was complex enough as it
was.

1. How the compiler knows that encoding_operations exist (since they are not
   named in any way that would allow the compiler to automatically discover
   them).
2. How the compiler infers what encoding_operation to run. It must do so
   securely, so that a dependency cannot redefine addition to be "do addition
   and also read the password out of memory and send it to me across the
   network" for the whole program.
3. How the compiler understands conversions between encodings and determines the
   correct ones when executing encoding operations.

Plus eventually we will need ways to explain logical constraints on numbers, in
order for Define to be a verified language, but that will come along with the
full implementation of
[DLP 18 (Modular Constraints)](00018-modular-constraints.md).

Eventually we will also need to be able to specify the guarantees that an
operation makes about its arguments (especially whether they are read-only or
guaranteed-write), primarily in order to implement paradox detection and perhaps
some aspect of modular constraints.

## A Real Program

A basic integer addition operation:

```define
# This is the operation actually used logically in the program.
define the operation<standard:/number/integer/add> {
    define the view<a> {
        it may only contain dimension points where {
            it has the value<standard:/number/integer>.
        }
    }
    define the view<b> {
        it may only contain dimension points where {
            it has the value<standard:/number/integer>.
        }
    }
    define the view<sum> {
        it may only contain dimension points where {
            it has the value<standard:/number/integer>.
        }
    }

    it does {
        execute the encoding operation.
    }
}

define the encoding_operation<standard:/number/cpu/integer/64bit/add> {
    it implements operation<standard:/number/integer/add>.

    extend the view<a> {
        it may only contain dimension points where {
            it has the encoding<standard:/number/cpu/integer/64bit>.
        }
    }
    extend the view<b> {
        it may only contain dimension points where {
            it has the encoding<standard:/number/cpu/integer/64bit>.
        }
    }
    extend the view<sum> {
        it may only contain dimension points where {
            it has the encoding<standard:/number/cpu/integer/64bit>.
        }
    }

    it does {
        execute the computer operation.
    }
}

define the potential action<mv:example.com:example:/add_numbers> {
    define the position<augend> {
        it may only contain dimension points where {
            it has the value<standard:/number/integer>.
        }
    }
    define the position<addend> {
        it may only contain dimension points where {
            it has the value<standard:/number/integer>.
        }
    }
    define the position<result> {
        it may only contain dimension points where {
            it has the value<standard:/number/integer>.
        }
    }

    it happens when {
        the position<result> has a dimension point.
    } and it does {
        execute the operation<standard:/number/integer/add> {
            with view<a> set to position<augend>.
            with view<b> set to position<addend>.
            with view<sum> set to position<result>.
        }
    }
}
```

## Why This is the Right Solution

There's a few aspects of this solution to discuss.

### Are Operations a Property of Numbers?

Some languages treat the variable or literal to the left of an operator as the
"owner" of the operator. That is, if you add `"string" + 3` you get `"string3"`
but if you add `3 + "string"` you get an error (strings can't be added to
numbers).

Mathematically and logically, this is not true. In formal mathematics, an
operation is an independent entity---a mapping from a tuple to a result.

It is an overextension of the ideas of object-oriented programming (and
showcases one of its limitations) to believe that an operation is a "method" on
its leftmost input. There are some operations that are fundamentally about the
full set of inputs and are not tied to any of them. Almost all programming
languages eventually have to acknowledge this if they want to allow you to write
`3 + 4.2` and have the result be a floating point number. Or they choose not to
acknowlege it and leave programmers in some very confusing situations when they
write something opaque like `x + y` and then don't understand that `+` is really
a _method_ of `x` and it's not the same somehow as `y + x`. (Not to mention that
this kills the compiler's ability to reassociate or vectorize operations.)

This means that both logical operations _and_ encoding operations need to be
defined as concepts on their own---an action that occurs based on its inputs.

### Why Global, Unattached Concepts?

So, logically, an operation is something that an action is doing. It's a
decision by a view point: this other dimension point will change its quality in
this way. So it is somehow logically attached to a machine (a dimension point
taking an action).

One option I considered was to have a dimension point that represented the
computer, and have operations be attached to it. I may still change my mind and
go down that path. The akward part of that is, where does the "computer"
dimension point come from? Does every action have to create it? It actually
exists in another universe, so it wouldn't even be a normal type of position.
And what does having the "computer" dimension point get us? It can't be created,
destroyed, or moved by the program. It's not clear that it would be meaningful
for it to have other positions or actions on it.

So basically, from the perspective of the program, a "computer" dimension point
would be a single, static object that just "has" operations on it.

Conceptually, this might be interesting for representing other computers or a
multi-chip system (like CPU / GPU or some DSP), but it's not completely clear
that we need that. Perhaps we do, and we'll redesign this when we get there. My
suspicion, though, is that instead we'll have operations like
`/cuda/float16/add` or similar when we get to talking about other parts of the
system. After all, they will actually be different operations that could require
different reasoning, since the hardware is different.

### Why Not Move Dimension Points Into Operations?

One thing I considered was making developers move dimension points into
positions owned by operations, in the same way they have to do it for actions.
However, it wasn't clear what the point of that would be, or what it would
logically be representing. Operations are what an action _does_ to symbols, they
aren't themselves a machine (except in the universe of the computer, where they
very much are machines).

Also, if operations can't move, destroy, or create dimension points, and they
are logically atomic and synchronous, what would the point of moving the
dimension points be? You'd just move them in to move them out.

Mentally, when I conceive of a machine operating, I conceive of it changing the
qualities of dimension points after they have come into a location where the
machine triggers on them. It knows where they are, they aren't moving, and it
changes their qualities. So I decided that the concept of Views could finally be
used, but only in this very narrow case where we are just referring to the
significance attached to a dimension point, not the dimension point itself.

### Why Separate Logical and Encoding Operations?

As we go into the future and we add more verification constructs, we need a
generic way to say things like "we are adding numbers" or "we are checking
equality." We want to allow developers to write portable code. They shouldn't be
forced to specify int32 / int64 unless they really _want_ to (or need to, like
at the edges of the program where data is entering in a specific format) but we
should still be able to verify the behavior of various operations like
arithmetic. Also, the compiler should be able to figure out from constraints (a
future implementation detail of
[DLP 18 (Modular Constraints)](00018-modular-constraints.md)) or general
inference what the optimal binary size is for everything (including perhaps the
format that will require the least conversions or workarounds to work with the
rest of the program).

### Why Verbose, Imperative Operations?

Most languages choose to use some standard mathematical layout for mathematical
operations, either `x + y + z` or `+(x, y, z)` or `+ x + y z`. This puts the
language into one of a few possible situations:

1. The compiler must decide what all operations mean.
2. All operations must be methods with the numbers being "objects."
3. The language must be a pure functional language that defines `+` once.

Lean, a modern formal verification language, took another approach to this: you
have to create your own functions to define every mathematical operation
(although Lean provides the standard, common ones in its standard library).
That's a bit closer to what we are doing. Lean did it in order to enable full
theorem proving and verification. We are doing it to give us flexibility for
programmers, the potential for extreme optimization, and extensibility. Plus we
are being more explicit (as far as I am aware) about how programmers can extend
the compiler's core primitives and expressing that those core primitives exist.

We chose to be especially verbose for a few reasons:

1. Extreme clarity.
2. Extreme simplicity of parsing and refactoring, sometimes even naive
   refactoring.

It's certainly annoying to type it all out as a programmer, and it takes up a
ton of space when you're trying to read it. But it does provide total clarity on
what's happening in the program.

You'll note that we also chose not to implement an "order of operations" or
parenthetical systems of algebraic mathematics. Once again, very annoying but
extremely clear---it makes the intent of the program blindingly obvious.

It will also be very optimizable (although existing languages mostly don't
suffer in this respect from their operations syntax) because we will know
exactly the developer's intention about ordering, and (in the future) we will

## Forward Compatibility

It's hard for me to imagine a syntax that we could _not_ translate this into.
This is dramatically more verbose and specific than any other language's
interface to the hardware (outside of writing raw Assembly) as far as I know.

## Refactoring Existing Systems

Every existing programming language's operations syntax should be translatable
into this form. There would be some challenges with translating a language like
Lean that defines _numbers themselves_ through inductive, recursive proofs, but
theoretically I imagine we could have a `/number/lean/nat` value type if we
really had to. That could get pretty complex, but I think it would be doable.
