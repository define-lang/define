# Define Language Proposal 9: Global Name Circular Dependencies are Forbidden

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** January 3, 2026
- **Date Finalized:**

## Problems

Some programming languages allow circular dependencies, where Module A can
depend on Module B and Module B can depend on Module A, simultaneously. It can
even be more complex, where a symbol inside of A depends on a symbol inside of
B, but B's symbol depends on another symbol inside of A, and so on. This causes
numerous problems.

### Large Compilations

If Module A and Module B depend on each other circularly, any compiler must
actually treat them as a single unit, meaning that it _must_ compile them
together. The larger the cycle, the more compilations it must keep in memory
simultaneously.

While all dependency trees cause this problem when you compile the root node of
the tree, circular dependencies cause the problem when you compile _any_ node in
the dependency tree.

In many large C++ programs, these huge compilation units from circular
dependencies are one of the primary reasons for slow (45+ minute) builds.

### Parallel Compilation

Because cycles create a single compilation unit, such cycles also prevent
parallel compilation. Any set of files involved in a circular dependency must be
compiled in a single thread.

### Tool Incompatibility

Some build tools (such as bazel) don't allow circular dependencies in their
build configuration. When you point them at a codebase that has circular
dependencies, the developer suddenly has to refactor their code if they want to
actually gain the benefit of using that build tool.

### Static Analysis

Circular dependencies complicate static analysis, especially when the static
analysis tooling has its own parser or validator (instead of using the libraries
that come with the compiler).

### Refactoring Circular Dependencies

When you have a set of code files that all depend on each other circularly, it
can be very hard to extract pieces of functionality from that code and move it
somewhere else in your program. You end up having to bring along the whole set
of code with you, which defeats the purpose of refactoring.

Sometimes, the problems caused in a large codebase by circular dependencies are
extremely expensive to untangle when you need to untangle them. I have had to do
some of this work, myself, on multi-million-line codebases. Other developers had
given up and decided it was impossible---that's how hard it can be.

## Solution

Define solves this problem by forbidding circular dependencies between global
names. If a reference to a name outside of the current file would cause a
circular dependency, the compiler must throw an error. So this code is
forbidden:

`my_project/foo.def`:

```
define the quality<example.com:example:/foo> {
    define the potential_form<foo_form> {
        it has a dimension point in position<x> {
            it has the quality<example.com:example:/bar>
        }
    }
}
```

`my_project/bar.def`:

```
define the quality<example.com:example:/bar> {
    define the potential_form<bar_form> {
        it has a dimension point in position<y> {
            it has the quality<example.com:example:/baz>
        }
    }
}
```

`my_project/baz.def`:

```
define the quality<example.com:example:/baz> {
    define the potential_form<baz_form> {
        it has a dimension point in position<z> {
            it has the quality<example.com:example:/foo>
        }
    }
}
```

This creates the cycle `foo -> bar -> baz -> foo`, which would be forbidden.

### Within a File

Within a file, the compiler requires that global names be defined before they
are referenced. If the file `foo.def` contains
`potential_form<example.com:example:/foo>` and
`quality<example.com:example:/foo>`, then they may not circularly reference each
other. If the `quality` wants to reference the `potential_form`, the
`potential_form` must be defined first in the file, and vice versa.

### Non-Filesystem Contexts

In non-filesystem contexts or concatenated files, global names must be defined
before they are referenced, or the compiler will assume the reference should
trigger a file load. If the compiler later encounters a redefinition of the same
global name, it will fail with an error indicating a name conflict. This is
already implied by previous proposals, but is called out here explicitly just to
make the behavior clear.

The compiler should provide configuration values that deny all or certain types
of file loads when processing non-filesystem contexts or concatenated files, to
ensure programs compile as intended. For example, if the compiler knows that
"this entire universe is in this concatenated file," it should deny file loads
for that universe and simply indicate that an unknown name is being referenced.

### Exceptions

There are certain exceptions for situations that _must_ involve circular
references. The most obvious one is access controls. For example, the `program`
quality needs to be able to create a `terminal`, and the `terminal` might want
to have a line of code that indicates that the `program` is allowed to create
it.

The Define Language Spec will call these pieces of syntax out explicitly as
"allows circular dependencies." These would be situations where a global name
reference doesn't trigger a file load, essentially. In these situations, the
compiler may follow a delayed verification model:

1. If the compiler encounters a symbol that is not already defined, it remembers
   it for later verification.
2. When the compiler encounters the definition of that symbol, it then validates
   the reference.
3. If the compiler compiles the entire program without seeing the unknown
   symbol, the compiler indicates an error.

There are even some situations in which Step 3 would be skipped. In this case,
the spec will say that "unknown references are allowed." This would be rare, and
would require the programmer to explicitly state in syntax that they are
intending to write an unknown reference. However, it is necessary for certain
circumstances. For example, imagine that you are writing a library, and you want
to say that your code can be accessed by a certain other external library. The
compiler won't compile that other library just to verify the access control
statement is correct. (It might check the multiverse to know the library exists,
though.)

## A Real Program

The Solution section above contains a sufficiently real program to demonstrate
the restriction.

## Why This is the Right Solution

Most of the pain caused by circular dependencies in existing languages is caused
by circular dependencies between files. That at least forbids a tangle at the
_architectural_ level.

### Modeling Languages That Allow Circular Deps

One problem we might run into is having to model other languages that _do_ allow
circular dependencies. However, you can always model a cluster of
circularly-dependent nodes in a graph as a single node, if you have to, so
theoretically this would be possible, if complex.

### What About Forward Declaration of Local Names?

Originally I considered requiring forward declaration of all local names, as
well. That creates some very painful situations. For example, developers cannot
organize their code into logical sections---they must instead organize it
strictly by how the compiler needs it to be ordered. It's even worse when you
change code---if Function A now depends on Function C, you have to move Function
C to be defined above Function A, even if Function C otherwise didn't change.
There are no modern programming languages that require forward declaration for
all local names, and when I investigated the reasons, they seemed sound.

### What About Circular Dependencies Within a File?

I also considered forbidding circular dependencies in local names as well,
because you can really tangle up a file with lots of internal circular
references. However, that creates all sorts of difficult situations. For
example, it significantly complicates certain code patterns, such as
parent-child relationships (like a "tree" object that has "nodes" but the nodes
want to be able to point back to the tree) and mutual recursion (where two
functions call each other).

We may decide to ban certain forms of circular dependencies between local names,
in order to avoid the worst tangles, but we will leave that for another
proposal.

## Forward Compatibility

It is forward compatible to deny circular dependencies. It would _not_ be
forward compatible to allow circular deps , as we could not change our minds
about that later. (That is, once you allow circular dependencies, there's often
no good way to write an automated refactoring that takes the tangle apart.)

This does mean that if we allow circular dependencies for local names, we can't
change our minds later.

## Refactoring Existing Systems

No systems exist with circular dependencies, today, thankfully. Untangling
circular dependencies cannot be done through automation, as far as I am aware.
At the very least, any automation that can do even part of it is extremely
complex.
