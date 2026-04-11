# Define Language Proposal X: Values

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** April 10, 2026
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

Developers can indicate that a dimension point accepts a value by adding this as
a line in the definition of a position:

`it has a binary value.`

Dimension points may have only a single value. That value _may_ be an infinite
number of bits (though later proposals will explain how to constrain this), but
those bits all conceptually represent a single value: a single number, a single
character, etc.

A value may be set on a dimension point via this syntax in an Action Statements
Block:

`set the value of position<recipient> to position<source>.`

That makes `position<recipient>` have the same value that is curently in
`position<source>`. It does not create a reference to `position<source>` but
creates an entirely new value.

Once a dimension point is placed into a position with a value, it is considered
logically to always have a default value. If not specified, that value is
logically a 1-bit 0. However, most often the code the compiler generates will
actually assume that the first value that the dimension gets set to in the
program is actually its initial value.

## A Real Program

## Why This is the Right Solution

## Forward Compatibility

## Refactoring Existing Systems
