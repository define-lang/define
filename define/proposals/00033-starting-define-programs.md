# Define Language Proposal 33: Starting Define Programs

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** January 26, 2026
- **Date Finalized:**

## Problems

How does a universe start? How do you start a define program? What file do you
compile to indicate that this is a binary that you want to start? What syntax do
you use to indicate that this is where the program is starting?

Traditional programming languages have the concept of a "main" function.
Essentially, you write a certain function with a certain signature. The compiler
looks for that and then runs that function when the program starts.

In C, it looks like:

```C
int main() {
    return 0;
}
```

In Java:

```Java
public static void main(String[] args) {
}
```

In Python:

```Python
def main():
    print("Hello from Python")

if __name__ == "__main__":
    main()
```

Define doesn't even have the concepts necessary to have a "main function." So
how do we start programs?

## Solution

When a Define program starts, it does the following:

1. Defines a position (called the "view point") with a single required quality.
2. Creates a particle in that position (called the "view point particle").

In order for a program to actually _run_, the single required quality has to be
a `potential action` that is a constructor, which runs as soon as that initial
particle is created.

### Compiling Define Programs

To compile a Define program, one simply compiles the definition of a single
constructor. The compiler then goes through and compiles the whole program by
tracing symbol references from that single quality.

It is also legal to compile a file containing a potential action that is not a
constructor, or a potential position, but all that will happen is that it will
verify the code compiles correctly. In the future, this may create some form of
shared library, but we have not yet defined how that would work.

### Init Ending Does Not Terminate the Program

Define programs do not terminate when the first constructor ends. They only
terminate as described in a later proposal.

## A Real Program

```
define the potential action<mv:example.com:example:/start> {
    it triggers when {
        this particle is created.
    } and it does {
        # The actual code of the program.
    }
}
```

## Why This is the Right Solution

This creates an elegant way to start a program from any constructor, for
debugging purposes or simply to have multiple potential binaries created out of
the same codebase. It also fits in very well with our
[Concepts](../spec/concepts.md) and finally gives some reality to the "view
point" concept.

It also means there never has to be any special syntax or semantics for "main."
We just use syntax and semantics that already exist in the program.

The slightly awkward downside is that it makes a constructor into the "main"
function. The nice thing is that in Define, a constructor is essentially just
like any other action, from the perspective of the compiler, so there's no
actual compilation or runtime complexity from making a compiler "do work."

### Alternative Solutions

We could have chosen to have a specially-named action that runs when the program
starts. That ends up being pretty similar.

We could have allowed the view point to be a global position with lots of
different constraints on it (potentially multiple different constructors).
However, there's no way to directly create a particle in a global position; it's
not clear what that would even mean. I suppose we could make the view point
position _imply_ the global position. We might do that in the future, but it
creates too many ways to do things, and the semantics of "run this action" feel
more natural.

All other options involve inventing new syntax to indicate that something is
main, and that seemed both unnecessary and more likely to lock us into a bad
forward compatibility situation that we would eventually want to get out of
(like Java making `String[] args` a required argument on every main function
even when it hardly matters for many programs).

## Forward Compatibility

We can't really change our minds about how this works, because "compile this
file" will be built into workflows (CI systems, scripts, etc.) that are
completely outside of our control. As a result, we have to be very confident
that this is the right approach. That's true of any approach. This one seems the
most flexible, since it just uses all of the power of the language to behave
exactly like the rest of the language does.

## Refactoring Existing Systems

This is a considerably more powerful and flexible system than other programming
languages, for the most part. Other languages generally fall into two camps:

1. Having a main function.
2. Executing code that's written at the top level in a file.

We handle both of those situations. The one situation we don't explicitly handle
is that `main` often returns an integer, which becomes the error code returned
to the operating system, by convention. We will handle that explicitly, most
likely via a library, instead.
