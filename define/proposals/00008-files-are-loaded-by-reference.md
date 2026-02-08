# Define Language Proposal 8: Files Are Loaded By Reference

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** January 2, 2026
- **Date Finalized:**

## Problems

Most programming languages have the concept of "imports" or "includes" where you
indicate explicitly that you intend that the code in this file should depend on
the code in another file. For example, in Python:

```Python
import time

print(time.time())
```

Java:

```Java
import com.example.SomeClass;

public static void main(String[] args) {
    var instance = SomeClass();
}
```

This causes various issues that can turn into real problems in large codebases:

- In most languages, this causes name confusion, as described and solved in
  other proposals.
- These imports can get "out of sync" with the code, so that there are "dead
  imports" (imports that aren't actually used by the code).
- The developer has to remember (or their IDE has to automate correctly) to add
  imports at the top of the file when they want to reference some new thing in
  the middle of the file.
- Imports in some languages require you to import a bunch of code into your
  codebase that you're never going to use, just because you need one thing from
  a module.
- There are stylistic choices you have to make about how you _order_ imports
  that are very difficult to standardize in codebases. For example, Python
  generally _wants_ you to put them in the order "standard library, third party,
  local application" and then alphabetize within those structures. Very few
  Python programs that I have read do this reliably.

Some languages (like Python) even allow dynamic imports based on information
that can only be known while the program is running, which makes reliable static
analysis impossible.

In Define, imports would also be redundant---we already require global names for
global references, so if you had to note at the top of the file that you were
"importing" them, it would just be typing the exact same thing again for no real
value.

## Solution

In Define, there are no "import" statements. Instead, files are loaded by the
compiler when it encounters a global name from outside of the current file and
needs to load it. In other words, referencing a global name means importing that
global name.

They are loaded in the order they are encountered in the code.

This most likely happens during the compiler's validation phase, after lexing,
parsing, and AST transformation.

## A Real Program

Here is an example of a multi-file program.

`my_project/foo.def`:

```
define the quality<example.com:my_project:/foo> {
  define the potential_form<bar> {
    it has a dimension point in position<x> {
      it has the quality<example.com:my_project:/baz>
    }
  }
}
```

`my_project/baz.def`:

```
define the quality<example.com:my_project:/baz> {
  # code goes here
}
```

In this example, when compiling `foo.def`, `baz.def` is loaded when encountering
the line `it has the quality<example.com:my_project:/baz>`.

## Why This is the Right Solution

It eliminates imports entirely, removing all the problems that import statements
have.

It creates one and only one way to import code. It ensures that only code you
actually use and reference in your program gets compiled into your program.

It does potentially cause the problem of accidentally importing two different
similar things in the same file, because you don't have a list of them right at
the top that you can read. Tools could work around this by giving you a clear
view in your editor of what the current file depends on.

It also means that in order to statically understand the dependency tree of a
Define program, you have to at least _parse_ the whole program, not just some
import lines at the top of files. However, this ends up being true in every
other programming language that I'm familiar with anyway, because in many cases
you can just import things in random locations or refer to global symbols
anywhere in a program. Since our global names have only one format, parsing them
out is actually faster and more deterministically reliable than any other
programming language I'm familiar with. (You could probably even figure out the
total set of dependencies in a Define program with a basic set of shell
commands.)

In the future, we may allow some form of aliasing, like:
`alias quality<example.com:my_project:/foo> as quality<local_foo>` but that
would cause a bunch of other problems that we described in
[DLP 5](00005-global-names-local-names-and-scopes.md), and we haven't
encountered a need for it yet. Even if we did allow aliasing, we still wouldn't
resolve names until they were actually used.

## Forward Compatibility

Loading files happens deterministically with no ambiguity. As such, we should be
able to change our minds about how loading works, in the future. If we need to
add imports or some other mechanism like aliasing in the future, we could
refactor the existing system to that with total reliability.

## Refactoring Existing Systems

No previous mechanism of importing exists before this. There is nothing to
refactor.
