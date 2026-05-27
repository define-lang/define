# Define Language Proposal 1: Types of Names

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** December 28, 2025
- **Date Finalized:**

## Problems

### 1: Evolution of a Language

Programming languages tend to have the concept of "reserved words" that cannot
be the names of variables. Then, when they want to change the syntax in the
future, instead they have to say "all programs that used that word are now
broken and must be refactored." This makes it quite painful to upgrade to new
versions of a programming language, and also makes it hard for language
designers to develop new syntax.

For example, Python 3.6 and earlier allowed this syntax:

```Python
def fetch_url(url, async=True):
    if async:
        # run in background
        pass
    else:
        # run now
        pass

fetch_url("http://example.com", async=False)
```

Then Python 3.7 added `async` as a keyword, which broke that code:

```Python
# SyntaxError: invalid syntax
def fetch_url(url, async=True):
                   ^
# The parser expects a function definition here, not a variable assignment,
# because 'async' is now a command, not a name.
```

### 2: Different Types of Names

Every language has different sorts of things that require names. For example,
take this Python program:

```Python
import time

class Clock:
    def get_time(self) -> float:
        return time.time()

def main():
    my_clock = Clock()
    print(my_clock.get_time())
```

That shows a module name (`time`), a class name (`Clock`), a method name
(`get_time`), a function name (`time.time` and `main`), and a variable name
(`my_clock`).

Python provides conventions for those names that you _can_ follow: you are
supposed to name classes with `CamelCase` and variables with
`lowercase_and_underscores`. But you don't _have_ to.

This creates a problem for the reader: they don't know what a name actually
is---they are just guessing based on context. It creates a problem for the
writer: they must avoid creating a variable that has the same name as a
function, class, etc. And it creates a problem for the compiler: it has to
create a table of names which can overlap and refer to different sorts of
things.

It is quite easy for a programmer to make a mistake like:

```Python
import time

class clock:
    pass

clock = time.time()
```

Where suddenly the whole class `clock` no longer exists and has been replaced by
a floating point number.

This general problem (that you can't guarantee what type of thing a name is
talking about) exists in every programming language that I am familiar with.

## Solution

Instead of reserving specific words, Define will reserve _all_ words and only
allow names when they are wrapped in certain symbols. Different types of things
in define will have different prefixes.

The form of all names will look like: `type<name>` where `type` is the prefix
and then `name` is any form of name the developer would like to use. For
example, a quality that we want to name "adder" would look like this:
`quality<adder>`.

Some potential types of names could be:

```
quality
position
view
form
potential_form
trigger
```

However, until syntax is actually defined for a type of name, it doesn't exist
in the language.

Note that this proposal only covers the idea of types and the syntax (the fact
that names are prefixed by the type and surrounded by `<>`). It does not
standardize the names themselves.

## A Real Program

Since I am writing this before Define exists, here is a theoretical program
using the syntax:

```
define the quality<adder> {
    define the potential_form<add> {
        a particle in position<first_addend>.
        a particle in position<second_addend>
    }
    define the trigger<add> {
        take potential_form<add> as form<args>
        return form<args>::position<first_addend> + form<args>::position<second_addend>
    }
}
```

Note that both the potential form and the trigger may both be named "add,"
because the type disambiguates them.

## Why This is the Right Solution

This guarantees our ability to evolve the language in the future.

It disambiguates types of names, and means that we don't need to specify a style
convention for how things are named.

It allows us to represent programs in any programming language, all of which
have different naming conventions.

## Forward Compatibility

Forward compatibility for this proposal is intuitive. If we want to change our
minds, we change the names of any of the types quite trivially. We can add new
types as long as they don't conflict with existing types, and we have infinite
potential words we could use to describe those types.

## Refactoring Existing Systems

There are no existing systems, but let's imagine a syntax that could have
existed before:

```
assign the quality Adder to my_adder.
```

It is quite straightforward to parse that syntax and change it to:

```
assign the quality<adder> to position<my_adder>.
```

It is straightforward because we know what is in each position in each statement
in syntax, already. (Though notice that now with our new syntax it's much
clearer whether `my_adder` is a `position` or a `view`.)
