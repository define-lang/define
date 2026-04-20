# Define Language Proposal 39: Value Types

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** April 19, 2026
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

Later on, mainstream languages allowed types to have "is a" relationships to
each other. A letter is an integer, an integer is a number, and a float is also
a number. This works great until you have a problem like: what if I want letters
that are not represented by integers, but by something else, but I still want
them to behave exactly like letters are guaranteed to behave? This gave us
various compositional models and dependency injection in an attempt to solve the
"what if sometimes this has some different implementation" problem.

### 5: Implementation Hiding / Showing

Most of the time, the programmer shouldn't have to understand how the CPU does
twos complement math to know that they can add two integers together. The
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
still understands the _contract_ the data type exposes and my data type still
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
   and _name_ of the operation, and encodings specify the _implementation_ of
   the operation. Operations are named like `operation<standard:/integer/add>`
   and are a property of the value type assigned to a dimension point. While
   actions are "physical" machines in our universe that operate on dimension
   points, operations are _symbolic_ machines. they operate entirely on values,
   not on positions.
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

```define
# Logically defined as an arbitrary-precision signed integer. Limiting
# it to ranges of integers would be done by constraints.
define the potential value<standard:/number/integer>.

# Logically defined as a checked add where the compiler will ensure
# that overflow is impossible before running it. There would be separate
# saturating and wrapping adds.
define the operation<standard:/number/integer/add> {
    define the argument<a> {
        it has the value<standard:/number/integer>.
    }
    define the argument<b> {
        it has the value<standard:/number/integer>.
    }
    define the argument<sum> {
        it has the value<standard:/number/integer>.
    }
    it does {
        set argument<sum>::value<standard:/number/integer> by the computer.
    }
}

# Somewhere inside of an Action Statements Block
execute the operation<standard:/number/integer/add> {
    with argument<a> set to position<augend>::value<standard:/number/integer>.
    with argument<b> set to position<addend>::value<standard:/number/integer>.
    with argument<sum> set to position<result>::value<standard:/number/integer>.
}

# Defined as whatever binary encoding the target CPU uses.
define the encoding<standard:/number/integer/cpu/32bit/signed> {
    this dimension point must have the value<standard:/number/integer>.
    # Imaginary syntax for quality-requiring a constraint.
    this dimension point must have the constraint<standard:/number/integer/32bit>.

    define the converter to encoding<standard:/number/integer/cpu/32bit/unsigned> {
        it is implemented by the compiler.
    }
    define the converter to encoding<standard:/number/integer/cpu/64bit/signed> {
        it is implemented by the compiler.
    }
    define the converter to encoding<standard:/number/float/cpu/64bit> {
        it is implemented by the compiler.
    }
    define the converter to encoding<standard:/number/integer/cpu/16bit> {
        # Imaginary syntax, at this point.
        require that {
            # This perhaps will end up using operation syntax when we actually
            # implement it, not sure yet.
            the value<standard:/number/integer> is less than number<2^15>.
            AND
            the value<standard:/number/integer> is greater than number<-2^15>.
        }
        it is implemented by the compiler.
    }
}
```

## Why This is the Right Solution

Okay, so let's do a bit of a deep dive into type systems.

### The Infinite Complexity of Categorization

There are an infinite number of ways of categorizing data, all of which are
essentially based on the opinion of the viewer as to how they want to categorize
data. In other words, there are actually an infinite number of potential
_problems_ you might have to solve with a categorization system that have an
even larger infinity of potential solutions.

Even if you could come up with a single system that could categorize all data,
you'd then have to be able to explain how all of those _categories_ relate to
each other, which could also have an infinite variety. In essence, "all the ways
of categorizing all data" is almost certainly equivalent to "all possible
universes that could exist." In order to describe them all, you'd need a whole
programming language that could describe all universes. What would the type
system be for _that_ language? Seems hard to solve.

(Side note: it would also be impossible to do in Define, because in order to
describe all universes, you must be able to describe _unpredictable_ universes,
and we can't allow a type system inside of Define that is undecidable because
Define has to be decidable).

Thus, we somehow must have a constrained categorization system that can yet
express all possible programs in a way that logically represents the universe
that the programmer is trying to express. We also must be able to compile this
categorization system in reasonable time, and its behavior must be fully
predictable (deterministic) for the programmer.

The way that we get there is by understanding the _purpose_ for which we are
trying to build a type system.

### Logical Foundations of Type Systems

First, let's start with the existing theory behind type systems, which tells us
a lot about the problems that type systems need to solve.

For most of the history of computer programming, programming languages have not
had very strong theories behind their type systems. Designers would have a set
of logical principles about how data ought to relate to other data. They would
then empirically demonstrate what it could accomplish by using their system in
actual computer programs. There was no overall higher-level "science" of type
systems they were using that would tell them concretely what trade-offs they
were making with a type system, how to think about type systems in general, etc.

This has been true for most type systems in most mainstream object-oriented
languages, such as the "is a" relationship between classes in languages like
Java. While there _were_ some mathematical theories behind all these systems,
and they are pretty good at handling most problems, anybody who's used them for
long enough has discovered some pretty rough edges where it gets pretty
confusing to model concepts successfully in a way that actually represents the
universe you want to design and gives you all the safety that you want from the
type system.

That said, there are some sounder theories of type systems that have more
compelling logical proofs of covering every type of logic you would need to
write in a program. In particular, the most mathematically-grounded type systems
that I am aware of are based on these principles:

1. The [Lambda Calculus](https://gemini.google.com/share/5e3e8b16adc2).
2. The
   [Curry-Howard Correspondence](https://gemini.google.com/share/f3ad4a72b96f)
   (CHC)

These two principles have allowed functional programming languages to go much
further with formal verification and type safety than most traditional
object-oriented languages. Some version of these two principles are what make
functional languages "feel" more correct to programmers who use them.

There are only a few languages that _fully_ implement CHC (using
[Dependent Type Theory](https://gemini.google.com/share/af2ee26bbca8)): mostly
languages designed for full formal verification like Rocq or Lean. Why is that?

### The Difficulties of Implementing the Curry-Howard Correspondence

The traditional difficulties of implementing the full power of CHC in a
programming language have been:

1. It requires proofs of termination. Forcing a developer to prove that their
   complex web server or UI loop terminates is a hurdle that most languages
   aren't willing to impose on developers.
2. To get the full power of CHC, it requires you to write a whole other language
   (type expressions) inside of the language you're writing. This can be tedious
   and complex.
3. It makes programs "look like" math instead of a description of the universe
   you are trying to simulate. This maps very naturally onto problems that can
   be reasoned through as mathematical propositions, and is fantastic for
   mathematicians looking to prove theorems. However (and I'll touch on this a
   bit more later) most computer programs don't logically map onto being math
   functions and so it requires a bit of mental contortion to think through them
   that way. (I'm sure one could argue the same about Define's spatial model of
   programming. My present belief is that it will be more natural for developers
   than functional programming is, because it will naturally map to the way
   universes work, and because it allows you to model the world logically in
   either functional or object-oriented ways, as you wish. I am sure it will
   still be a hurdle for developers trained in traditional languages, though.)
4. Actually implementing _full_ CHC can be very computationally expensive as the
   compiler works through the proofs. In reality, checking CHC on _most_
   programs is pretty fast, but only because those languages force you to
   manually write out parts of proofs that the compiler _should_ be able to
   derive but can't because of the computational complexity of deriving them.
5. It forces you to include every possible error state bundled into the _type_.
   This is especially relevant for I/O, where a program interacts with the
   outside world and the outside world could misbehave. This creates strong
   guarantees about error handling, but it overlays that concept into the single
   concept of a type, which can be difficult for programmers to reason about,
   sometimes (depending on the implementation).
6. It makes it a little weird to reason about the state of external components
   that have complex, changing state. For example, is a terminal with the words
   "Hello World" on it a different "type" than a terminal with the word
   "Welcome" on it? Does that mean that the function `print("Hello world")`
   returns a different type than `print("Welcome")`?

Thus, most languages pick out parts of CHC and only implement the parts that
programmers need most that can be expressed with simpler logic.

One could definitely argue that some of these problems are more or less
important. There are many programmers in the world who love Lean. I fully
support that. I think it's a super cool language. I don't know that Define will
ever be a better theorem prover than Lean, Rocq, or others that exist. What I do
think is there are solutions that would solve the above problems in a way that's
more intuitive (and potentially more powerful and performant) for programmers
than how it has worked in those other languages.

In essence, my belief is that CHC is a fundamentally sound theory that has not
been implemented in a way that solves all of the above problems well, in most
languages.

### Mistakes in Implementing the Curry-Howard Correspondence

The Curry-Howard Correspondence is a beautiful piece of logic that is super
valuable to the designers of type systems. The biggest problem that I have with
it, from the perspective of designing a language, is that it bundles everything
you need for formal verification into the single concept of a "type." This is
mathematically elegant, but actually makes it harder for programmers to reason
about how to fit various different categories of assertions into a single
system. For example, assertions about nullness, allowed ranges of values,
encoding of values, allowed mathematical operations on values, potential error
states, etc. all become part of one single concept: a type.

I believe this issue comes from to a more fundamental error that language
designers have made, which is that they have logically assumed that _everything_
in the program is a symbol (the meaning attached to a dimension point, not the
dimension point itself). Values are symbols, variable names are symbols,
functions are symbols, often even types and raw operations (like addition) are
symbols themselves. While it's true that the code we write is a representation
of other things, I believe it is a mistake to equate all symbols in a program as
all being "just symbols" that are all the same kind of thing.

### The Difference in Define

One of the most fundamental differences in Define compared to other languages is
the recognition that there are actually
[multiple separate universes](../spec/concepts.md) involved with any single
program. At the least, these are: the universe of the program, the universe of
reflection, and the universe of the physical computer. In other words, the
symbols we write in a language often represent _fundamentally different things_.
Sometimes these things have relationships to each other, but you can understand
the specific relationship they have. Dimension points in the program's universe
have meanings (values). Those meanings represent something in the physical
universe---in particular, on the computer. What is happening physically on the
computer and what is happening logically in the program's universe are not
actually the same thing, from the perspective of language design.

This brought the most important insight to solving the type problem: that the
real core problem we need to solve _first_ is the correspondence between the
logical values in the program and the physical values on the machine. This is
actually a problem that all programming languages _must_ solve, and which they
usually actually hide entirely inside of the compiler, declaring only fixed
concepts like `int64` for a built-in integer type and `+` for the built-in
concept of addition.

While ultimately some part of those problems must be solved inside of the
compiler (or in the interpreter, for interpreted languages) they actually
represent perhaps the core problem of type systems: the need to translate
logical values into concrete encodings and take concrete operations on them on
real hardware. This is the one categorization that a language _must_ perform, so
that should be our starting point.

We may need to solve this for aspects of Define beyond just values in the
future, but starting with values gives us the foundation we need in order to
progress logically forward from here.

### Values and Operations as Communication

The other breakthrough was realizing that symbols are actually used as a form of
_communication_ to the computer.

The core idea that symbols are messages is not new. It is one of the core
principles of languages like Smalltalk and Elixir.

What is perhaps new is the idea that the actual interaction between the
program's universe and the computer's universe is communication.

### Curry-Howard in Define

My belief is that we will, eventually, get most of the power of CHC in Define
without the logical-reasoning complexity, the need to think of your program as
math, or the need to write out explicit proofs of things that are obvious from
the structure of the program. It will come from multiple different components of
the system rather than encoding everything into a single type system. I believe
it will also get us more compositional flexibility than a traditional CHC
system, because you will be able to encode constraints inside of qualities and
then assign those qualities however you wish.

We will never have the _full_ power of CHC, because it relies on higher-order
logic (essentially, the idea that you can have logical propositions that are
_about_ other logical propositions, or in the case of a programming language,
types that are about things in the program itself like "a type that represents a
function") which, as I've worked it out so far, would get us into situations
where static analysis of the program become very difficult, implemnetation of
the compiler becomes complex, compile performance becomes harder to manage, etc.

All that said, I haven't finished designing the language yet, so who knows. We
have found our way around a lot of other problems so far, maybe we will find a
way around this one.

### Hindley-Milner Type Inference

There is another very powerful way of doing typing in programming languages that
deserves a mention here, which is
[Hindley-Milner Type Inference](https://gemini.google.com/share/64dfe6e1a24e)
(HM). This is a very clever algorithm that allows a compiler to _infer_ the type
of every variable in the program without the developer ever having to explicitly
note the type of anything. It figures it out from the operations that are
performed, which makes a lot of sense based on the Problems that we laid out in
this proposal (noting that it's really operations that determine when a type
matters).

It's super cool, but it does hit a wall in some common situations that require
you to then write explicit types on _some_ variables. For example, if you want
API guarantees on a library that you're shipping, you _should_ (but don't have
to) specify explicit types. If you had a type that was a list that took either
integers or strings, you would have to specify that (because HM would otherwise
see two different inputs into the same list and say "you can't do that"). That
would violate our "there is only one way to do it" rule in Define. It creates
logical inconsistency in how programs are written, what best practices are
("when should I add types?"), and what is "safe" and verifiable behavior.

It also often makes code harder to read---you can't figure out what a variable
_is_ as a reader, you can only see what gets _done_ to it. You have to do the
same mental inference that the compiler is doing. That is okay in a lot of
circumstances, and less okay in others. Sometimes it actually is a pretty good
trade-off, because the compiler enforces safety based on what you _do_, and you
don't have to think about it.

HM can also produce confusing error messages. The compiler could point to line
500 of a function and say something incredibly cryptic, like: "Cannot unify Type
X with Type Y." The developer looks, sees perfectly fine code on line 500 and
has no idea that the actual mistake happened 490 lines ago. There are
mitigations for this, but it's fundamentally pretty tough to solve sometimes.

### So Why These Parts?

So now we understand the background and the other possibilities that I didn't
choose. Why choose the pattern that I _did_ choose? Some of it's described
above: the corespondence between universes, and modeling values as
communications.

However, once you have those principles in place, you need solutions for these
components of a value system:

1. The logical concept of a value.
2. Logical operations on that value.
3. The real physical encoding of the value in the physical universe.
4. The real operations that the computer is doing with the real encodings.
5. A system of converters between (a) logical values and their encodings and (b)
   between different equivalent encodings.

The solution in this proposal gives a basic outline of a solution that
encompasses exactly that. It doesn't exactly specify how all of those parts will
work or exactly how each of the proposed pieces solves all of the problems, but
it gives us the basic building blocks on which we can write later proposals.

## Forward Compatibility

Given how explicit everything is in the proposal, it should be possible to
refactor the syntax and semantics into any other system we come up with in the
future, provided that values, encodings, operations, and converters fully
specify everything they are doing and don't leave anything to "magic." At the
least, if they have certain behavior they always do behind the scenes, that
should be exposed somehow as default values that can be changed by the
programmer.

## Refactoring Existing Systems

One of the cool parts of this system is that I believe this is a more expressive
system for core types than I've seen outside of theorem provers like Lean. It
also allows us to provide compile-time performance that could potentially be
greater than any other language if we can more explicitly match all the
characteristics of values to encodings in the most efficient way.

Thus, we should be able to take the existing value-to-encoding systems of any
existing language and translate them into Define.
