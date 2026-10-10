# Define Standard Library Proposal 1: Core Numeric Value Type

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** October 8, 2026
- **Date Finalized:**

## Problems

In order to have a programming language, we must be able to express computations
in the symbolic system of the computer.

Per our [concepts](../../spec/concepts.md), we assign meaning to particles.
Numbers are "meanings" we assign to particles. Although, per
[DLP 38 (Binary Values)](../../proposals/00038-binary-values.md), binary digits
are the core data type of modern computers, most of the core _operations_ a
computer performs (outside of I/O) are mathematical operations on numbers.

Thus, we must be able to express numbers as a symbolic meaning that particles
have. However, there is _enormous_ complexity in doing this the "right way," or
even knowing what the right way _is_.

This is probably the area of Define where I have spent the most time researching
existing computers and programming languages in order to determine the direction
we should go. The problems and complexities are numerous.

The first, core problem is determining what are our numeric value types. Is
there just one core type that all types "descend from?" Is there just one core
type that all types "build on top of?" Are there actually multiple core numeric
types? We have to explore very deeply into numerous aspects of language design
to even begin to answer this question.

### 1: Logical Representation of Numbers

There are numerous ways to even _define_ a number. Most languages throw their
hands in the air and decide that there is no logical representation of a number,
and they just say "however the computer behaves with your computer, that's how
numbers behave," even if they behave differently on different hardware. In other
words, you have to _run the program_ to know what the program will do. Many
compiler _backends_ use optimizations to change what the computer actually does
based on logical conclusions they can draw about mathematical operations in the
program, but those are not always logical _guarantees_ of the actual programming
language---they are coincidences of the hardware that _happen_ to allow those
optimizations.

Some languages sort of implicitly define a number through Hindley-Milner type
inference: whatever operations are performed on that data, that's the type of
number it must be.

Languages like Lean have taken a recursive approach to defining natural numbers
and used that as their core numeric primitive. This is much more mathematically
sound, and allows those languages to provide strong formal proof semantics. This
has some complexities. For example, a naive Lean compiler would have to use the
inductive definition of Nat every time it did anything with numbers. (The real
Lean compiler has an optimization for it.) But it's still stronger than
"whatever the computer does."

That said, Define is not trying to be a theorem prover, it's trying to be an
optimal programming language for writing computer programs that execute and do
work. We also need programs to be statically analyzable and compile quickly.
Dependent typing systems like Lean's are sometimes undecidable or involve
complex calculations during compilation that I believe we could do faster and
more cheaply if we didn't have to support the full proving power of something
like Lean.

### 2: Future Proofing Numbers

As soon as you _provide_ logical semantics for a number in a language, you are
_guaranteeing_ those logical semantics are what all computers that run that
program will implement, even if it's wildly inefficient to do so on that
particular computer. That's not too much of a danger for integers, which have
developed pretty standard hardware over the years, but it's a bit trickier for
fractional types like floats.

Even for integers, though, you run into complexities like size, signedness,
rounding behavior of division, the behavior of whole numbers in subtraction, or
the bit size of the result of a multiplication.

Also, we genuinely have no idea what future hardware will or won't support.

### 3: Computer Representation

Computers really want numbers to fit into registers or some particular bit size
or shape in order to compute with them efficiently. On most general-purpose CPUs
at present, that's 64 bits. However, SIMD instructions also mean that computers
really want _consistent_ formatting for those numbers, but also might accept
various different bit sizes so long as all the sizings for a SIMD instruction
are the same size (not true for all SIMD instructions or architectures, but true
for many). Plus, by _count_, most CPUs are actually 8-bit or 32-bit
microcontrollers.

Some hardware also might want to use its floating-point units to process
integers, and if you're using a 64-bit float, that gives you about 2^53 whole
integers you can represent until you lose precision.

You can choose to wave your hands in the air and just not choose a
representation, but then you end up like Python. On a typical 64-bit CPython
build, an integer consists of:

- An object header containing metadata.
- A sign and a count of how many digits are needed.
- An array of digits, each storing 30 bits of the integer.

The reality, though, is that the vast, vast majority of Python programs don't
_need_ those mechanics and could have just stored and used 64-bit integers in
hardware.

So basically, there's just a ton of complexity around the computer
representation of numbers, even integers (which seem the simplest, on their
face!).

### 4: Optimization

Closely related to the above problems, one of my goals with Define is to enable
theoretical maximum optimization capability for the compiler. There is a huge
tension here with our other goals. We want to have logically comprehensible and
intuitive behavior, but we also want to let the compiler potentially make
numbers behave _unintuitively_ if that's faster in the hardware and still
accomplishes the programmer's actual intent.

This problem comes up most often with floating-point numbers, but there are
considerations here for integers and rational numbers in general, too.

The most common optimization question is "what's the lowest clock-cycle set of
operations that I could execute that would accomplish the programmer's intent?"
Of course, to do that, you have to know the programmer's intent, and you have to
know a fair bit about the hardware. It's also not quite that simple because the
hardware architectures of CPUs can mean that _when_ you execute an instruction
makes a significant difference. Still, that question is a fine logical place to
_start_.

The simple problem here, though, is understanding the programmer's intent
clearly enough that you know the maximum possible optimization available.

### 5: Real vs Rational vs Integer vs Natural

Programs have various ways to choose to logically represent numbers. Some
programming languages and proof assistants have chosen Real as their core
numeric type. This puts them into a weird place with irrational numbers, because
it means:

1. If they are a verified language, the compiler must implement the algorithms
   necessary to verify an irrational number (which sometimes amounts to theorem
   proving across an algebraic equation possibly spread across many functions)
2. The real computer implementation of irrational numbers isn't really the
   (unrepresentable) irrational number---it's some precision level of that
   number, instead, which means the verifier is "lying" to the programmer to
   some degree.

If you choose Rational as your type, then you end up basically needing a concept
of a numerator and a denominator. But what type are the numerator and
denominator themselves? Also, one of the dangers of _providing_ Rational as a
type is that a naive programmer might not realize that strict rationals can be
very expensive in hardware and in the compiler (doing fixed-point math or
accumulating numerators and denominators and then sometimes reducing them).

That leaves you with Integer and Natural as the next potential options to look
at for core numerics. You could choose to represent all numbers as integers, and
just say "natural numbers are integers of 0 or greater." Or you could choose to
represent integers as natural numbers with a magnitude and a sign.

If you just have natural numbers, though, what happens when you subtract one
from the other and the result is less than 0?

### 6: Logical Constraints

Define intends to be a pragmatically verified language. In order to do this, it
must be able to express logical propositions about the symbols assigned to
particles. In the case of numbers, it means we need to be able to make
assertions about those numbers and the results of operations on them having
certain properties, such as being within a certain range, comparing two or more
numbers, numbers being equal to each other, numbers being one in a set, and
possibly others.

Our calculations that we assert logically in the compiler need to be guaranteed
as the actual semantics of what occurs in the computer, while still allowing for
maximum optimization capability by the compiler.

We also have to be able to reason through what sort of logical constraints are
available for a certain type of number, which means we have to understand the
logical semantics of that number type.

### 7: Convenience vs Explicitness

How painfully detailed do we want the programmer to be? Do we want to have the
compiler just "figure out" what the best concrete type is for a particular
number type, or do we want to make them specify every detail of the numeric type
down to the smallest detail? Some of the trade-off here is: if we require the
programmer to be very explicit, they might be more explicit than they actually
_need_ to be, thus preventing optimizations that the compiler actually _should_
be able to do.

For example, let's say we specify somehow that it has to be an exactly 32-bit
integer. What if there's some hardware somewhere that would calculate it much
faster as a 16-bit integer, and all the values actually fit into a 16-bit
integer?

There are lots of trade-offs in explicitness, there's some fine detail in
getting it right.

### 8: Conversion Costs

There are real hardware costs to translating between bit shapes of numbers. Some
transitions are free or nearly free, like translating an int32 to int64 (it just
gets sign-extended and is essentially free in most hardware). However,
translating a uint64 to an int64 or vice versa involves bounds checking, at the
least. And translating from any integer type to any float type involves real
calculations (for example, translating an integer over 2^53 into a float64
requires losing precision).

So how both the programmer and the compiler choose to represent numbers has real
hardware costs if the bit form keeps flapping back and forth throughout a
program. In other words, ideally you don't keep re-encoding a value type over
and over, but instead keep it stable. However, there are boundaries in a program
where a program _does_ need to do the bit conversion. You want this conversion
done minimally, but you also want to optimize the overall time and memory of the
program, meaning that sometimes you need to convert in order to actually have an
optimal program.

How you define your numeric types can have a strong influence on how often
conversions happen. It also potentially gives the programmer a footgun of being
too explicit and thus either having to implement conversions themselves or the
compiler having to do too much of it in the backend.

### 9: Single Numeric Type vs Multiple Numeric Types

One of the things I went back and forth on the most is whether there should be a
single `value</number>` type or if we should have separate types like
`value</number/integer>`, `value</number/float>`, and so forth.

One of the biggest reasons I debated back and forth on this was that I think
most programs don't care about the specific implementation of their numeric
values, as long as it's optimal. Most programs actually aren't primarily about
doing math. (They are primarily about communicating something between people or
between people and a computer.) My reasoning behind Number was that it would
allow the compiler to determine the best representation all the time, taking
away the optimization burden from the programmer.

The complexity behind Number was: how does it actually behave? What happens when
it is fractional, does it use slow rational math or fast floating-point math? Do
we track error bounds for it for floating-point math, or do we track (and
specify constraints on) the denominator?

### 10: Defining the Types and Constraints Themselves

Let's say we did have a Rational type. Then what type are its numerator and
denominator? A circular definition of a rational with denominator 1? What type
is _that_ Rational's denominator? This problem appeared everywhere in number
design. If we wanted to have floating point numbers, what numeric type was the
exponent? When I specify a constraint on the numerator of a rational, what
number type does that constraint use?

## Solution

The core numeric type of the Define Standard Library is
`value</number/natural>`, representing the natural numbers starting from 0. This
represents one of the two core _real_ (meaning it has concrete reality in the
universe, not just symbolic representation) numeric values of all universes:
quantity.

All other numeric types can be defined in terms of natural numbers. We will also
have a `value</number/integer>` and `value</number/rational>` for exact math
that build on this definition of `value</number/natural>`.

Natural numbers will have their own value operations that make it very clear
what the behavior is for those operations. For example, subtraction will have
different operations for "saturate to zero" vs "result in a negative integer."

The compiler will implement natural numbers and their operations. The general
expectation is that the _logical_ behavior of natural numbers on all hardware is
essentially the same, given that they are the simplest and most basic quantity
type. (There would be some slight exceptions for hardware that primarily does
floating-point math, although mostly only on degree of precision.)

Note that in general, in order to be able to optimize safely across hardware
platforms, we should consider limiting natural numbers to no greater than
`2^63 - 1` in many circumstances. (This allows us to use signed integer behavior
in the backend on architectures where signed operations are faster than unsigned
operations.)

## A Real Program

### Operations

```define
define the operation<standard:/number/natural/subtract> {
    define the view<a> {
        it is read.
        it may only contain particles where {
            it has the value</number/natural>.
        }
    }
    define the view<b> {
        it is read.
        it may only contain particles where {
            it has the value</number/natural>.
        }
    }
    define the view<result> {
        it is written.
        it may only contain particles where {
            it has the value</number/integer>.
        }
    }

    it does {
        execute the encoding operation.
    }
}
```

`standard:/number/natural/add` and
`standard:/number/natural/subtract_saturating` have the same views, except that
their `result` view has the value `/number/natural`.

### Parking Garage Counter

A parking garage counts the cars that enter and leave each hour.

In this program, `/garage/parked` has the value `standard:/number/natural` and
`/garage/net_change` has the value `standard:/number/integer`.

```define
define the potential action<define-lang.org:parking:/garage/record_hour> {
    it also assigns the position</garage/parked>.
    it also assigns the position</garage/net_change>.

    define the position<run>.
    define the position<arrivals> {
        it may only contain particles where {
            it has the value<standard:/number/natural>.
        }
    }
    define the position<departures> {
        it may only contain particles where {
            it has the value<standard:/number/natural>.
        }
    }

    it happens when {
        the position<run> has a particle.
    } and it does {
        define the position<parked_with_arrivals> {
            it may only contain particles where {
                it has the value<standard:/number/natural>.
            }
        }
        create a particle in position<parked_with_arrivals>.
        execute the operation<standard:/number/natural/add> {
            with view<a> looking at position</garage/parked>.
            with view<b> looking at position<arrivals>.
            with view<result> looking at position<parked_with_arrivals>.
        }

        # The sensors sometimes miss a car entering, so departures can exceed
        # the cars we counted. The garage can never hold fewer than zero cars.
        execute the operation<standard:/number/natural/subtract_saturating> {
            with view<a> looking at position<parked_with_arrivals>.
            with view<b> looking at position<departures>.
            with view<result> looking at position</garage/parked>.
        }

        # The net change for the hour is negative when more cars left than
        # arrived.
        execute the operation<standard:/number/natural/subtract> {
            with view<a> looking at position<arrivals>.
            with view<b> looking at position<departures>.
            with view<result> looking at position</garage/net_change>.
        }

        destroy the particle in position<run>.
    }
}
```

## Why This is the Right Solution

The real final decider was "if I have any other type, how do I define its
components?" Like if I have a Rational number, how do I define its numerator and
denominator? If I have imaginary numbers, how do I define the real and imaginary
components? There was no other way to do that other than by having natural
numbers be the core type, which don't require any other definition.

For optimization, this provides us at the very least the simplest possible
foundation on which to build other things. It does theoretically allow a bit of
a footgun ("oops I made this a natural when really these 100 other actions need
it as a float") but my hope is that the Define compiler's superior ability to
optimize and infer will allow us to optimize correctly anyway (at least
eventually).

In general, my present belief is that choosing explicitness will actually
provide us more optimization opportunities, especially when combined with
Define's value constraint system.

In terms of future-proofing, natural numbers seem like the easiest to
future-proof. Their behavior has not changed in hardware in a very long time,
and when it has, it's mostly been around SIMD or bit sizes, not in fundamental
logical behavior. For the areas where logical behavior is a bit trickier, we
will just make the programmer be explicit about their intent for the operation
(rounding behavior for division, subtraction behavior for naturals, etc.).

### Why Not Signed Integers?

The one other possibility for a core type was signed integers. My primary wonder
there was about efficiency: was there any situation in which making signed
integers the core type would make our programs more efficient at runtime?

There are some cases. For example:

- x86 chips without AVX-512 pay one or two extra single-cycle instructions for
  some unsigned operations. That includes nearly all Intel consumer chips (only
  some consumer chips from 2019 to 2021 had AVX-512) and AMD chips before Zen 4
  (2022). The affected operations are:
  - Scalar conversion between uint64 and double. `cvtsi2sd` converts a signed
    integer in one instruction, but the unsigned version (`vcvtusi2sd`) only
    arrived with AVX-512F, first on Intel's Knights Landing (Xeon Phi) in 2016.
  - Strict SIMD compares (`<`, `>`) on 8-, 16- and 32-bit lanes, since x86 SSE
    and AVX2 have no unsigned compare instructions.
  - All ordered SIMD compares (`<`, `<=`, `>` and `>=`) on 64-bit lanes, since
    there is also no unsigned 64-bit min/max before AVX-512.
- The JVM has no unsigned types (though often can compile down to unsigned
  operations anyway).

Most of those issues rarely matter in practice (the clock cycles required for
the instructions don't overcome the load/store costs involved) but they do
exist.

The difficult _logical_ problem was subtraction, solved by us having separate
operations for saturating subtraction and subtraction that can go negative.

There's also a minor conceptual issue that signed integers have a sign and a
magnitude, which sometimes you might care about separately, and the magnitude is
always a natural number. We could have solved that with constraints (just saying
that it's an integer that's 0 or greater) but it would have involved integers
having a self-referential definition if we went with that way of defining them.

I also went with natural numbers because they are _conceptually_ the
simplest---they represent real quantities of particles, one of the two real
values in a universe (the other one being distance).

## Forward Compatibility

Natural numbers, given that they are (a) a man-made numeric construct while also
being (b) a fundamental reality of the universe (quantity) seem _highly_
unlikely to have any _logical_ changes in their behavior in the future. Hardware
support for natural numbers (unsigned integers) has had consistent _logical_
behavior since the start of binary computing until now, other than details about
overflow, rounding, etc. which Define intends to make explicit.

## Refactoring Existing Systems

Having explicit natural numbers would make it hard to translate from other
languages that don't specify explicit numeric types, like Python. However, the
reality in most programs written in those languages is that there _are_
constraints on the numbers, you just can't see them in the language. So it's
still _possible_ to translate most of those programs, it's just harder.

Languages that already have unsigned integers or `Nat` should be very simple to
translate into Define.
