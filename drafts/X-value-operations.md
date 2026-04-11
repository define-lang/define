### 3: Types of Values

All programming languages in existence today have to deal with the fact that the
number 97 sometimes means the letter "A," sometimes means the abstract concept
of the decimal number 97, sometimes means a special code for which fruit the
user has purchased, sometimes means the number of cents in a price, and so on
and so forth.

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

This has numerous challenges. Once you have types, you must describe how they
can be related to each other. Early languages started off by hardcoding these
rules---integers and floats can interact, but only in the ways the compiler
knows about. Characters are integers, but specifically ASCII (or UTF-8) coded
ones only, so you can interact with them like integers. Boolean values had a
value of 0 or 1 (often very confusing when you set some integer to 0 by default
and then it was able to be used as a boolean value, or when you accidentally
added boolean values together instead of just checking them or flipping them
like bits).

Later on, languages allowed types to have "is a" relationships to each other. A
letter is an integer, an integer is a number, and a float is also a number. This
works great until you have a problem like: what if I want letters that are not
represented by integers, but by something else, but I still want them to behave
exactly like letters are guaranteed to behave? This gave us various
compositional models and dependency injection in an attempt to solve the "what
if sometimes this has some different implementation" problem.

The real problems that type systems are trying to solve are:

1. Don't allow operations that don't make logical sense.
2. Don't require the programmer to know the implementation of the operations in
   order to be able to guarantee/understand how they will work. (The programmer
   knows the contract, but not the implementation.)
3. Be able to accept unknown inputs that have necessary properties. Like, "this
   function accepts any two numbers, regardless if they are integers, floating
   point numbers, BigInts, or whatever, and then it adds them."
4. Allow the programmer to define their own system that can re-use the existing
   contracts with additional functionality or modifications. ("In my program, I
   have a special type of integer that prints out differently when you convert
   it to a string, but otherwise they behave identically to how integers
   normally do.")
5. Allow contracts to be enforced on how values may be passed through the
   program. ("You can't provide a letter as an argument when I asked for a
   number.") This one is really in service of "don't allow operations that don't
   make logical sense," but it's a core logical component of why we have type
   systems, so it seemed worth mentioning.

If we break this all down, then very basically, the minimum question a dimension
point needs to be able to answer is: **"What operations am I meaningful input
for?"** This further breaks down into two separate questions:

1. What operations _can_ operate on this data?
2. What operations _should_ operate on this data?

For example, I _can_ add `NumberOfApples` and `NumberOfOranges`. They are both
small integers. But in most situations, I _shouldn't_ add those numbers
together, unless I'm trying to calculate "total number of fruits," and ideally
the structure of the program would prevent me from doing so.

The compiler, however, should clearly tell me that I _can't_ multiply the letter
"a" by the number 10. That shouldn't even be an option.

So another way of looking at this is: maybe "integer" isn't a thing that data
**is**. Maybe it's a set of things you **can do** with data.

### 4: Runtime Efficiency and Magical Behavior

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
compiler can avoid actual bit conversions that happen in the CPU, but not
always.) This is some pretty benign magic, but I personally had not thought
about the fact that this was happening until I was researching for this
proposal.
