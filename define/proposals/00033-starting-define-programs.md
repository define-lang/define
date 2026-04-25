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

1. Define a position with a single required quality. This position is called the
   "view point."
2. Create a dimension point in that position.

In order for a program to actually _run_, the single required quality has to be
a `potential position`, because its Position Assignment Block will run when the
potential position is assigned to the view point.

Thus, in essence, when a program starts, it does:

1. Create an empty position with no constraints.
2. Create a dimension point in that empty position (the view point).
3. Assign that dimension point a quality (a potential position).
4. The Position Assignment Block of that position runs.

### Compiling Define Programs

To compile a Define program, one simply compiles the definition of a single
potential position. The compiler then goes through and compiles the whole
program by tracing symbol references from that single quality.

It is also legal to compile a file containing a potential action, but all that
will happen is that it will verify the action compiles correctly. In the future,
this may create some form of shared library, but we have not yet defined how
that would work.

### Init Ending Does Not Terminate the Program

Define programs do not terminate when the first position initialization block
ends. They only terminate as described in a later proposal.

## A Real Program

```
define the potential action<mv:example.com:example:/start> {
    define the position<run>.
    it triggers when {
        the position<run> has a dimension point.
    } and it does {
        # The actual code of the program.
    }
}

define the potential position<mv:example.com:example:/main> {
    it may only contain dimension points where {
        it has the action</start>.
    }
    after it is assigned {
        create a dimension point in position</main>.
        create a dimension point in action</start>::position<run>.
    }
}
```

In that program, the view point gets assigned the position `main`. That causes
the Position Assignment Block of `main` to run, which runs `start`. In general,
this pattern (having a position trigger a single action) is the recommended form
for Define programs, so that they do not do work inside of a constructor (where
the compiler is holding a lock on the view point before it finishes initializing
it). The compiler will optimize this into a synchronous function call, anyway,
most likely.

## Why This is the Right Solution

This creates an elegant way to start a program from any position in the program,
for debugging purposes or simply to have multiple potential binaries created out
of the same codebase. It also fits in very well with our
[Concepts](../spec/concepts.md) and finally gives some reality to the "view
point" concept.

It also means there never has to be any special syntax or semantics for "main."
We just use syntax and semantics that already exist in the program.

The slightly awkward downside is that it makes the equivalent of a _constructor_
into the "main" function, which might be slightly awkward for the compiler, but
that doesn't seem too difficult to handle.

### Alternative Solutions

We could have chosen to have a specially-named action that runs when the program
starts. That ends up being pretty similar.

We could have chosen to just make "compile this action" into the entry point, to
enforce the best practice described in A Real Program. (Basically, we would have
just assigned and triggered the action.) However, that would mean we could never
choose to make "compile this action" mean something different in the future
(like "create a library"). Also, we would have had to specify some convention
for how the action gets triggered. Generally I want to avoid things like naming
conventions or function signature conventions in Define, as names shouldn't have
meaning other than "this is a particular position in space."

Basically, all the other options involve inventing new syntax to indicate that
something is main, and that seemed both unnecessary and more likely to lock us
into a bad forward compatibility situation that we would eventually want to get
out of (like Java making `String[] args` a required argument on every main
function even when it hardly matters for many programs).

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

We handle both of those situations. The one situation we don't handle is that
`main` often returns an integer, which becomes the error code returned to the
operating system, by convention. We will handle that explicitly, most likely via
a library, instead.
