# Define Language Proposal 58: Association Rules

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** November 11, 2026
- **Date Finalized:**

## Problems

Several kinds of configuration associate one definition with another:

- [DLP 47 (Value Encoding Associations)](00047-value-encoding-associations.md)
  associates encodings with value qualities.
- [DLP 48 (Encoding Operation Associations)](00048-encoding-operation-associations.md),
  and [DLP 55 (Logical Operations)](00055-logical-operations.md), associate
  Encoding Operations with Logical Operations and Value Operations.
- [DLP 50 (Encoding Converter Associations)](00050-encoding-converter-associations.md)
  associates Encoding Converters with the encodings they convert between.

The compiler uses associations primarily to answer questions about code
generation, like "how do I actually generate code for this Value Operation?"

But what happens when one of your _dependencies_ defines one of these
associations? Do they override yours? Can adding a new dependency change how the
compiler chooses to generate _your_ code? Can adding a new dependency change how
the code of _other_ dependencies compiles?

For Define in particular, this breaks down into a few separate problems.

### 1: Universes With Different Interpretations (Coherence)

Imagine if this situation were possible:

1. Library A has an encoding called `/fast/integer/binary64`. It associates this
   with `value<standard:/number/integer>`.
2. Library B also uses `value<standard:/number/integer>`, but only knows about
   the standard library's encodings for it. Let's say the encoding that Library
   B chooses is `encoding<standard:/number/integer/ascii>`, where bytes
   represent decimal digits.
3. A program that we will call P uses both libraries. Library B does not know
   about Library A's associations, and the compiler does not enforce consistency
   between the two libraries in terms of how they interpret
   `value<standard:/number/integer>`.
4. An action in Library A sets the value of a particle to the integer 300. In
   Library A's code, the compiler uses Library A's encoding. At runtime, the
   program writes the bytes `2C 01 00 00 00 00 00 00` as the particle's value.
5. Program P moves the particle that Library A created into a position in
   Library B.
6. Library B adds 1 to that number (so logically, it represents 301, now).
7. Library B's code was generated using Library B's associations, so it executes
   the `encoding_operation<standard:/number/integer/ascii/add>`, which reads the
   bytes as ASCII digits.
8. The first byte, `2C`, is a comma, so the result is garbage or a failure at
   runtime, even though the code of both libraries was correct.

If we pass data between one universe and another, the way that data is
interpreted needs to stay consistent, even in a potential future world where we
allow separate compilation of libraries.

The reason that this situation occurs is because the compiler sometimes makes
implicit choices for the programmer. Regardless of how explicit we try to be, if
we want to make a general-purpose cross-platform programming language, we have
to separate out logical representations from concrete runtime representations.
Also, making that translation is the core of optimization, at some level
(producing the optimal physical-universe representation that meets the logical
requirements).

Thus, the key is how do we make those implicit choices in such a way that
behavior will be consistent even when we pass particles across universes?

This problem is not unique to Define---most other programming languages suffer
from _not_ solving this problem. For example, in C++, if you have multiple
definitions for the same symbol, which one actually gets executed at runtime
depends on a hard-to-understand ordering of compilation and linking. In Java, if
you have the same class defined multiple times on the classpath, the one that
happens to be earlier in the classpath "wins," in a way that is invisible and
confusing to the programmer.

### 2: Action at a Distance (Modularity)

Adding a new dependency to a project must not implicitly change how your code
compiles or how the code of other dependencies compiles.

For example, in Define, you wouldn't want some library you added to change how
every value in your program was encoded, just because you added that dependency
(maybe even just added it transitively).

Concretely, imagine if this were possible:

1. Program P adds two integers in its own code. Normally, the compiler uses
   `encoding_operation<standard:/number/integer/add>` as the runtime code for
   that addition.
2. Library C is a logging library. It has its own Encoding Operation,
   `/log/fast_add`, which adds two `encoding<standard:/number/integer>`
   integers. Library C only adds small numbers, so `/log/fast_add` is only
   correct for numbers that are less than 1,000,000.
3. Library C associates `/log/fast_add` with
   `logical_operation<standard:/number/add>`.
4. Program P adds a dependency on Library C, only so that it can write logs.
5. (Here's the problem) The compiler sees the association in Library C and makes
   it true for the whole program, not just Library C.
6. Every integer addition in Program P (and in every other library that Program
   P uses) now _could_ execute `/log/fast_add` instead of the standard library's
   addition operation. None of that code changed, and none of it uses anything
   from Library C other than logging statements.
7. Program P adds 2,000,000 and 1 and gets the wrong answer.

Once again, real languages suffer from this problem.

C and C++ can have an `#include` in a library that changes a definition for
everything that transitively includes that library's headers. The best practices
of those languages avoid this, but it's still _possible_.

Java has this "action at a distance" problem with `ServiceLoader`, which Java
uses as a way to find implementations of "plugins," more or less. Which
implementation gets loaded depends once again on classpath order. For example,
you could load a completely different JSON parser than you expect because some
library decided to specify it as satisfying the binding you're looking for.
(This is frequently encountered with Java's most popular logging facade, SLF4J,
where libraries just change your logging provider out from under you.)

### 3: Lazy Lookup

One of the overall design principles of Define is that we never have to compile
or validate code we aren't going to use---that it's structurally impossible to
ship dead code to production.

That means that somehow, when loading associations, we need some way to only
validate the values, encodings, and operations (value, encoding, and logical)
that we actually need for _this_ program that we are compiling.

This is a real problem in other languages or frameworks. For example, in Java,
Spring has to scan _every_ class on the classpath (which involves reading
through every jar file on the classpath and loading every class into the JVM) in
order to find components. When you start to have hundreds or thousands of jar
files on your classpath and tens or hundreds of thousands of classes, that
becomes a very significant cost with real-world consequences.

### 4: Extensibility

As [DLP 47 (Value Encoding Associations)](00047-value-encoding-associations.md)
notes in its Problem 1, we have this problem of "value qualities with new
encodings" and "new encodings for existing value qualities."

Both of those are _theoretically_ possible.

1. **New Encodings for Existing Value Qualities**: A library might want to
   support new hardware for existing programs.
2. **New Value Qualities Re-using Existing Encodings**: A new conceptual value
   quality that can never be intermixed with another value quality, but behind
   the scenes it uses the same encoding.

The first would allow us a useful form of extensibility to support new hardware
without requiring direct modifications of the compiler. That's a somewhat rare
need, but then again, _any_ extension to this system should be a rare need.

I'm of two minds about the second problem (new value qualities re-using existing
encodings):

It allows you to specify two value qualities that in fact have the same bits at
runtime but the compiler says they are not equivalent. That actually can be
good, if you want to enforce some sort of type safety. It also might actually be
logically true in a few cases (for example, `minute` would have different
addition semantics than `integer`). What I haven't worked through is when you
would use qualities on positions for that safety vs different value qualities,
and I'm concerned we are going to create two parallel logical systems for
accomplishing similar goals.

Having two values with identical encodings but different value qualities
requires having a Value Operation to convert between them. Of course, this will
also be the case with some built-in standard value qualities, most likely, on
some hardware. So that's not really a special, new problem. Also, if they really
are the same actual encoding, that conversion can and should be a no-op at
runtime.

The whole value quality system is intended to represent primitives and abstract
hardware operations only, not complex typing logic. That logic is supposed to be
through constraints or particle structure if it goes beyond the actual physical
representation or the actual fundamental _type_ of symbol being represented.
(Not the program's domain model of the type of symbol, either, but the
irreducible logical type of a primitive value.)

On the other hand, it's not actually fully possible to ban this behavior,
because even if we said "you can't re-use encodings from other projects,"
libraries could just cut and paste all the code related to an encoding into
their own codebase, which would actually be a _worse_ situation than allowing
them to explicitly refer to it (because then the compiler wouldn't even know, at
optimization time, that the encodings are actually identical!).

## Solution

### Background: The Rust Orphan Rule

Different languages have taken different approaches to Coherence and Modularity
that have worked better or worse over time. The primary inspiration for our
solution is Rust. Its "orphan rule" solves Modularity and Coherence elegantly
while still allowing most of what real programs need. The rule states:

> A crate may implement a trait for a type only if it defines the trait, or it
> defines the type.

If you are not familiar with Rust, this basically means that you can't give a
new behavior to a type unless you defined either the behavior or the type.

### The Association Ownership Rule

In Define, our rule is:

**A project may make an association only if the project also defines one of the
parts of that association that the compiler must use as a lookup key.**

This can be referred to as the Association Ownership Rule.

More concretely, the rules are:

| Association                                        | The project must define                                                           |
| -------------------------------------------------- | --------------------------------------------------------------------------------- |
| Value-Encoding Associations (DLP 47)               | The value quality                                                                 |
| Value Operations to Encoding Operations (DLP 48)   | The Value Operation                                                               |
| Logical Operations to Encoding Operations (DLP 55) | The Logical Operation, or an encoding that the Encoding Operation's views require |
| Encoding Converter Associations (DLP 50)           | The input encoding or the output encoding                                         |

### What This Bans

A project may not:

- Associate an encoding with another project's value quality.
- Associate an Encoding Operation with another project's Value Operation.
- Associate an Encoding Operation with another project's Logical Operation,
  unless the project making the association defines an encoding that the
  Encoding Operation's views require.
- Associate an Encoding Converter with two encodings from other projects.

All four would break Modularity and Lazy Lookup. The first would also break
Coherence (by changing how a particle's bits are interpreted across a universe
boundary).

### Pure-Association Libraries

Note in particular that our rule entirely bans libraries that simply associate
two things but define neither of them. They have no value to the language, there
is literally no reason to write them. This rule is unlikely to ever change.

### Lazy Lookup of Associations

The compiler only processes associations when code actually refers to a name
that requires association, and only when that association needs to actually be
done at compile time. It does not eagerly compile associations just because they
are listed in a configuration file.

However, for any association defined in the root project being compiled (the
project that contained the entry point) if that association is not used during
the compilation of the project, the compiler will throw an error that that
association is dead code.

Combined with the Association Ownership Rule, this solves our Lazy Lookup
problem. The way the Rule structures allowed lookups ensures that we never have
to search over all association configurations, and instead only need to look up
associations when a name from the universe that makes the association gets
referenced.

### Conflicts

Currently, this proposal guarantees coherence only because, in Define's
dependency system, it is impossible for one universe to have different
definitions within a single compile. That property would have to remain true in
the future in order for us to preserve coherence (or any future proposal that
changes that behavior would have to explain how we preserve coherence).

## A Real Program

### Adding Money

A library defines its own value quality for money, an encoding for it, and an
Encoding Operation that adds money in that encoding:

```bash
# .define/project/config.defcl
project: {
    universe_name: "mv:example.com:money"
    associations: {
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
            value: "/money"
            encoding: "/money/cents"
        },
    ]
}
```

```bash
# .define/encodings/encoding_operations.defcl
encoding_operations: {
    operation_encodings: [
        {
            logical_operation: "standard:/number/add"
            encoding_operation: "/money/cents/add"
        },
    ]
}
```

```define
define the potential value<mv:example.com:money:/money> {
    it supports the logical_operation<standard:/number/add> {
        it may be read.
        it may be written.
    }
}

define the encoding<mv:example.com:money:/money/cents>.

define the encoding_operation<mv:example.com:money:/money/cents/add> {
    define the view<a> {
        it is read.
        it may only contain particles where {
            it has the encoding</money/cents>.
        }
    }
    define the view<b> {
        it is read.
        it may only contain particles where {
            it has the encoding</money/cents>.
        }
    }
    define the view<result> {
        it is written.
        it may only contain particles where {
            it has the encoding</money/cents>.
        }
    }

    it does {
        execute the computer operation.
    }
}
```

The compiler finds `encoding</money/cents>` for `value</money>`. When a program
adds two money values, the compiler looks for an Encoding Operation that
performs `logical_operation<standard:/number/add>` on `encoding</money/cents>`.
It looks in this library, which defines the encoding, and finds
`encoding_operation</money/cents/add>`.

### Reusing Another Project's Encodings

A text library defines a value quality for Unicode code points and associates it
with two encodings from a numbers library:

```bash
# .define/project/config.defcl
project: {
    universe_name: "mv:example.com:text"
    associations: {
        has_encodings: TRUE
    }
}
```

```bash
# .define/encodings/encodings.defcl
encodings: {
    value_encodings: [
        {
            value: "/text/code_point"
            encoding: "mv:example.com:numbers:/number/integer/unsigned/32bit/big_endian"
        },
        {
            value: "/text/code_point"
            encoding: "mv:example.com:numbers:/number/integer/unsigned/32bit/little_endian"
        },
    ]
}
```

```define
define the potential value<mv:example.com:text:/text/code_point> {
    it supports the logical_operation<standard:/number/less_than> {
        it may be read.
    }
}
```

The compiler finds both encodings for `value</text/code_point>` in the text
library, which defines the value quality. When a program compares two code
points that have
`encoding<mv:example.com:numbers:/number/integer/unsigned/32bit/big_endian>`,
the compiler looks for an Encoding Operation that performs
`logical_operation<standard:/number/less_than>` on that encoding. It looks in
the numbers library, which defines the encoding. The numbers library associates
`encoding_operation<mv:example.com:numbers:/number/integer/unsigned/32bit/big_endian/less_than>`
with `logical_operation<standard:/number/less_than>`, so the compiler uses that
Encoding Operation.

## Why This is the Right Solution

This is one of the few times in Define that we have almost wholesale adopted a
concept from another language. Rust has proven out the safety and utility of the
orphan rule, so we are on pretty solid ground here.

Languages that let any library implement a behavior for any type have the
Coherence and Modularity problems above, and they are hard problems to fix once
code depends on them.

In Haskell and Swift, for example, a library can say how a type from a second
library implements a behavior from a third library. If two libraries both do
that for the same type and behavior, Haskell can use one implementation in one
part of a program and the other implementation elsewhere, and Swift does not
define which one it uses at runtime. Both languages now warn about this, but
cannot forbid it without breaking existing libraries.

### Why Logical Operations Also Allow Encodings

For most associations, the project must define the thing that the association is
keyed on: the value quality, the Value Operation, or one of the encodings that
an Encoding Converter converts between.

Logical Operations are different, mostly because their views don't assign
encodings or value qualities. Thus, how the compiler associates them to an
Encoding Operation is different. Also, we expect most Logical Operations to be
defined only in the standard library, since the compiler has to know about them.

Let's say that we said "only the universe that defines a Logical Operation may
associate an Encoding Operation with that Logical Operation." Well, that's
obviously a non-starter--it would mean only the standard library can associate
Logical Operations with Encoding Operations. Anybody who wanted to make their
own Value Operations and Encoding Operations would have a pretty hard time.

Okay. So what if we just said that anybody who defines an Encoding Operation can
associate a Logical Operation with it?

That would let any library change how every program performs a Logical
Operation. It would enable exactly the bad example in our Modularity problem
above: A logging library could define its own Encoding Operation for adding
`encoding<standard:/number/integer>` particles, which is only correct for small
numbers, and associate it with `logical_operation<standard:/number/add>`. Every
integer addition in every program that uses the logging library could then run
that Encoding Operation, even in code that never logs anything. The compiler
would also have to read the associations of every project in the program to find
out whether some library had done this, which breaks Lazy Lookup.

The _safe_ restriction is: if you define the encoding, you can associate Logical
Operations to Encoding Operations that use that encoding. This lets you define
the behavior of code _you_ wrote, without changing the behavior of code that
_other_ people wrote via action at a distance.

This is safe even if the Encoding Operation you're supporting only has a single
view that uses your encoding---only your universe could have defined that
Encoding Operation (if somebody that depends _on_ you defined it, you couldn't
have it in your associations, because your universe doesn't "know" about that
other universe; if somebody you depend on defined it, they can't have known
about your encoding).

This actually creates a _restriction_ on Logical Operations: the only things you
can associate with a Logical Operation must involve encodings _you_ define.
Value Operations actually don't have this restriction---they could be associated
with an Encoding Operation from one of your dependencies, whereas a Logical
Operation could not be.

### Allowed Extensions

Originally when I drafted
[DLP 47 (Value Encoding Associations)](00047-value-encoding-associations.md), I
allowed "my encoding, their value." However, even when writing that DLP, it had
issues when I tried to figure out how to implement it. You can see an earlier
draft of that DLP that banned it in its commit history. Once I was working on
this DLP, however, the reasoning became crystal clear: allowing "my encoding,
their value" would break Coherence and Modularity. For example:

1. A graphics library defines `encoding</gpu/float16>`, a 16-bit floating-point
   encoding that GPUs process quickly, and associates it with
   `value<standard:/number/float>`.
2. Program P depends on the graphics library only to draw charts. P also depends
   on a statistics library that sums millions of floats.
3. Every float in P, and in the statistics library, can now be encoded as
   `/gpu/float16`, although neither of them changed. A 16-bit float has about
   three decimal digits of precision, so the statistics library's sums can come
   out wrong. That breaks Modularity.
4. The statistics library's tests, compiled without the graphics library, only
   ever use the encodings that the standard library associated with it. So the
   same library encodes the same value quality differently in its tests than in
   P. That breaks Coherence.

Thus, "my encoding, their value" will likely forever stay banned.

I originally also banned "my value, their encoding." The long description of
Problem 4 explains my misgivings about it. The one I was most concerned about
was people mis-using the value system where they should be using the quality
system. However:

1. It made the Association Ownership Rule much more complex, with a weird
   exception that you had to understand.
2. I didn't actually have a concrete program that I had written that actually
   demonstrated any real problem.
3. There was no way to solve the "people could just cut and paste stuff anyway"
   problem, which was a worse outcome.

Given that it worked elegantly within the rules (it preserved Modularity and
Coherence), I decided to allow it.

## Forward Compatibility

The rule only restricts which associations may be written, so later loosening it
is possible without breaking any existing project. Tightening it later would not
be, which is why we have to decide it now, before projects other than the
standard library write associations.

The most dangerous decision is allowing "my value, their encoding," because it's
very hard to undo that (it involves cross-universe dependencies and guarantees
that would be very hard to auto-refactor our way out of).

## Refactoring Existing Systems

Every existing association follows this rule. Pre-existing programming languages
mostly do not. However, when a real program written in another language does
_not_ follow these rules, it usually is _not_ intentional on the part of the
programmer. In other words, converting to Define would expose bugs here, for the
most part.
