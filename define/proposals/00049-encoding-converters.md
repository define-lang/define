# Define Language Proposal 49: Encoding Converters

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** September 19, 2026
- **Date Finalized:**

## Problems

In all real hardware-level code, conversion between data types happens. In most
languages, this is invisible to the programmer, happening at the hardware level.
In others, it's somewhat explicit, but surprising. (Like our example of Rust
casts in [DLP 39 (Value Types)](00039-value-types.md).)

### 1: Encodings are not Consistent

Different hardware performs the same logical operations using different binary
formats. What is `float16` on a CPU might be `bfloat16` on a TPU. If the logical
constraints of our operations allow it, those encodings _might_ be
interchangeable, and they might not be.

### 2: Operation Sets Differ Across Platforms

As we have discussed in a few proposals about encoding operations, just because
one platform uses two's complement integers for both `add` and `multiply`
doesn't mean that another architecture will use the same encoding for both of
those operations. But the program only specifies one logical value, so we have
to be able to somehow convert invisibly in order to preserve abstraction and
cross-platform support for developers.

### 3: Parallelism

There are various choices you could make about conversion:

1. You could replace the existing value with the new converted form,
   permanently.
2. You could put the new converted form into a new memory location (for us,
   something like a new particle).
3. You could persistently retain multiple encodings of the same value.

Almost all of those choices have _some_ sort of consequence for parallelism, if
you want to be sure to guarantee reads come after writes. The worst one (but
very likely the most common) is replacing the value. A converter could do that
silently as part of what looks like a _read_ operation, in a way that's
invisible to the logical layer of the program.

### 4: The Scope of Conversion

Are converters allowed to change the semantic meaning of a value, or are they
bound to preserve its meaning? What does "the semantic meaning" even mean for
the value?

### 5: Chaining Conversions

You might need to get from encoding A to encoding C but there is no converter
for them. What if there is a converter from encoding A to encoding B, and a
converter from encoding B to encoding C, do we chain them?

If we allow chaining, how do we resolve multiple possible paths for chains? What
happens when the composed guarantees of multiple converters are not equivalent
to the guarantees that a direct logical conversion would require? (For example,
if we allow losing precision or inexact conversions at each step.)

If we don't chain them, and we require explicit converters for all conversions,
does that cause some sort of quadratic blowup of required converters to be
implemented?

### 6: Applicability

Some converters could work for every possible value in an encoding, others might
require constraints. For example, a truncating integer narrowing might require
that the value already fit into the new size. (That is, that a supposed "32-bit
integer" is already guaranteed to actually only have 16 bits of data in it.)

Also, there can be converters that only apply given particular encoding options.

Theoretically, there can also be converters that require relationships between
the input and output, like the converter accepts variable widths but always
outputs the _same_ width as the input. It's possible that we can solve that
problem purely with constraints on the input encoding.

### 7: Syntax

Do we re-use the `view` type for a converter even though it might allow aliasing
between its input and output? If you can permanently rewrite the format of data
on a particle as part of a conversion, that's sort of like aliasing views, but
really there was only one particle involved to begin with. (Also, sometimes
there could be multiple memory locations and at other times there could be just
one, which is confusing.)

## Solution

We create a new name type, `converter`, which always uses global names. The
syntax for a converter looks like this:

```define
define the converter<mv:example.com:example:/number/integer/unsigned/32to64bit> {
    # Converter Definition Block

    # Converter Input Statement
    it has the input encoding</number/integer/unsigned> {
        it has the encoding_option<bits> {
            it has the constraint</bits/32>.
        }
    }
    # Converter Output Statement
    it has the output encoding</number/integer/unsigned> {
        it has the encoding_option<bits> {
            it has the constraint</bits/33to64>.
        }
    }

    it does {
        # Converter Statements Block
        execute the computer converter.
    }
}
```

That shows one of the simplest possible converters.

### Converter Guarantees

Many of our Problems are resolved simply by making this statement:

Converters may not violate the logical constraints that the program expects to
be satisfied.

That means that inexact conversions are allowed, but only when they preserve the
program's logical guarantees. (For example, there are going to be a lot of
programs where the precision loss on float conversions simply doesn't matter.)

### Converter Chaining

There is no automatic chaining of converters. Define only supports explicit
converters that match the encodings in play. However, you may compose converters
by having the Converter Statements Block execute other converters, like this:

```
execute the converter</number/integer/8to16bit>.
execute the converter</number/integer/16to32bit>.
```

That would be an (inefficient) converter from 8 to 32 bits without having to
have any specific hardware implementation available.

Of course, the Converter Guarantees rule still applies to the overall converter.

### Converter Triggering

Converters are used automatically by the compiler when resolving operations for
code generation. The compiler decides how and when to use converters to best
effect.

Note that when deciding what converter to use, the compiler can potentially have
access to _both_ the value's constraints and the encoding's options. I expect
this to rarely be actually necessary, as the compiler usually will have already
resolved the optimal encoding for any value before we have to resolve how to
convert between encodings. However, the fact that we _need_ a conversion could
be taken into account when determining the encoding, too. (Like you could choose
an encoding that doesn't require a conversion, if the hardware cost justifies
that decision overall for the program.) In some case that I can't currently
predict, the converter itself could also be chosen based on information that we
only have from the value's constraints.

### Parallelism

The part of the compiler that determines parallelism must be able to leave
certain aspects of parallelism delayed until the full hardware resolution of
actions is known. That is, we may determine a logical level of parallelism that
is then "interrupted" by a converter writing a particle.

However, it is likely that the compiler can often still enable parallelism in
that situation via one of the other parallelism mechanisms in the Problems
section.

## A Real Program

```define
define the constraint<mv:example.com:example:/bits/8to128> {
    its minimum value is 8.
    its maximum value is 128.
}

define the constraint<mv:example.com:example:/bits/32> {
    its minimum value is 32.
    its maximum value is 32.
}

define the constraint<mv:example.com:example:/bits/33to64> {
    its minimum value is 33.
    its maximum value is 64.
}

define the encoding<mv:example.com:example:/number/integer/unsigned> {
    define the encoding_option<bits> {
        it has the constraint</bits/8to128>.
    }
}

define the converter<mv:example.com:example:/number/integer/unsigned/32to64bit> {
    it has the input encoding</number/integer/unsigned> {
        it has the encoding_option<bits> {
            it has the constraint</bits/32>.
        }
    }

    it has the output encoding</number/integer/unsigned> {
        it has the encoding_option<bits> {
            it has the constraint</bits/33to64>.
        }
    }

    it does {
        execute the computer converter.
    }
}
```

## Why This is the Right Solution

This gives us a simple way to specify that conversions are available and can
occur, in a way that the compiler could know about their existence during
various different phases, as necessary.

Making input/output into explicit syntax avoids the view aliasing problem.

Denying automatic chaining resolves all problems of path resolution and getting
confused about how composed converters preserve or don't preserve guarantees.

The Triggering piece is a bit hand-wavy, deferring it to the compiler. As we
learn more during implementation, we will likely come back and specify that more
clearly. There is significant danger in overspecifying it, however, as new
hardware can come out that would cause us to want to change our mind about how
conversion happens.

We also haven't said _how_ we would prevent converters from violating the
logical constraints of Define. There ideally would be some form of static check,
but at the least this provides a guarantee that the compiler can depend on, and
if somebody violates it in their implementation, that's on them. In the standard
library, it would be a law for us.

In general, right now this proposal is a bit bare-bones, intentionally. I'm
already worried that this converter design is overengineering at this point in
the lifecycle of Define. I don't want to specify too much before we have a bit
more implementation experience.

## Forward Compatibility

In general, the proposal seems to specify enough statically that we could change
this design or its syntax fairly easily.

Right now we allow inexact conversions if they follow logical guarantees. The
directions we could go in the future are allowing all inexact conversions
(dangerous and unlikely for us to do, and hard to change our minds about later)
and requiring only exact conversions. If we changed our mind about that, I
believe all that would happen is that the runtime behavior of programs would
change to be more correct but slower, and we _would_ break people's existing
converters. So that's a small one-way door here.

## Refactoring Existing Systems

As with all our other value-related proposals, this is somewhat more flexible
than most systems, outside of MLIR. Also, converters are somewhat of an
implementation detail for most programs. But for primitive casts (which would be
the primary thing we would have to proxy somehow in Define) it should be
possible to create converters for all primitive-to-primitive casts in existing
languages using this system.
