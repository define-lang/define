# Define Language Proposal X: Value Types

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** April 12, 2026
- **Date Finalized:**

## Problems

In [DLP 38 (Binary Values)](00038-binary-values.md) we decided that all values
are essentially binary data. However, this leaves us with a few problems.

1. How do we interpret that binary data? Is it an unsigned big-endian integer?
   Is it an IEEE 754 floating-point number? Is it a UTF-8 unicode code point?
   All programming languages in existence today have to deal with the fact that
   the number 97 sometimes means the letter "A," sometimes means the abstract
   concept of the decimal number 97, sometimes means a byte-width unsigned
   integer in the hardware, sometimes means a special code for which fruit the
   user has purchased, sometimes means the number of cents in a price, and so on
   and so forth.
2. How do we allow programmers to take valid actions on that binary data and
   deny invalid actions? (For example, allow lexicographic comparison of UTF8
   characters but deny performing addition with them.)

It is actually very hard to logically separate those two problems, because what
you start to realize when reasoning through solutions is that the reason that we
_have_ encodings is so that programmers can take _action_ with them.

### 1: Encodings

There is a real physical problem that we have to solve: not all binary data is
interpreted the same way. There's byte orders, number encoding methods,
non-numeric data, bit packing, and any other thing you can imagine encoding as a
series of binary bits.

Different chips and hardware even use different encodings for the same things,
often for good reasons. CPUs have a good reason to put bits in a particular
order (processing efficiency in circuits) while network cards may have a good
reason to use another order (reading the header bits of a network packet first
before the data).

### 2: Cross-Platform Portability

In general, programmers want to write a program once and have it work across all
sorts of different hardware. When you only expose the hardware mechanisms
directly to the programmer (which is what C does, more or less) then they have
to understand each different piece of hardware they are writing a program for
and write slightly different programs for each different piece of hardware. The
real-world result of this is that programs written in low-level languages
historically were not very portable. This hindered hardware advancement, added
great expense to companies _trying_ to support multiple pieces of hardware, and
is the source of untold bugs in cross-platform software.

### 3: Types and Limiting Operations

If you have a 97 that is supposed to be a number, you don't want to allow adding
the letter "A" to it, because that would be a mistake (it doesn't make sense).
If you know it's the letter "A" then (1) you usually don't care, logically, that
it's actually the number 97 (any implementation would be fine as long as it gets
you the result you intend) (2) you only want to allow operations on it that make
sense for letters.

Most languages solve this via a system of types, whereby you say that "this
binary data represents a letter," and then you constrain every operation in the
entire program by saying what operations can occur on what types. (Or in some
languages, what _happens_ when an operation is executed on certain types, like
in languages that allow you to append numbers to strings by using `+`.)

If we break this down, then very basically, the minimum question a dimension
point needs to be able to answer is: **"What operations am I meaningful input
for?"** This further breaks down into two separate questions:

1. What operations _can_ operate on this data?
2. What operations _should_ operate on this data?

For example, I _can_ add `NumberOfApples` and `NumberOfOranges`. They are both
small integers. But in most situations, I _shouldn't_ add those numbers
together, unless I'm trying to calculate "total number of fruits," and ideally
the structure of the program would prevent me from doing so unless I really
wanted to and expressed clear intent that I knew I was violating the type
barrier intentionally.

The compiler, however, should clearly tell me that I _can't_ multiply the letter
"a" by the number 10. That shouldn't even be an option.

So another way of looking at this is: "integer" isn't just a thing that data
**is**. It's also a set of things you **can do** with data. Without those
actions, "an integer" is meaningless; it's just some binary bits that you're
moving from one place to another (a totally valid thing for a program to do, but
not its most common need).

### 4: Type Relationships

Type systems have numerous challenges. Once you have types, you must describe
how they can be related to each other. Early languages started off by hardcoding
these rules---integers and floats can interact, but only in the ways the
compiler knows about. Characters are integers, but specifically ASCII (or UTF-8)
coded ones only, so you can interact with them like integers. Boolean values had
a value of 0 or 1 (often very confusing when you set some integer to 0 by
default and then it was able to be used as a boolean value, or when you
accidentally added boolean values together instead of just checking them or
flipping them like bits).

Later on, languages allowed types to have "is a" relationships to each other. A
letter is an integer, an integer is a number, and a float is also a number. This
works great until you have a problem like: what if I want letters that are not
represented by integers, but by something else, but I still want them to behave
exactly like letters are guaranteed to behave? This gave us various
compositional models and dependency injection in an attempt to solve the "what
if sometimes this has some different implementation" problem.

### 5: Implementation Hiding / Showing

Most of the time, the programmer shouldn't have to understand how the CPU does
twos compliment math to know that they can add two integers together. The
programmer shouldn't care what's going on to upgrade a 32-bit signed integer so
that it can be added to a 64-bit integer.

In fact (see our cross-platform problem above) most of the time, the programmer
probably doesn't even care how many bits are in an integer. (Making them care
has led to untold maintenance issues when the world transitioned from 16-bit to
32-bit, and then again when it transitioned from 32-bit to 64-bit, to the point
that even decades after the introduction of 64-bit CPUs, some programs have
never been successfully ported from their 32-bit implementations.) Usually, they
just care that there's an integer and they're going to do some math with it or
store it somewhere, and they want the compiler / runtime to handle how that
actually happens, especially when performance isn't critical for that
application.

All that said, sometimes programmers really _do_ need to know the exact
implementation of everything they're doing. If you're writing code where the
exact timing of everything matters (some hardware requires this), low-level
kernel activities, extreme high-performance code, drivers that translate network
bytes into CPU bytes, etc. you really _want_ to be able to dig into those
details.

Traditionally, this trade off has literally required choosing a _different
programming language_ for each different use case, because you could not get
sufficient abstraction of implementation details _and_ the ability to reach into
the specifics for performance reasons. Also, even in languages where you _could_
do both (like C++) it was sometimes hard to know whether all of your
dependencies were just as performant as your application code needed to be,
because you didn't know if the dependency had chosen the slow abstract path or
the fast specific path for any given task.

To my knowledge, Rust is the language that has done the best here. Nearly all of
its abstractions incur no cost at runtime, and the language lets you dig deep
into the details if you really need to.

### 6: Assignment Protection

A special type of operation is assigning a value to a variable (or in Define, to
a dimension point). One of the key protections that a programming language
usually needs is the ability to say "you can't assign this letter to this
variable that only accepts 64-bit integers," even though they are both
binary-encoded data. Without this protection, it becomes very hard to track down
bugs in the program and implement clear contracts between components.

### 7: Implementation Overrides / Re-Use

Imagine I have this requirement: I have a special type of integer that prints
out differently when you convert it to a string, but otherwise it behaves
identically to how integers normally do. I need this to happen everywhere that
converts integers into strings, without having to modify the code in those parts
of the program. Also, I need every part of the program that currently accepts
integers to accept my new Magic Integer.

In essence, what this means is "I need to be able to define some sort of data
type where the operations behave differently but where the rest of the program
stil understands the _contract_ the data type exposes and my data type still
meets the expected contract."

### 8: Runtime Efficiency and Magical Behavior

One of the downsides of many attempts at type systems is that they enforce
inefficient behavior at _runtime_ for the program. For example, in some
languages, I the programmer may know that my string represents both a
`PersonName` and a `LockerOwnerName`, but I am forced to actually _copy_ the
entire string in memory just to assign the `PersonName` to the
`LockerOwnerName`. (Yes, there are efficiencies that compilers attempt to do
there, but there are still many situations in which you must do something
inefficient in order to comply with the type system. I've run into it frequently
myself when building the Define compiler, such as having to copy strings out of
the source code instead of just referring to that section of the source.)

Polymorphism in Java and most other languages translates into vtable lookups
that must actually happen at runtime, even though the polymorphism exists mostly
as a convenience to the _programmer_. This translation is magical and invisible
to the programmer---a convenience, but one that incurs a runtime cost that very
few object-oriented programmers know about.

One of the great advantages of Rust is that it enables zero-cost abstractions.
However, even in Rust there is _magic_ that is happening sometimes at runtime
that the programmer might not realize. For example, most casts in Rust are
invisible actions that happen just in the compiler. _However_, if you do
something like `my_int as f64` (casting an int to a 64-bit floating-point
number) at runtime the program _must_ actually shift a bunch of bits in order to
convert the encoding of the binary data from a 64-bit integer into the
completely different encoding of a floating-point number. (Yes, sometimes the
compiler can avoid actual bit conversions that happen in the CPU, and sometimes
this is free in the CPU, but it's still a bit of magic that hides behavior.)
This is some pretty benign magic, but I personally had not thought about the
fact that this was happening until I was researching for this proposal.

## Solution

The Values section of the [Concepts](../spec/concepts.md) (which I actually
mostly wrote _after_ writing out the Problems above) provides a framework that I
believe successfully solves all of the problems above. We simply need to
describe what our concrete implementation of those concepts will be in Define.
In brief:

1. **Concept** of a Value: You can assign qualities like
   `value<standard:/number/integer>` or `value<standard:/number/natural>` to a
   dimension point. These behave according to the rules of mathematics, as far
   as Define is concerned, unless their type definition indicates otherwise.
2. **Representation** of a Value: The actual implementation of a value is
   dictated by an _encoding_, which is also a quality you can assign to a value.
   Often the encoding is inferred by the compiler, except at the boundaries of a
   program where the encoding type is enforced by something external and must be
   specified explicitly. This is a quality you can assign like
   `encoding<standard:/integer/unsigned/cpu/64bit>` or
   `encoding<standard:/integer/twos_complement/32bit>` or various other things
   with more or less specificity.
3. **Intentions** about a Value: These are operations that you can execute. We
   define `potential operations` on `value` types, which get concrete
   `operation` types in `encoding` types. That is, values define the _contract_
   and _name_ of the operation, and encodings specify the _implementaion_ of the
   operation. Operations are named like `operation<standard:/integer/add>` and
   are a property of the value type assigned to a dimension point.
4. **Translations** between representations: These are mechanisms to translate
   between representations, even translations like "a string of ASCII digits" to
   "binary 64-bit int." Encodings can specify what they can convert _to_ and
   _from_ using a special name type `converter`. Define's circular name
   reference controls prevent developers from writing the same converter twice
   (a converter in the "32-bit int" encoding to convert to 64 bits, and a
   converter in the "64-bit int" encoding to convert _from_ 32 bits would cause
   a circular reference error between those encodings).

This should give Define more power, abstraction, _and_ explicit control over
computer behavior (when desired) than any other programming language I know of.
It lets the compiler designers create a very powerful system that allows for
deep optimization while still allowing programmers to create their own types of
values, encodings, operations on those values, along with full translations from
and to any other encoding the programmer needs to interact with.

It even allows (in the compiler frontend, at least) programmers to create custom
operations for obscure hardware that can still be plugged into Define's
fully-verified system.

Values will have relationships to other values, encodings will have
relationships to values, and operations will have relationships to both values
and encodings. Converters are properties of encodings.

The full details of this system will require separate proposals for each
component, as each deserves a very deep dive into its reasoning and
construction.

## A Real Program

## Why This is the Right Solution

## Forward Compatibility

## Refactoring Existing Systems
