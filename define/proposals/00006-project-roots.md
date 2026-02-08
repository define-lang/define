# Define Language Proposal 6: Project Roots

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** January 2, 2026
- **Date Finalized:**

## Problems

### 1: What Do Global Names Mean?

We have defined the concept of global and local names in Define. If you have a
global name that looks like `quality<example.com:example:/foo/bar>`, what does
the first `/` mean? Is there some way that I should mentally map that to a
location on the disk or some way I should be able to find the code?

### 2: The Complexity of Importing Code

I have done a lot of work on systems in other languages that read code off the
disk. For example, Java's "classpath" system, and Python's "import" system,
where I have modified (or attempted to modify) them for specific purposes
internally in large companies (namely, Google).

In a Python project, you can import things so many ways:

```Python
import my_program.foo.bar
from .foo import bar
import bar
```

Depending on how you have configured your Python interpreter, all three of those
could be a valid way to import a module _in your own codebase_. While this may
seem convenient for the programmer, it causes huge complexity and performance
issues in the module importer that _cannot_ be solved because the language
allows all of these syntaxes.

Java has a lot of the same problems, plus a long history of attempting to create
module systems that didn't succeed but which the classpath infrastructure must
continue to support. As a result, in Java, when you type:

```Java
import com.example.SomeClass;
```

Java has to go through a wildly expensive process of opening ZIP files and
reading code just to find that one class. I once re-wrote Java's classpath
system to be much stricter and it was somewhere around 3X faster, but couldn't
actually be used because of a bunch of legacy decisions made during the history
of Java to support various methods of file loading.

### 3: Filesystem Traversal Costs and Restrictions

I have done a lot of profiling of build systems, and one of the surprisingly
expensive parts of building software is the cost of filesystem accesses. Yes,
many filesystems will cache access patterns to make it much faster. However, if
you constantly have to do things like resolving the parent directory or the
absolute path of a file in order to enforce some verification or discover where
a module is, it can get fairly expensive in terms of time.

Also, sometimes programs are compiled in environments where you cannot detect
the absolute path or know the parent directory of the code you're looking at,
due to security restrictions. Or the question "what is the parent directory?"
has an ambiguous answer, due to symlinks.

In general, any enforcement mechanism that requires knowing the absolute path of
a file or traversing to the parent directory of the current directory should be
avoided. Also, any system that requires continuously doing a bunch of `stat`
syscalls to discover if files exist should also be avoided. (For example,
crawling a directory tree and seeing if there is a special config file in just
that directory.)

### 4: Vendoring

Imagine a programmer named Alice who writes a library called `math-utils`. In
her code, she writes: `define the quality <core/adder>`.

Now Bob builds an app. He wants to rely on Alice's library. For one reason or
another, he needs to check Alice's code directly into his own repository,
instead of relying on it as an actual library. This is called "vendoring." His
file structure looks like:

```
/bobs-app
  /src/main.def
  /vendor
     /math-utils   <-- Alice's Code lives here now
        /core
           /adder.def
```

So now how is Bob's app supposed to refer to Alice's `core/adder`? He could
write a program to rewrite all of the references in Alice's `math-utils` to look
like: `vendor/math-utils/core/adder`, sure. However, that is awkward and hard to
maintain. It makes merging future changes from Alice very hard. Also, what if he
wants to switch to the external third-party library in the future? Is he then
going to have to switch all the references in _his_ program from
`vendor/math-utils/core/adder` to just be `core/adder` again?

Many programming languages just take the attitude "well, you shouldn't do that"
about vendoring. However, the practical reality of programming is that sometimes
people have to do this.

### 5: Non-Filesystem Contexts

Programming languages must work even when the code is not written in a file in a
filesystem. For example, they have to work when written in a text box on a web
site, in a REPL, in a string passed in on stdin, etc.

## Solution

All Define codebases that exist on a filesystem have the concept of the "project
root" for that codebase, which is the parent directory that is the
super-directory of all the code in the project. This directory is the directory
represented by the first `/` in a global name.

For example, imagine I have this directory and file layout in my project:

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

In that layout, `my_project/src` is the project root. That means I would refer
to something in the file `my_project/src/foo/bar.def` like:
`quality<example.com:my_project:/foo/bar>`.

### Defining the Root

Any directory that contains the path `.define/project/config.defcl` is a project
root. (In other words, a directory named `.define`, with a subdirectory named
`project`, with a file in it named `config.defcl`.)

The contents and language used for that file are the subject of another
proposal. It is expected to at least contain the name of the universe for the
project, but simply its _existence_ creates a project root, regardless of its
contents.

### Define Tools Must Run From the Root

When the compiler or any language tool for Define is invoked in a filesystem
context, the current directory must be a project root. Otherwise, the tool will
refuse to execute and return an error.

Tool implementers may choose to provide a command-line flag that allows
"discovering" a project root in a directory above the current directory, in
which case the tool will discover that directory and then change its current
working directory to that directory.

The compiler's current working directory must continue to be the project root
for the lifetime of the compiler (with exceptions as specified below).

### Sub-Roots

Define will assume that all code it sees within a project is part of that
project unless the project configuration says otherwise. If there are project
roots in a directory structure below the current root, then the current root's
configuration files must indicate the existence of those "sub-projects."

When a compiler or define tool encounters a sub-root, it creates a new context
for itself and switches its current working directory to that sub-root. It then
runs a complete compilation on that sub-root as its own universe, before
returning to compiling the parent root.

Sub-roots are only compiled when the _code_ indicates that compiling them is
necessary, not simply because they are listed in the configuration. For example,
you could have this directory structure:

```
my_project/
    .define/project/config.defcl
    core/foo.def
    lib/math-utils/.define/project/config.defcl
    lib/math-utils/adder.def
```

The file `my_project/.define/project/config.defcl` would indicate that the
subdirectory `lib/math-utils` is a sub-root.

However, unless `my_project/core/foo.def` actually _references_ `adder.def`
somehow, `lib/math-utils` would never be compiled, nor would its configuration
ever be accessed.

It is recommended that compiler implementers provide a tool to discover "dead"
libraries like this so that developers can choose to remove them from their
filesystem. The language must make it deterministically possible to know that a
library is "dead."

### Sub-Roots Must Be Unique Universes

As implied by the specifications for universes, authorities, and multiverses,
any sub-root loaded during the lifetime of the compiler must contain a universe
with a unique fully-qualified universe name. No two sub-roots that are actually
compiled during a compilation may claim to contain the same fully-qualified
universe name.

### Sub-Roots Must Contain the Expected Universe

The project root will say what universe is in each sub-root. For example, it
might contain configuration values like this (in an imaginary configuration
language since this is being specified before the configuration language
exists):

`sub_root { fqun "mv:alice.com:math-utils" path "lib/math-utils" }`

When the compiler reads the configuration in `lib/math-utils`, the file
`lib/math-utils/.define/project/config.defcl` must say that the project is named
`mv:alice.com:math-utils`.

### Non-Filesystem Contexts

When code is compiled via a non-filesystem context, such as being passed in as a
string with no file name or being written in a REPL, the project root only
becomes relevant when the compiler discovers it needs information about the
project root (for example, to look for definitions that are not defined inside
of the passed-in string).

When compiling outside of a filesystem context, the compiler does not look for
or require a project root until it needs one.

The compiler _may_ take a command-line flag to indicate a project root that
should be used during non-filesystem compilation, to allow for specifying needed
configuration.

### Universes Have a Single Root

Any given project (universe) has a single directory that is its project root.
Allowing for multiple roots would allow for ambiguity in file loads---it's
possible to have the same path in two separate directories. Define forbids
ambiguity.

## A Real Program

`TODO`

## Why This is the Right Solution

If we know what directory the compiler is running in, it greatly simplifies
filesystem traversals. We don't have to figure out where `foo/bar/baz.def` is,
it's in that exact subdirectory from where we are running. We just load files as
we encounter them in code, without having to "hunt" to see what files might
exist, where. Along with later proposals, it makes code loading deterministic
without extensive ambiguity. It also gives us a single place to look for
configuration for the project.

Sub-roots solve the vendoring problem.

Other solutions would involve always discovering that the
`.define/project/config.defcl` file exists, which would involve constant stat
calls. I also considered simply naming the config file `.define/project/config`
and allowing for any extension, but directory lists are usually more expensive
than simple calls to see if a file exists, so I went with a fixed path.

## Forward Compatibility

In general, strictness like this should provide us more flexibility in the
future. If we do want to change the location of the configuration file in the
future, we know exactly where it is. If we switch to another method of defining
project roots, we know exactly what defines them now.

Given the system allows no ambiguity, if we wanted to migrate away from this
system, theoretically we could just provide a script that deterministically
migrates a codebase away from this system to some other new system, so the
compiler would not have to maintain legacy "cruft" to deal with this as an old
system.

## Refactoring Existing Systems

It would be very challenging to migrate code from _not_ having this system into
having it. This is why it needs to be part of the language from the start.
Theoretically one could try to look at how code references other code and try to
"figure out" the project root from how the code is structured, but you couldn't
do it deterministically on 100% of codebases.
