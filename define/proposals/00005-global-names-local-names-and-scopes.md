# Define Language Proposal 5: Global Names, Local Names, and Scopes

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** January 1, 2026
- **Date Finalized:**

## Problems

### 1: Name Conflicts

In many programming languages, the same name can have multiple meanings. For
example, this Python program routinely confuses Python programmers:

```Python
my_number = 0

def set_number_to_ten():
    my_number = 10

set_number_to_ten()
print(my_number)
```

That program prints `0`, because the `my_number` inside of the function is not
the same as the `my_number` outside of the function. This, however, works:

```Python
my_number = 10

def print_my_number():
    print(my_number)

print_my_number()
```

That prints `10`. But _this_ does not work:

```Python
my_number = 10

def print_my_number():
    print(my_number)
    my_number = 20

print_my_number()
```

That produces:
`UnboundLocalError: cannot access local variable 'my_number' where it is not associated with a value`.

Wait, what? Essentially, what happens here is that the compiler is forced to
develop a fairly complex system to determine what names mean what in what
context. As you can see in this case, the compiler actually had to look at a
_later_ line in the function in order to know how an _earlier_ line would
behave.

This also leads to confusion for the programmer. In fact, most Python
programmers today have no idea that what is described above is how Python works.

In an attempt to be helpful and convenient for the programmer, most programming
languages have added complexity to their compiler and confusion for their users.

And if you think the above example is confusing, try running this code:

```Python
functions = []
for i in range(3):
    functions.append(lambda: i)

# Programmer expects: [0, 1, 2]
# Actually prints: [2, 2, 2]
print([f() for f in functions])
```

Here's another example from C++:

```C++
class Base {
public:
    void process(int x) { cout << "Int: " << x; }
};

class Derived : public Base {
public:
    // This function HIDES Base::process(int), it does not overload it.
    void process(double y) { cout << "Double: " << y; }
};

int main() {
    Derived d;
    d.process(10); // Error!
    // Compiler expects a double (from Derived), and Base::process(int) is invisible.
}
```

### 2: Understanding Symbols Across Files

Let's imagine these Python files:

`clock.py`:

```Python
import time

now = time.time

def one_minute_later_than_now():
    one_minute_in_seconds = 60
    return now() + one_minute_in_seconds
```

`stopwatch.py`:

```Python
import clock

def start_and_end_time():
    return (clock.now(), clock.one_minute_later_than_now())
```

When a human or a static analysis tool reads the file `stopwatch.py`, they have
no idea that `clock.now()` is exactly `time.time()`. They would have to actually
open and process the file `clock.py` to find that out, and the compiler (or the
runtime, in Python's case) also has to keep track of the fact that both of those
symbols (`clock.now` and `time.time`) actually refer to the exact same thing.

### 3: Disambiguating Where A Variable Is From

Imagine you have this Python file:

```Python
import uuid

def my_function():
    time = uuid.uuid1()
    #
    # Imagine there are now 300 lines of code here
    #
    print(time.time)
```

Now you, the programmer, have to remember what `time.time` means there. In most
Python programs, that would be a reference to the `time` function in the `time`
module. But here it is a reference to the `time` property on a `uuid.UUID`
object. You have to keep the context of the program in your mind in order to
understand that line of code, even if that context was hundreds of lines higher
up in the file.

Basically the question in the mind of the programmer is, "Is that a `time`
variable that I defined, or is it a `time` variable from some other file or
location in the program?"

### 4: Disambiguating Module Sources

In some programming languages, it is very hard to understand whether a name you
are referring to is something from the standard library, an external library,
your current program, or is something "built in" to the language.

For example, are these Python imports part of your program, the standard
library, or a third-party library?

```Python
import clock
import enum
import pathlib
import typing
```

You can't tell just by looking at them. And even worse, the answer is: it
depends. Depending on what version of Python you're running and how you have
configured your Python interpreter, these could be inside of your codebase, from
the standard library, or from a third-party source.

Some programming languages make you _think_ you can figure this out, when in
reality you can't. For example, in Java you might see:

```Java
import com.yourcompany.SomeClass;
import com.yourcompany.SomeOtherClass;
```

You might simply assume that those are both inside of your codebase, since they
both have the domain name of your company attached to them. But they could be in
your codebase, in another codebase inside of your company, or even in an
open-source library that your company released.

### 5: Concatenating Files

In some contexts, programmers need to take code from a bunch of different files
and combine it all into a single file. For example, today this is common when
writing JavaScript, where there are build and performance reasons to do this so
that the web browser gets everything at once.

Most programming languages either fail at this completely, or make it very
difficult. Ideally, a programming language would allow you to simply concatenate
files without modifying them and the code would still work.

## Solution

The solution is to specify two types of names: global names and local names, and
then describe how and when they must be used.

### Fully-Qualified Universe Names

The definition of a fully-qualified universe name is any of the following:

1. `multiverse:authority:universe`
2. `authority:universe` with the implied multiverse of `local`.
3. Any universe allowed to exist by itself in names per the Define Language
   Standard, such as `standard`.

This is referred to as `fqun` in later sections and other proposals.

### Global and Local Name Formats

We create two types of names: global names and local names.

A global name takes the format: `type<fqun:/path/to/name>`.

A local name takes the format: `type<name>`.

These are the only two allowed name formats in Define.

### Global Names Must Be Unique Within a Program

Within any given program that Define is compiling, global names must be entirely
unique. The same name for the same `type` cannot be defined twice. (One can have
the same name for different types. For example, a `quality` and a
`potential_form` could share the same name.)

### Local Names

Local names only exist inside of another definition. For example (using some
semi-imaginary syntax since we are writing this before the Define syntax is
fully specified):

```
define the quality<fqun:/drawings/graph> {
    define the potential_form<coordinate> {
        a dimension point in position<x> {
            it has the quality<standard:/integer>
        }
        a dimension point in position<y> {
            it has the quality<standard:/integer>
        }
        a potential_form<extra_info> {
            a dimension point in position<label> {
                it has the quality<standard:/string>
            }
        }
    }

    define the potential_form<graph> {
        a dimension point in position<x_axis> {
            it has the quality<example.com:graphs:/axis>.
        }
        a dimension point in position<y_axis> {
            it has the quality<example.com:graphs:/axis>
        }
    }

    define the trigger<draw> {
        it takes the arguments {
            potential_form<graph> as form<graph>
        }
        it does {
            # Code for the trigger goes here
        }
    }
}
```

`potential_form<coordinates>`, `position<x>`, and `position<y>`,
`potential_form<extra_info>`, `position<label>`, `potential_form<graph>`,
`position<x_axis>`, `position<y_axis>`, `trigger<draw>`, and `form<graph>` are
all local names.

We will refer to this example code many times again throughout this proposal to
explain various things.

### Name Scopes

Every name has a "scope," which is the definition that is its direct parent. For
example, `position<x>`, `position<y>`, and `potential_form<extra_info>` above
all have the exact same scope. The parent scope is the definition of
`potential_form<coordinate>`. `position<label>` is in a child scope of
`potential_form<extra_info>`.

More simply, we might say that `potential_form<coordinates>` is the direct
parent of `position<x>`, and `position<x>` is a direct child of
`potential_form<coordinates>`. That means that `position<x>` is in the scope
created by `potential_form<coordinates>`.

Scopes only have the meaning they are assigned in this proposal.

#### Global Scope

At the very top level of a program (not inside of any other definition) we have
a scope that we call the "global scope."

The global scope may not define local names. It must only define global names.

In the example above, `quality<fqun:/drawings/graph>` is defined in the global
scope.

Global names may only be defined in the global scope.

#### Local Scopes

Any scope created by another definition is a local scope. Every definition in
the above example other than `quality<fqun:/drawings/graph>` is in a local
scope.

The Define Language Specification will explicitly indicate if syntax creates a
local name scope.

#### Transitive Scopes

If we say "transitive parent scopes," we mean all scopes that are parents,
parents of parents, and so on until we get to the top-level scope. For example,
the transitive parent scopes of `position<label>` are the scopes created by
`potential_form<extra_info>`, `potential_form<coordinates>`,
`quality<fqun:/drawings/graph>`, and the global scope.

If we say "transitive descendent scopes," we mean all scopes that are at a lower
level than the current scope. For example, the transitive descendent scopes of
`quality<fqun:/drawings/graph>` are the scopes created by
`potential_form<coordinate>`, `potential_form<extra_info>`,
`potential_form<graph>`, and `trigger<draw>`.

Recall, however, that there will never be a local name in the global scope,
though, and so rules about local names will never apply to the global scope.
Thus there will be many situations where the compiler does not have to ascend or
descend into the global scope to verify local name correctness, as there are
never local names in the global scope.

### Referring to Local Names

Within the same scope, local names may refer to each other exactly as they are
defined. For example, if we wanted to change our example above about
`position<x>` and `position<y>`, they could refer to each other line this:

```
define the potential_form<coordinate> {
    a dimension point in position<x> {
        it has the quality<standard:/integer>
    }
    a dimension point in position<y> {
        it has the same quality as position<x>
    }
}
```

`position<x>` and `position<y>` are defined in the same scope, so they simply
refer to each other by their local name.

Local names may also refer to anything defined in a transitive parent scope. For
example:

```
define the potential_form<coordinate> {
    a dimension point in position<x> {
        it has the quality<standard:/integer>
    }
    it has the potential_form<y_info> {
        a dimension point in position<y> {
            it has the same quality as position<x>
        }
    }
}
```

There you see that the definition of `position<y>` can refer to `position<x>` by
its local name, since `position<x>` is in one of `position<y>`'s transitive
parent scopes.

### Referring to Inner Members

Any definition that creates a local scope can have things defined inside of it.
For example, we can see above that `quality<fqun:/drawings/graph>` defines
`potential_form<coordinate>`. We call a definition like this that is inside of
another definition an "inner definition." There must be some way to refer to
inner definitions.

Global names and local names can be combined using the symbol `::` to refer to
inner members.

For example, taking the example of `quality<fqun:/drawings/graph>` above, let's
imagine we put some code inside of `trigger<draw>`. We would need some way to
refer to the contents of `form<graph>`:

```
it has the trigger<draw> {
    it takes the arguments {
        potential_form<graph> as form<graph>
    }
    it does {
        # Imagine that the x_axis and y_axis positions have a quality
        # that defines a trigger called "render."
        execute potential_form<graph>::position<x_axis>::trigger<render>
        execute potential_form<graph>::position<y_axis>::trigger<render>
    }
}
```

What if `trigger<draw>` above needed to refer to something defined outside of
`quality<fqun:/drawings/graph>`? In that case, it might have a line that looked
like:

`create a quality<fqun:/drawings/circle>::potential_form<outline> in form<outline_dot>`

In other words, the only thing that changes is the first element in the chain of
names. For global names it's the global name first, and then the local names
inside of that thing. For local names it's a local name first, and then the
local names inside of that thing.

The full name "path" thus created is referred to as a "chained name."

### Local Naming is Enforced

When it is valid to use a local name, a local name must be used. You may not
choose to use a global name in a context where a local name would be valid to
use.

For example, this code is not valid:

```
define the quality<fqun:/drawings/graph> {
    it has a potential_form<graph> {
        it has a dimension point in position<x> {
            it has the quality<standard:/integer>.
        }
        it has a dimension point in position<y> {
            it has the same quality as quality<fqun:/drawings/graph>::potential_form<graph>::position<x>.
        }
    }
}
```

That would throw an error indicating that the reference
`quality<fqun:/drawings/graph>::potential_form<graph>::position<x>` must be
written as `position<x>`.

You may also not define inner definitions using global names. This code is also
invalid:

```
define the quality<fqun:/drawings/graph> {
    it has a potential_form<fqun:/drawings/graph/coordinate> {
        # code goes here
    }
}
```

That would throw an error indicating that
`potential_form<fqun:/drawings/graph/coordinate>` must be defined using a local
name.

### Local Name Conflicts

Local names may not be identical to any name in their transitive parent scopes.
For example, this code is disallowed:

```
define the potential_form<foo> {
    it has the potential_form<foo> {
        # some code here
    }
}
```

That would make the meaning of `potential_form<foo>` ambiguous, and Define
forbids ambiguity.

Note that different types of names do not conflict. So for example, this is
allowed:

```
define the quality<foo> {
    it has the potential_form<foo> {
        # more code here
    }
}
```

## A Real Program

There are extensive numbers of real programs in the Solution section above.

## Why This is the Right Solution

Problem 1 (Name Conflicts): This (in particular, the use of global names for
everything that isn't local, combined with the local name conflict rule)
completely solves name conflicts. Name conflicts are impossible.

Problem 2 (Understanding Symbols Across Files): Because everything has exactly
one name, you always know what is being referred to, even across files.

Problem 3 (Disambiguating Where a Variable is From): You can always tell where a
concept comes from, and you can always tell if it's not from inside of the
current top-level definition.

Problem 4 (Disambiguating Module Sources): The _format_ of a global name always
tells you exactly what you're referring to, whether it's a part of your current
program, the standard library, something "built-in" to Define, or an external
library. In fact, it even tells you if the external library is from the standard
open-source ecosystem or internal to your company.

Problem 5 (Concatenating Files): Because local names can never exist in the
global scope, and because global names can only be defined in the global scope,
files can be concatenated together with no change to the code.

### Caused Problems

I acknowledge that this does cause some problems.

#### Moving Symbols Causes Refactoring

If you move a symbol out from inside of a particular definition, you have to
refactor everything that refers to it. For example, if you have this code:

```
define the quality<fqun:/foo/bar> {
    define the potential_form<baz> {
        # code goes here
    }
}
```

And you want to move `baz` into its own top-level definition, you have to change
all the code that refers to it. Because one of Define's goals is deterministic
refactoring, this shouldn't be hard to accomplish, but still can be annoying or
difficult in large code ecosystems.

We could potentially solve this by leaving behind some sort of "tombstone" that
auto-redirects to the new definition, but we won't do that because it causes
multiple of the other Problems from above, again. (It allows confusion about
what symbol you're actually talking about when reading code that depends on your
code.)

#### Verbosity

As with the rest of Define, having to use global names explicitly can become
very verbose. In the future we may allow some form of aliasing certain global
names so that you can refer to them in a shorter way. However, this would
re-cause some of the problems above (in particular, it would potentially confuse
programmers who see a local name and think it is a global name).

#### Alternative Solutions

Other programming languages solve this problem by confusing rules about name
shadowing, where names implicitly override other names in certain scopes. This
causes the Name Conflicts problem that we are explicitly trying to solve.

The original syntax I imagined for referring to inner definitions looked more
like: `trigger<fqun:/drawings/graph::graph::x_axis::draw>`. That is easier to
type. Unfortunately that allows for ambiguity, because the name `x_axis` could
be a `trigger`, it could be a `potential_form`, it could be anything. So that
syntax simply can't be used in Define.

## Forward Compatibility

Because there is no possible ambiguity in what a name refers to, all names can
be deterministically refactored inside of a program. This means we could change
the name format to any other format, in the future.

## Refactoring Existing Systems

It would be impossible to deterministically refactor all existing systems
without these restrictions, which is why this has to be part of the language
from the start.
