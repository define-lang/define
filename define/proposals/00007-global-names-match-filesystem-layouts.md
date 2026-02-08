# Define Language Proposal 7: Global Names Match Filesystem Layouts

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** January 2, 2026
- **Date Finalized:**

## Problems

### 1: Matching Global Names to Files

If I see `quality<example.com:example:/foo/bar>` how can I be confident that
that is located in `foo/bar.def` relative to the project root? What if I load
`foo/bar.def` and I find something else in that file?

### 2: Sub-Roots Create Ambiguity

Imagine you have a project with a sub-root in `lib/math-utils` with a file
`lib/math-utils/adder.def`. You could refer to the code in `adder.def` in two
different ways in your codebase, even though it's the same thing: as
`quality<example.com:my_project:/lib/math-utils/adder>` (as though it's part of
your codebase, incorrectly) and `quality<mv:alice.com:math-utils:/adder>` (as
though it is a third-party library that you have "vendored" into your codebase).
That creates ambiguity and Define forbids ambiguity.

### 3: Sub-Roots Allow for Conflicts

Imagine this set of files:

```
my_project/foo.def
my_project/lib/math_utils/adder.def
my_project/lib/math_utils/bar.def
```

Let's say that `my_project` is the project root, and `lib/math-utils` is a
sub-root that contains the universe `mv:alice.com:math-utils`.

What if `bar.def` is not actually part of `lib/math-utils` and it contains a
definition like:
`define the quality<example.com:my_project:/lib/math_utils/bar>`? Well, that's
allowed by our current proposals. But then what if `mv:alice.com:math-utils`
decides to start including a file of its own called `bar.def` in future
releases? Uh-oh, that creates a file conflict that would require human
intervention.

## Solution

Having global names and project roots solves most of these problems. However, we
are missing one important point: enforcement of what's in the files.

### Global Names Must Map to the Filesystem

When reading a file in a Define project, Define must enforce that the global
name after the fqun matches the filesystem layout.

For example, imagine we have this layout for a Define project:

```
my_project/
    src/
        foo.def
        foo/
            bar.def
            utils/
                uri.def
        core/
            router.def
```

Assuming that each `.def` file above defines a quality, the above example
directory structure would contain the following qualities:

```
quality<fqun:/foo>
quality<fqun:/foo/bar>
quality<fqun:/foo/utils/uri>
quality<fqun:/foo/core/router>
```

Where `fqun` is some valid fully-qualified universe name.

If those files contain any other name, the Define compiler would indicate an
error. For example, if `my_project/src/foo.def` contained `quality<fqun:/baz>`,
the compiler would indicate an error and refuse to compile that file.

Note that one file may contain different _types_ of names. Thus, a single file
_may_ contain more than one definition, as long as they are different types of
definitions. For example, `my_project/src/foo.def` might contain a definition
for both `quality<fqun:/foo>` and `potential_form<fqun:/foo>`.

### Sub-Root Conflict Detection

The compiler must throw an error if it discovers that a file is within a
sub-root on the filesystem but it was loaded as though it was in a different
root. It should not do this eagerly, but only when it discovers the conflict.

For example, taking the example layout from the Problems section above:

```
my_project/foo.def
my_project/lib/math_utils/adder.def
my_project/lib/math_utils/extra/bar.def
```

Now imagine the following sequence of events:

1. `foo.def` references
   `quality<example.com:my_project:/lib/math_utils/extra/bar>`.
2. The compiler loads and compiles `lib/math-utils/extra/bar.def`. At this time,
   no error is thrown.
3. `foo.def` then later references `quality<mv:alice.com:math_utils:/adder>`.
4. The compiler looks at the project configuration for `my_project` and sees
   that `mv:alice.com:math_utils` is in `lib/math_utils`.
5. The compiler sees that it should load `adder.def` from `lib/math_utils`.
6. The compiler realizes that the earlier `bar.def` is contained inside of a
   sub-root but was claimed to be owned by the main project root.
7. The compiler throws an error indicating the conflict.

### Non-Filesystem Contexts

In a development environment that is not on a filesystem at all (such as a REPL,
a raw string being passed to the compiler, a textbox on a web page, etc.) the
Define compiler only needs to enforce any of these restrictions in situations
where project roots become relevant (for example, when loading code outside of
the immediate string that is being compiled).

For now, this also solves the problem of concatenation, by allowing
concatenation to happen in non-filesystem contexts. (I am wary of allowing
concatenation on the disk, as that could then persist in source control and
conflict with future valid files, creating potential ambiguity.)

## Why This is the Right Solution

This gives all Define tools confidence about where to find a definition.

It solves all sub-root ambiguity problems, because the sub-root must now
explicitly specify that the code in the file belongs to its own universe, or the
compiler will throw an error. That is, if `lib/math-utils` is a sub-root, the
file `lib/math-utils/adder.def` must now say:
`define the quality<mv:alice.com:math-utils:/adder>` or that's an error.

It also solves potential sub-root conflicts. Even though those conflicts are
unlikely, they are _possible_ ambiguity, and Define attempts to forbid possible
ambiguity.

It provides the flexibility needed in non-filesystem contexts without providing
a broad escape hatch for persistent files on the disk (because that would
potentially degrade the guarantees of Define).

## A Real Program

`TODO`

## Forward Compatibility

By preventing all conflicts and enforcing what is in files, we eliminate
ambiguity from the filesystem, allowing tools to reliably and simply refactor
full Define codebases deterministically.

We assume that non-filesystem contexts are not intended to be long-term
maintained pieces of software and thus do not need the same strength of
guarantees. However, since for non-filesystem contexts we expect much of the
program to be within the string we are compiling, we can still apply most
potential refactorings to the string just as we would to the files on the disk,
with no difficulties caused by lifting the filesystem restriction (as it simply
doesn't _matter_ in that context).

The one danger is that a developer could choose to use the non-filesystem
contexts as a workaround, persist the code on the disk, and violate constraints
in a way that our refactoring systems do not expect.

Otherwise, we should be able to deterministically refactor both on-disk files
and non-filesystem code.

## Refactoring Existing Systems

No systems exist to be refactored. If systems did exist, one could refactor most
systems by simply moving files around to match what their definition claims
their path is. Of course, one might run into conflicts trying to copy multiple
files into the same location, which is why this enforcement has to be in place
from the start of the language.
