# Define Language Proposal 38: Binary Values

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** April 12, 2026
- **Date Finalized:**

## Problems

Nearly all computer programs deal with _values_ in some way or another. People
write computer programs to make computers take some sort of action, and there
are very few actions they can take without using values in some way.

The [Concepts](../spec/concepts.md) describe a value as a meaning assigned to a
dimension point, essentially an opinion about a dimension point.

Define will be theoretically capable of doing computation without assigning any
values to dimension points, purely by checking presence or absence on dimension
points in positions (which would represent bits). Define could in this way model
any circuits or any real computation mechanism for discrete data that could
exist in the physical universe. (And in the future, Define Approximately would
be able to represent infinite math as well, giving us the power to represent any
possible form of computation that could _actually_ exist.) However, most
practical programs will want to rely on the simulator (the computer) to do
computation, as it's much more efficient and able to respond to situations from
outside the program (like user input) more dynamically.

Thus, we do need to hae a way to assign meaning (values) to dimension points.

### 1: Infinite Complexity

The problem with opinions, in the world of computer programming, is that
opinions can have infinite complexity. There can be infinite opinions that
relate to other opinions in infinite ways.

However, there are a few saving graces here, for us:

1. We only care about the opinions that are relevant to assign to dimension
   points in order to write computer programs.
2. At any given moment, a computer program does not have multiple viewers who
   have different opinions about what the same dimension point "means." The only
   situation in which this would happen is in parallelism conflicts, and we
   eliminate those through paradox detection.

As the [Concepts](../spec/concepts.md) point out, this means that what we really
care about is assigning a meaning to a dimension point that represents something
in the physical universe. In particular, something about a computer.

### 2: Abstractions

When you press a key on your keyboard, a series of actions happens:

1. There is an electrical signal that produces a "scancode." This is a number
   that says which key you hit on the keyboard (not what letter that represents,
   just where the key is located on the keyboard).
2. That scancode is re-translated into an electrical signal via WiFi or USB or
   however your keyboard is connected.
3. The connection signal is re-translated back into binary by the computer.
4. That binary is sent as another electrical signal to your CPU, which once
   again re-interprets that signal as binary.
5. The CPU sends this binary to your operating system's kernel, which takes the
   scancode, looks it up in its key-mapping table, and says "that's the letter
   A," and then sends the ASCII or UTF-8 or whatever for "A" to the
   currently-active application.

This exposes a lot of wild things for computer programs.

First off, it shows us that what a binary number means at different times in a
computer means different things. At one point it meant the scancode, later it
meant the ASCII code.

It also shows us that there is another thing computers do besides just binary:
they rely on electrical signals. Now, they most often re-interpret these
electrical signals as binary, but the reality in the physical universe is that
they are interpreting a _range_ of voltages or phases or amplitudes (or any
other quality you could imagine using to send a signal) as being 0 vs being 1.
We aren't going to solve this problem as part of Define Exactly, but it's worth
noting that binary is a polite fiction the computer tells us. The physical
reality is a range of electromagnetic states (in fact, always a comparison
between at least two states, such as ground and live wires, or between a voltage
and its inverse across two live wires).

Unfortunately, most hardware only exposes the binary to the software, not the
actual electromagnetic states. As such, we usually can't write programs directly
about those electromagnetic states, and must interact only with the abstraction
of binary data. There are analog controllers and a few specialized pieces of
hardware that will expose the signal information directly, but even then, since
most software is written assuming binary data, even those are often interacted
with by software sending them binary signals.

We could solve the electromagnetic state problem in the future with Define
Approximately. For now, with Define Exactly, the practical realities of the
world require us to focus on binary data.

## Solution

In a Define program, there is only one _real_ type of value: binary data.
Dimension points can only be given the meaning "a sequence of bits."

Dimension points may have only a single value. That value _may_ be an infinite
number of bits (though later proposals will explain how to constrain this), but
those bits all conceptually represent a single value: a single number, a single
character, etc.

### Declaring that a Dimension Point May Have a Value

Developers can indicate that a dimension point accepts a binary value by adding
this as a line in the definition of a position:

`it has a value.`

This is called a Value Declaration.

There is no syntax to add this property to a dimension point later; it must be
assigned at the creation of a dimension point. If a dimension point moves
through a position that does not have a value, the dimension point does not lose
its value. However, referring to the dimension point via that position does not
allow accessing or interacting with its value.

### Initial Values of Dimension Points

Once a dimension point is placed into a position with a value, it is considered
logically to always have a default value. If not specified, that value is
logically a 1-bit 0. However, most often the code the compiler generates will
actually assume that the first value that the dimension gets set to in the
program is actually its initial value.

### Setting a Value on a Dimension Point

A value may be set on a dimension point via this syntax in an Action Statements
Block:

`set the value of position<recipient> to position<source>.`

This is called a Value Setting Statement. It makes `position<recipient>` have
the same value that is curently in `position<source>`. It does not create a
reference to `position<source>` but simply changes the value on
`position<recipient>` to be identical to the value that is currently on
`position<source>`.

Both positions must be declared as having values, otherwise the compiler must
throw an error.

### Memory Layout

It is worth noting that this proposal is not an instruction to the compiler
about what to do with _memory_. For example, if the same value exists in
multiple places in the program and does not change, the compiler may choose to
make all usages of that value in the program point to the same memory location.

### Automated Requirements

Referring to any interface position or quality-required position in a Value
Setting Statement infers that that position must be occupied. (In other words,
it creates an automated requirement in an action for that position to be
occupied.)

## A Real Program

```define
define the potential action<example.com:example:/set_value> {
    define the position<recipient> {
        it has a value.
    }
    define the position<has_a_value> {
        it has a value.
    }
    it happens when {
        the position<has_a_value> has a dimension point.
    } and it does {
        set the value of position<recipient> to position<has_a_value>.
    }
}
```

## Why This is the Right Solution

This is one of the parts of Define that I have done the most reasoning and
research about.

The first key breakthrough was that assigning a value to a dimension point makes
that dimension point into a symbol: a particle with meaning. However, real
living beings can assign any possible meaning to any particle, which creates an
infinite complexity that can't be reasoned about via a programming language.

Thus, I had to create some framework in which values could live and relate to
each other. To start this, I had to reason through _why_ we want to assign
meaning to dimension points in a program, and I determined that it's because we
want to actually _use_ the "simulator" (the computer), like provide actual
concrete instructions to it, not just reason through abstract things inside the
universe of the program itself. Thinking through that further, it became
apparent that computers only care about electromagnetic states, which they
translate into binary. Thus, with most current computers, the only "meaning"
that anything can actually have in a program is "this binary data."

Also, information theory, specifically Claude Shannon's work, dictates that any
discrete information can be losslessy encoded into binary digits (bits). So we
are in pretty safe terrirory here.

It actually would be nice to be able to reason about non-binary electromagnetic
states in a computer program, to help with analog controllers and signal
processors, but those use cases are rare today for programmers and so they
aren't my top priority. Define Approximately will handle these, although we
could also handle them as an incremental improvement to Define Exactly in the
future, by just adding some sort of different value type.

Quantum computing would also need different types of values, potentially.

## Forward Compatibility

Since we have defined both the default state and the way that values transition,
and we can determine that deterministically, theoretically we should be able to
change both the syntax and the semantics here in the future.

The potential danger is if that future change would involve inserting behavior
at _runtime_ into the program. Since we have chosen the current fundamental of
computers (binary data) as the "meaning" of dimension points, it seems unlikely
that we would encounter such a difficult transition in the future. I'm
optimistic that even if such a transition occurred, we would be able to
deterministically transform Define programs in a way that still preserved
optimal performance characteristics.

If we need new types of values (electromagnetic states, quantum states) in the
future, it doesn't seem to hard to create a new value system or additional
syntax alongside the existing system in this proposal.

## Refactoring Existing Systems

There are no Define systems that have a different value system than this,
because this is the first proposal for a value system.

All existing programs that deal with discrete data could be translated into this
form of data. The one exception is that today Define does not allow programmers
to explicitly refer to addresses in memory (pointers) and so programs that
absolutely depend on direct memory manipulation would not be portable to Define.
However, that's not a limitation of this proposal---we could still use binary
data to refer to a memory location if we wanted to.
