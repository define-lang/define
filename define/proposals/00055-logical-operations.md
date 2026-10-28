# Define Language Proposal 55: Logical Operations

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** October 26, 2026
- **Date Finalized:**

## Problems

Define needs to be able to set constraints on values and prove facts about those
values. This is relatively easy when you are setting a value. "I set this value
to 50." "Do the constraints allow the number 50?" It's more complex when the
value has gone through operations---we have to be able to reason about what
value operations do in order for the compiler to know if each operation is safe.

For example, if I have `operation<standard:/number/natural/add>` and I have one
value that can be from 0 - 5 and another that can be from 0 - 10, I have to know
that the new possible bounds are 0 - 15 after that operation.

This gets us into a whole host of problems.

Note: For extensive background research and principles around all of this, see
[Numeric Operation Requirements](background/numeric-operation-requirements.md).

### 1: Optimization and Encodings

The compiler is supposed to pick the best encoding for a value
([DLP 39: Value Types](00039-value-types.md),
[DLP 46: Value Encodings](00046-value-encodings.md)).

If it knows the result of an addition can only ever be 0 to 15, it could pick an
8-bit encoding (or even a 4-bit one, if some hardware wanted that). If all it
knows is "some natural number," it has to assume the number could be infinitely
large.

This is basically the same insight that [MLIR](https://mlir.llvm.org/) is built
on. (MLIR is a compiler framework from the LLVM project that keeps high-level
operations around while it lowers them to hardware.) You want to keep knowing
what logical operation is happening while you optimize, not just which
instruction is running.

### 2: Syntax

How do we even write down what an operation means?

In a traditional language or most existing automated verification systems, the
answer has been mathematical syntax: `result = a + b`. In Define, that has a few
problems:

1. It looks wildly different than the rest of Define's syntax.
2. It would require a whole different parser infrastructure just to parse these
   expressions.
3. It does not surrender to trivial static analysis (grep and sed).

### 3: Reasoning About Views

We know that operations have views. When the compiler reasons about the behavior
of an operation, how does it take each of those views into account without us
having to write custom code in the compiler for every value operation?

For example, if I have `view<a>` and `view<b>` as inputs to
`operation<standard:/number/natural/add>`, and `view<result>` as the output, how
does the compiler know what to do with `view<a>` and `view<b>` when it logically
is running addition? You and I know that those are two operands, but the
compiler doesn't know that at all.

Some operations also have more than one output, like an operation that gives you
both the quotient and the remainder of a division, so how does the compiler know
what goes where?

### 4: Composition

Some operations are a combination of other logical operations, like "multiply
and then add." Logically, that's two separate logical operations, even if in
hardware sometimes it's just one (a fused multiply-add).

How do we say that one value operation is a composition of various logical
operations? Do we have to invent some whole custom expression language? Do we
need to re-use the mathematical syntax that other verification systems use, like
Dafny?

### 5: Decidability

Languages like Lean solve this problem by defining all operations through
recursion. However, this creates a system that cannot itself be fully statically
analyzed, because it is undecidable (dependent types).

In reality the Lean compiler implements things like addition in some fashion
using hardware instructions, anyway. (It guarantees its behavior is identical to
the recursive def, but there's still a real physical operation under there
somewhere.)

Also, using pure logical definitions like Lean does requires Lean to do things
like use a bignum implementation for almost all numbers, something that would be
abhorrent to us as a language shooting for maximum optimization potential.

### 6: Associating Value Qualities with Logical Operations

Let's say that a value operation declares that it's doing `view<a> + view<b>`.
How does the compiler know that addition is a valid logical operation for those
two operands? And how does it know that the sum may be written to the view that
receives it?

### 7: Operands That Are the Same View

One of Define's restrictions is that views may not alias: two views in one
Operation Arguments Block may not look at the same position. This rule exists to
make static analysis tractable, because one of the most common issues that makes
analysis intractable is allowing pointer aliasing, and views are somewhat
similar to pointers (sufficiently similar that most of the same analysis issues
would apply).

The core problem is that if two views looked at the same position, a write to
one view's value could change what another view reads.

However, logical operations often need to operate on the same value more than
once. For example, squaring a number multiplies a value by itself. That's fine
to write out as a value operation (you just give it the input number and a place
to put the result), but as a logical operation you have to reason through
`x * x` where the same value (and thus the same view) is multiple operands.

This gets us into a well-known problem in interval arithmetic, called the
"dependency problem" (described by Ramon Moore, who is widely considered the
founder of interval arithmetic, in the 1960's). Stated simply: when the same
value appears more than once in a calculation, interval arithmetic treats each
appearance as if it were a different, independent value.

The classic example is `x − x` with x being allowed to have a range of 0 to 10:

- The true answer is always 0.
- Naive interval arithmetic on `a - b` computes "anything from 0 to 10, minus
  anything from 0 to 10" and gets −10 to 10. It doesn't know `a` and `b` are
  actually both `x`.

Squaring also has the problem, and in a way that has other important
consequences. Imagine that you have a function that looks like `multiply(a, b)`
and you want to call it like `multiply(x, x)`. (That is, you want to square
`x`.) If all the compiler knows is that each operand is somewhere from -3 to 5,
it has to assume that the result of the `multiply` could be anything from -15
to 25. However, in our case the real answer is that the value can only be
between 0 to 25, which is especially important because it eliminates the sign of
the result (which can matter for the precision of later calculations).

In other words, it's actually important for the compiler to be able to see that
two operands have the same value.

How do we square that against the intractability issues around aliasing?

### 8: Intermediate Values

Sometimes one value operation could be composed of many logical operations that
transform the same piece of data multiple times. For example, the absolute
difference of two natural numbers (how far apart they are) is one instruction on
a lot of hardware, but as logical operations it's two steps: subtract b from a,
then take the absolute value of that, or compare b and a and then order the
subtraction based on which one is larger.

In order to express that, you need multiple steps, and they have to store their
intermediate results somewhere. Like, logically, if we wrote it out very
pedantically, it would look like:

```python
def absolute_difference(a: int, b: int):
    x = a - b
    return abs(x)
```

Currently, a Value Operation's Operation Statement Block cannot express the step
there that stores `a - b` in `x`, because it cannot express a storage location
for an intermediate value. It _does_ have its interface views, and it can write
to its output views. So theoretically, it could store an intermediate result in
its output view, and just keep operating on that.

However, an intermediate value isn't always legal in the output view. In the
above example, `absolute_difference` returns a natural number (so the output
view would be a `value<standard:/number/natural>` in Define). However, the
intermediate value could be negative, so it can't logically go there.

There are also compositions that need more intermediate values at once than the
operation has output views. A saturating add (add two numbers, but stop at a
limit, like 255) is also one instruction on a lot of hardware. However, as a set
of logical operations, it's three steps:

1. add a and b
2. compare the sum to 255
3. use that truth value to pick either the sum or 255.

When the third step happens, the sum and the truth value both have to exist, but
there's only one output view. (Plus, as before, the truth value is a
`value<standard:/boolean>`, not a number at all.)

There's also an issue when it comes to precision. Sometimes an intermediate
value has to stay exact without forcing the compiler to store it. A fused
multiply-add (`a * b + c`) is one instruction on most hardware, and as logical
operations it's a multiply and then an add. However, the product could be wider
than the output's encoding allows, even when the result fits.

For example, imagine the output is limited to being an 8-bit signed integer.
With `a` as 100, `b` as 200, and `c` as -19,950, the result is 50, but the
intermediate product of `a` and `b` is 20,000.

If every intermediate value was forced into some fixed encoding, these would
either give the wrong answer or couldn't be done in one instruction.

## Solution

We add a new name type, `logical_operation`, and remove
`execute the encoding operation` from the language. We change how encoding
operations are associated to code the programmer writes in their normal business
logic.

The compiler can now determine the logical meaning of any value operation
entirely from the statements in its Operation Statements Block.

### Logical Operations

A "logical operation" is a way of expressing what a value operation is doing
logically. It exists so that the compiler can reason about the behavior of a
program at compile time.

Define attempts to guarantee that logical operations are a sound representation
of what a program will actually do at runtime. We also strive for (but do not
guarantee) precision (meaning that they are an _exact_ representation of what
will occur and that the constraints they express are exactly the real runtime
constraints).

### Defining Logical Operations

Logical operations are global names defined in the global scope, like this:

```define
define the logical_operation<standard:/number/add> {
    define the view<a> {
        it is read.
    }
    define the view<b> {
        it is read.
    }
    define the view<result> {
        it is written.
    }
}
```

As you can see, logical operations define only a set of views, and each view
definition has only View Direction Statements and no Quality Assignment Block.

### Compiler Integration

Even though they are names in the standard library, the compiler has to know
what every logical operation means. In other words, they are actually part of
the compiler, not really part of the standard library.

This is the only place where the compiler and the standard library are truly
coupled, at the moment. (Though it will probably also couple a few value
qualities in the standard library to the compiler, like
`value<standard:/boolean>`, too, once we start specifying some core logical
operations.)

In the future, we may support allowing developers to define their own logical
operations, and including code that extends the compiler so that it can reason
about those logical operations at compile time.

The compiler throws an error if a program attempts to use a logical operation
that it doesn't know about.

### Executing Logical Operations

Logical Operations can be executed inside of the Operation Statements Block of a
Value Operation. Their execution syntax is basically the same as all our other
execution syntax:

```define
execute the logical_operation<standard:/number/add> {
    with view<a> looking at view<a>.
    with view<b> looking at view<b>.
    with view<result> looking at view<result>.
}
```

This is called a Logical Operation Execution Statement.

The arguments block follows all the same rules as every other Operation
Arguments Block, except that logical operations have no value qualities or
encodings, so there's no matching required.

The direction rules from
[DLP 54 (View Direction Statements)](00054-view-direction-statements.md) apply
to logical operations too. A logical operation may not write to an input-only
view of the value operation, and it may not read from an output-only view or a
local view (see below) unless an earlier statement has already written to it.

Logical operations _must_ have at least one output view. (That rule is not true
of other operation types, which could be just sending something out and
receiving nothing in return.)

### Literals in Logical Operations Executions

For now, the compiler must be aware of every literal type used in a logical
operation's Operation Arguments Block and know how to translate it for that
logical operation. In the future, we will have a way to convert literals into
something a logical operation can use, more generically, allowing for people to
create and use their own literals.

### Value Qualities Declare What Logical Operations They Support

A value quality now must have a block. We add a new type of statement, called a
"Logical Operation Support Statement." It says that a logical operation may
operate on views with this value quality. Each line says whether it is supported
as an input view, an output view, or both, for the logical operation. It looks
like this:

```define
define the potential value<standard:/number/natural> {
    it supports the logical_operation<standard:/number/absolute_value> {
        it may be written.
    }
    it supports the logical_operation<standard:/number/add> {
        it may be read.
        it may be written.
    }
    it supports the logical_operation<standard:/number/equality> {
        it may be read.
    }
}
```

Logical Operation Support Statements must be in alphabetical order by the name
of the logical operation, and each logical operation may only be listed once.

A value quality may support any logical operations it wants. Supporting a
logical operation is a statement about what the value quality's values _are_. A
value quality that supports `standard:/number/add` is saying its values can be
added like rational numbers (and thus it guarantees that there will be encoding
operations that support that).

If a logical operation's Operation Arguments Block references a view with any
unsupported value quality on it, the compiler throws an error.

### Logical Operations Can Have Mixed Value Qualities

The input views of a logical operation don't have to all have the same value
quality. For example, naturals and integers will both support
`standard:/number/add`, so you can add a natural and an integer via that logical
operation (because it is logically rational number addition). The output views
don't have to match the input views either: the sum of a natural and an integer
can be written to an integer.

### Local Views

An Operation Statements Block for a Value Operation may define local views, the
same way an Action Statements Block may define local positions. A local view
holds an intermediate value in the middle of an operation:

```define
define the view<negated_b> {
    it may only contain particles where {
        it has the value<standard:/number/integer>.
    }
}
```

A local view has no direction--it is always both read and written, logically. In
fact, if it is not both read and written, it is dead code.

Local views must be assigned a value quality, like interface views.

A local view is not _conceptually_ like an interface view. It does not create a
particle or point to a real particle. Conceptually, it represents a symbol in
the universe of the programmer (the view point).

It is simply a way of providing a name to an intermediate step of a
transformation that a value operation is performing. Conceptually, Define still
considers that the entirety of the value operation happens atomically, and that
these intermediate views do not "exist" as a realized part of the program.

Just like with local positions, a local view must be defined before any
statement that refers to it.

It's worth reiterating here that Define expects Value Operations to be defined
very rarely, primarily in the Define Standard Library, and that most logic in a
program should be written through actions, so these intermediate views remain a
specialized way of expressing _logic_, not _programs_.

### Single Assignment

To simplify analysis, within an Operation Statements Block, any given name must
only refer to one value. (Not just one `value` quality or something like that,
but one actual value.)

The way that we enforce this is that we require Operation Statements Blocks to
be written in a form very similar to a compiler's Static Single Assignment form.
This enforces a set of rules on how and when views may be written and read:

| View                       | Written by            | Read by                    |
| -------------------------- | --------------------- | -------------------------- |
| Input-only interface view  | No statement          | Any statement              |
| Output-only interface view | Exactly one statement | Statements after that one  |
| Read/write interface view  | Exactly one statement | Statements before that one |
| Local view                 | Exactly one statement | Statements after that one  |

There is one exception: a Value Operation may execute another Value Operation
that has a read/write interface view. In that case, we can send any of _our_
read/write interface views to that Value Operation's read/write interface view
as part of an Operation Execution Statement that executes that other Value
Operation. The executed operation follows these same rules, so it inherently
reads the value before it writes the new one. In this situation, this does
"count" as a write to the interface view, though, so after that point it may not
be read or written further.

As an example, here's a saturating subtraction that subtracts `view<b>` from
`view<a>` in place (storing the result in `view<a>`), stopping at 0, and says
whether it had to stop. This isn't really _good_ code, it's just one that shows
an example of all the rules in the table above, with comments explaining the
rules and how they apply:

```define
define the operation<mv:example.com:example:/saturating_subtract> {
    # Read/write: statements may only read view<a> before the statement that
    # writes it (or in it, when it passes view<a> to a read/write view of an
    # operation it executes), so every read means the value the operation was
    # given.
    define the view<a> {
        it is read.
        it is written.
        it may only contain particles where {
            it has the value<standard:/number/natural>.
        }
    }
    # Input-only: no statement may write view<b>, and any statement may read
    # it.
    define the view<b> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/number/natural>.
        }
    }
    # Output-only: exactly one statement must write view<saturated>, and only
    # statements after that one may read it.
    define the view<saturated> {
        it is written.
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }

    it does {
        # This reads view<a> before the last statement writes it, and it's the
        # one statement that writes view<saturated>.
        execute the logical_operation<standard:/number/less_than> {
            with view<a> looking at view<a>.
            with view<b> looking at view<b>.
            with view<result> looking at view<saturated>.
        }
        # Every local view is written by exactly one statement, and only read by
        # statements after that one.
        define the view<negated_b> {
            it may only contain particles where {
                it has the value<standard:/number/integer>.
            }
        }
        # Reading view<b> again is fine, because it's input-only.
        execute the logical_operation<standard:/number/negate> {
            with view<a> looking at view<b>.
            with view<result> looking at view<negated_b>.
        }
        # A difference can be negative, so this is an integer, not a natural.
        define the view<difference> {
            it may only contain particles where {
                it has the value<standard:/number/integer>.
            }
        }
        # This is the last statement that reads view<a>.
        execute the logical_operation<standard:/number/add> {
            with view<a> looking at view<a>.
            with view<b> looking at view<negated_b>.
            with view<result> looking at view<difference>.
        }
        # To stop at 0, the result is the larger of view<difference> and 0.
        # We pretend that there's no "maximum" logical operation, so the
        # next three statements flip the sign, take the smaller of that and
        # 0, and take the absolute value of that.
        define the view<negated_difference> {
            it may only contain particles where {
                it has the value<standard:/number/integer>.
            }
        }
        execute the logical_operation<standard:/number/negate> {
            with view<a> looking at view<difference>.
            with view<result> looking at view<negated_difference>.
        }
        define the view<smaller> {
            it may only contain particles where {
                it has the value<standard:/number/integer>.
            }
        }
        execute the logical_operation<standard:/number/minimum> {
            with view<a> looking at view<negated_difference>.
            with view<b> looking at literal<standard:/number>"0".
            with view<result> looking at view<smaller>.
        }
        # This is the one statement that writes view<a>, and no statement after
        # it may read view<a>. An absolute value is never negative, so it fits
        # in a natural.
        execute the logical_operation<standard:/number/absolute_value> {
            with view<a> looking at view<smaller>.
            with view<result> looking at view<a>.
        }
    }
}
```

### Setting Values in Operations

A View Setting Statement may now appear in an Operation Statements Block. It is
simply a Value Setting Statement with views instead of positions:

```define
set the value of view<local> to view<input>.
```

Conceptually, this is the logical "identity" operation ("these two values are
the same value").

It has the same rules as a Value Setting Statement would follow. In particular,
both views must have the same value quality. The direction rules from
[DLP 54 (View Direction Statements)](00054-view-direction-statements.md) and the
Single Assignment rules from this proposal apply to it like any other statement
that appears in a Value Operation. A View Setting Statement is considered to
read from its source and write to its target.

#### View Setting Statement Restrictions

View Setting Statements have only two purposes:

1. De-aliasing a local or interface view to be able to pass it twice to the same
   Logical Operation or Value Operation.
2. Writing back to a read/write interface view after reading from it in an
   operation and writing that operation's result to a local view. (Like adding
   `1` to `view<value>` and storing it in `view<sum>`, and then doing
   `set the value of view<value> to view<sum>.`)

No other uses of View Setting Statements are allowed. This gives us a few rules.

When the target of a View Setting Statement is a **local view**, the source and
target must then be referenced in the same Logical Operation Execution Statement
or Operation Execution Statement together, which must be the next statement
after any following View Setting Statements.

When the target is a **read/write interface view**, the source must be from a
local view that was written by an operation that also read that same
**read/write interface view**, and must come immediately after that operation
(following any other View Setting Statements).

The source of a View Setting Statement may not be a literal.

The source of any View Setting Statement must never have been the target of
another View Setting Statement.

No other View Setting Statements are allowed.

To be clear, where we say "source" and "target" above, we mean the actual
_names_, not the values within them.

### Logical Operation Views Also May Not Alias

Define's "Views May Not Alias" rule applies to logical operation executions
exactly as it does to value operation and encoding operation executions. No two
views of one Logical Operation Execution Statement may look at the same view.

If you need to express that one value appears twice in the same logical
operation, you can express it via a View Setting Statement to "copy" the value
from one view to another. For example, here's a "square" value operation:

```define
define the operation<mv:example.com:example:/square> {
    define the view<a> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/number/integer>.
        }
    }
    define the view<result> {
        it is written.
        it may only contain particles where {
            it has the value<standard:/number/integer>.
        }
    }

    it does {
        define the view<copy_of_a> {
            it may only contain particles where {
                it has the value<standard:/number/integer>.
            }
        }
        set the value of view<copy_of_a> to view<a>.
        # view<a> and view<b> look at two different views, so they don't
        # alias, even though they have the same value.
        execute the logical_operation<standard:/number/multiply> {
            with view<a> looking at view<a>.
            with view<b> looking at view<copy_of_a>.
            with view<result> looking at view<result>.
        }
    }
}
```

In this way, the compiler can still see that the two values are the same through
inference, when it needs to, but the validator still enforces that names may not
be identical within the Operation Arguments Block by purely looking at the
structure of the block.

### Encoding Operations

Encoding Operations still do the actual work at runtime. Since there is no
longer a statement that says "execute the Encoding Operation for this value
operation," the config from
[DLP 48 (Encoding Operation Associations)](00048-encoding-operation-associations.md)
now associates Encoding Operations with logical operations, instead. An entry
has `logical_operation`, now, instead of `value_operation`:

```protocol-buffer-text-format
encoding_operations: {
    operation_encodings: [
        {
            logical_operation: "standard:/number/add"
            encoding_operation: "/number/integer/64bit/add"
        },
    ]
}
```

An Encoding Operation associated with a logical operation must have the same
views as the logical operation, with the same names and directions, in the same
order.

For each executed value operation, the compiler compiles the value operation's
statements, choosing an Encoding Operation for each logical operation execution
based on the encodings of what its views look at.

The compiler may also recognize a composition of logical operations and use an
Encoding Operation that does all of it at once. Future proposals will provide a
more comprehensive way for the compiler to understand when and how it can do
this.

#### Trust

The compiler trusts that an Encoding Operation actually implements the meaning
of the logical operation it's associated with. If an Encoding Operation does
something different from that meaning, that's a soundness error in that Encoding
Operation or in the compiler's implementation of the logical operation.

As a result, it is highly recommended to formally prove the equivalence of every
encoding operation to its logical operation's declared behavior.

## A Real Program

### Standard Operations

Here are some stripped-down examples of value types and logical operations
(these are also used by later examples in this proposal).

```define
define the potential value<standard:/number/natural> {
    it supports the logical_operation<standard:/number/add> {
        it may be read.
        it may be written.
    }
    it supports the logical_operation<standard:/number/less_than> {
        it may be read.
    }
    it supports the logical_operation<standard:/number/multiply> {
        it may be read.
        it may be written.
    }
    it supports the logical_operation<standard:/number/negate> {
        it may be read.
    }
    it supports the logical_operation<standard:/number/power> {
        it may be written.
    }
}

define the potential value<standard:/number/integer> {
    it supports the logical_operation<standard:/number/add> {
        it may be read.
        it may be written.
    }
    it supports the logical_operation<standard:/number/less_than> {
        it may be read.
    }
    it supports the logical_operation<standard:/number/minimum> {
        it may be read.
        it may be written.
    }
    it supports the logical_operation<standard:/number/multiply> {
        it may be read.
        it may be written.
    }
    it supports the logical_operation<standard:/number/negate> {
        it may be read.
        it may be written.
    }
    it supports the logical_operation<standard:/number/power> {
        it may be read.
    }
}

define the potential value<standard:/boolean> {
    it supports the logical_operation<standard:/number/less_than> {
        it may be written.
    }
}

define the operation<standard:/number/natural/add> {
    define the view<a> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/number/natural>.
        }
    }
    define the view<b> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/number/natural>.
        }
    }
    define the view<result> {
        it is written.
        it may only contain particles where {
            it has the value<standard:/number/natural>.
        }
    }

    it does {
        execute the logical_operation<standard:/number/add> {
            with view<a> looking at view<a>.
            with view<b> looking at view<b>.
            with view<result> looking at view<result>.
        }
    }
}

define the operation<standard:/number/natural/subtract> {
    define the view<a> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/number/natural>.
        }
    }
    define the view<b> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/number/natural>.
        }
    }
    define the view<result> {
        it is written.
        it may only contain particles where {
            it has the value<standard:/number/integer>.
        }
    }

    it does {
        define the view<negated_b> {
            it may only contain particles where {
                it has the value<standard:/number/integer>.
            }
        }
        execute the logical_operation<standard:/number/negate> {
            with view<a> looking at view<b>.
            with view<result> looking at view<negated_b>.
        }
        execute the logical_operation<standard:/number/add> {
            with view<a> looking at view<a>.
            with view<b> looking at view<negated_b>.
            with view<result> looking at view<result>.
        }
    }
}

define the operation<standard:/number/natural/increment> {
    define the view<value> {
        it is read.
        it is written.
        it may only contain particles where {
            it has the value<standard:/number/natural>.
        }
    }

    it does {
        define the view<sum> {
            it may only contain particles where {
                it has the value<standard:/number/natural>.
            }
        }
        execute the logical_operation<standard:/number/add> {
            with view<a> looking at view<value>.
            with view<b> looking at literal<standard:/number>"1".
            with view<result> looking at view<sum>.
        }
        set the value of view<value> to view<sum>.
    }
}

define the operation<standard:/number/natural/greater_than> {
    define the view<a> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/number/natural>.
        }
    }
    define the view<b> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/number/natural>.
        }
    }
    define the view<result> {
        it is written.
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }

    it does {
        # a > b is b < a.
        execute the logical_operation<standard:/number/less_than> {
            with view<a> looking at view<b>.
            with view<b> looking at view<a>.
            with view<result> looking at view<result>.
        }
    }
}

define the operation<standard:/number/integer/maximum> {
    define the view<a> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/number/integer>.
        }
    }
    define the view<b> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/number/integer>.
        }
    }
    define the view<result> {
        it is written.
        it may only contain particles where {
            it has the value<standard:/number/integer>.
        }
    }

    it does {
        # The maximum of a and b is the negation of the minimum of -a and -b.
        define the view<negated_a> {
            it may only contain particles where {
                it has the value<standard:/number/integer>.
            }
        }
        execute the logical_operation<standard:/number/negate> {
            with view<a> looking at view<a>.
            with view<result> looking at view<negated_a>.
        }
        define the view<negated_b> {
            it may only contain particles where {
                it has the value<standard:/number/integer>.
            }
        }
        execute the logical_operation<standard:/number/negate> {
            with view<a> looking at view<b>.
            with view<result> looking at view<negated_b>.
        }
        define the view<smaller> {
            it may only contain particles where {
                it has the value<standard:/number/integer>.
            }
        }
        execute the logical_operation<standard:/number/minimum> {
            with view<a> looking at view<negated_a>.
            with view<b> looking at view<negated_b>.
            with view<result> looking at view<smaller>.
        }
        execute the logical_operation<standard:/number/negate> {
            with view<a> looking at view<smaller>.
            with view<result> looking at view<result>.
        }
    }
}

define the operation<standard:/number/integer/square> {
    define the view<a> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/number/integer>.
        }
    }
    define the view<result> {
        it is written.
        it may only contain particles where {
            it has the value<standard:/number/natural>.
        }
    }

   it does {
        # The square of any integer is never negative, so it fits in a natural.
        execute the logical_operation<standard:/number/power> {
            with view<a> looking at view<a>.
            with view<b> looking at literal<standard:/number>"2".
            with view<result> looking at view<result>.
        }
    }
}
```

### Comparing

```define
define the operation<standard:/number/integer/has_opposite_signs> {
    define the view<a> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/number/integer>.
        }
    }
    define the view<b> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/number/integer>.
        }
    }
    define the view<result> {
        it is written.
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }

    it does {
        # Two integers have opposite signs exactly when their product is
        # negative.
        define the view<product> {
            it may only contain particles where {
                it has the value<standard:/number/integer>.
            }
        }
        execute the logical_operation<standard:/number/multiply> {
            with view<a> looking at view<a>.
            with view<b> looking at view<b>.
            with view<result> looking at view<product>.
        }
        execute the logical_operation<standard:/number/less_than> {
            with view<a> looking at view<product>.
            with view<b> looking at literal<standard:/number>"0".
            with view<result> looking at view<result>.
        }
    }
}
```

That's not the most _efficient_ way to logically calculate that two things have
opposite signs, but it is a logically accurate way to do it.

### A Fused Multiply-Add

```define
define the operation<mv:example.com:example:/multiply_add> {
    define the view<factor_a> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/number/integer>.
        }
    }
    define the view<factor_b> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/number/integer>.
        }
    }
    define the view<addend> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/number/integer>.
        }
    }
    define the view<result> {
        it is written.
        it may only contain particles where {
            it has the value<standard:/number/integer>.
        }
    }

    it does {
        define the view<product> {
            it may only contain particles where {
                it has the value<standard:/number/integer>.
            }
        }
        execute the logical_operation<standard:/number/multiply> {
            with view<a> looking at view<factor_a>.
            with view<b> looking at view<factor_b>.
            with view<result> looking at view<product>.
        }
        execute the logical_operation<standard:/number/add> {
            with view<a> looking at view<product>.
            with view<b> looking at view<addend>.
            with view<result> looking at view<result>.
        }
    }
}
```

### A Composed Operation

The compiler could derive here that `view<result>` is `view<value> + 1 + 1` by
looking down into the logical operations that are executed here, transitively.

```define
define the operation<mv:example.com:example:/add_two> {
    define the view<value> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/number/natural>.
        }
    }
    define the view<result> {
        it is written.
        it may only contain particles where {
            it has the value<standard:/number/natural>.
        }
    }

    it does {
        define the view<plus_one> {
            it may only contain particles where {
                it has the value<standard:/number/natural>.
            }
        }
        execute the operation<standard:/number/natural/add> {
            with view<a> looking at view<value>.
            with view<b> looking at literal<standard:/number>"1".
            with view<result> looking at view<plus_one>.
        }
        execute the operation<standard:/number/natural/add> {
            with view<a> looking at view<plus_one>.
            with view<b> looking at literal<standard:/number>"1".
            with view<result> looking at view<result>.
        }
    }
}
```

### Updating a View in Place

Executing an operation that has a read/write view can read and write a
read/write view of the operation that executes it, in one statement.

```define
define the operation<mv:example.com:example:/count_one_more> {
    define the view<count> {
        it is read.
        it is written.
        it may only contain particles where {
            it has the value<standard:/number/natural>.
        }
    }

    it does {
        execute the operation<standard:/number/natural/increment> {
            with view<value> looking at view<count>.
        }
    }
}
```

### Errors

```define
define the operation<mv:example.com:example:/bad_boolean_sum> {
    define the view<a> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }
    define the view<b> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }
    define the view<result> {
        it is written.
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }

    it does {
        # Error: value<standard:/boolean> may not be read by
        # logical_operation<standard:/number/add>.
        execute the logical_operation<standard:/number/add> {
            with view<a> looking at view<a>.
            with view<b> looking at view<b>.
            with view<result> looking at view<result>.
        }
    }
}

define the potential value<mv:example.com:example:/user_id> {
    it supports the logical_operation<standard:/number/equality> {
        it may be read.
    }
}

define the operation<mv:example.com:example:/bad_next_user_id> {
    define the view<a> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/number/natural>.
        }
    }
    define the view<result> {
        it is written.
        it may only contain particles where {
            it has the value<mv:example.com:example:/user_id>.
        }
    }

    it does {
        # Error: value<mv:example.com:example:/user_id> may not be written by
        # logical_operation<standard:/number/add>.
        execute the logical_operation<standard:/number/add> {
            with view<a> looking at view<a>.
            with view<b> looking at literal<standard:/number>"1".
            with view<result> looking at view<result>.
        }
    }
}

define the operation<mv:example.com:example:/bad_double_write> {
    define the view<factor_a> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/number/integer>.
        }
    }
    define the view<factor_b> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/number/integer>.
        }
    }
    define the view<addend> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/number/integer>.
        }
    }
    define the view<result> {
        it is written.
        it may only contain particles where {
            it has the value<standard:/number/integer>.
        }
    }

    it does {
        execute the logical_operation<standard:/number/multiply> {
            with view<a> looking at view<factor_a>.
            with view<b> looking at view<factor_b>.
            with view<result> looking at view<result>.
        }
        # Error: view<result> was already written by the statement above. The
        # product belongs in a local view.
        execute the logical_operation<standard:/number/add> {
            with view<a> looking at view<result>.
            with view<b> looking at view<addend>.
            with view<result> looking at view<result>.
        }
    }
}

define the operation<mv:example.com:example:/bad_read_after_write> {
    define the view<value> {
        it is read.
        it is written.
        it may only contain particles where {
            it has the value<standard:/number/natural>.
        }
    }
    define the view<result> {
        it is written.
        it may only contain particles where {
            it has the value<standard:/number/natural>.
        }
    }

    it does {
        define the view<sum> {
            it may only contain particles where {
                it has the value<standard:/number/natural>.
            }
        }
        execute the logical_operation<standard:/number/add> {
            with view<a> looking at view<value>.
            with view<b> looking at literal<standard:/number>"1".
            with view<result> looking at view<sum>.
        }
        set the value of view<value> to view<sum>.
        # Error: view<value> was written by the statement above, so reading it
        # here could mean either value.
        execute the logical_operation<standard:/number/add> {
            with view<a> looking at view<value>.
            with view<b> looking at literal<standard:/number>"1".
            with view<result> looking at view<result>.
        }
    }
}

define the operation<mv:example.com:example:/bad_square> {
    define the view<a> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/number/integer>.
        }
    }
    define the view<result> {
        it is written.
        it may only contain particles where {
            it has the value<standard:/number/natural>.
        }
    }

    it does {
        # Error: view<a> and view<b> both look at view<a>, and views may not
        # alias.
        execute the logical_operation<standard:/number/multiply> {
            with view<a> looking at view<a>.
            with view<b> looking at view<a>.
            with view<result> looking at view<result>.
        }
    }
}

define the operation<mv:example.com:example:/bad_reference> {
    define the view<result> {
        it is written.
        it may only contain particles where {
            it has the value<standard:/number/natural>.
        }
    }

    it does {
        execute the logical_operation<standard:/number/add> {
            # Error: view<result> is output-only and nothing has written to it
            # yet.
            with view<a> looking at view<result>.
            with view<b> looking at literal<standard:/number>"1".
            with view<result> looking at view<result>.
        }
    }
}

define the operation<mv:example.com:example:/bad_overwrite> {
    define the view<a> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/number/integer>.
        }
    }
    define the view<result> {
        it is written.
        it may only contain particles where {
            it has the value<standard:/number/integer>.
        }
    }

    it does {
        execute the logical_operation<standard:/number/negate> {
            with view<a> looking at view<a>.
            with view<result> looking at view<result>.
        }
        # Error: view<a> is input-only, so nothing may write to it.
        execute the logical_operation<standard:/number/negate> {
            with view<a> looking at view<result>.
            with view<result> looking at view<a>.
        }
    }
}
```

## Why This is the Right Solution

Boy oh boy did this involve a lot of research, time, and reasoning. There are a
ton of ways we could have implemented this.

### Why Not Math Syntax?

Math syntax is compact, and everybody knows what an infix expression like
`a + b` means. It's what most programming languages have chosen to express
mathematical operations. However, in Define, it would have a few problems.

The most important problem is that the meaning of each symbol is entirely
contextual. I cannot tell if `+` means saturating addition, wrapping addition,
overflow-checking addition, or what. It can be made statically knowable, but
then that also fixes the meaning of that `+` to only one meaning for all of
time.

That gets us into our next problem: forward compatibility. Using mathematical
syntax puts a huge amount of meaning into a very small symbol, which is, in
general, a forward compatibility risk. One of the reasons that Define chooses to
be so verbose is that we are much less likely to have to change our mind about
something like "execute the logical_operation" than we are about something like
`()` as execution syntax.

Symbols are also much more likely to conflict with other symbols that have a
different meaning in a different location, which complicates our parser and
makes it harder for us to provide good error messages to the user (it's much
easier to parse and provide clear error messages if every pattern of symbols in
the program has exactly one meaning and is used in exactly one situation, or
where the situations in which those symbols are used are so similar that you'd
be providing basically the same error message anyway).

One of the less important reasons is a stylistic issue and a consistency issue,
which is that the rest of Define reads more like English sentences, and math
syntax is not English sentences.

An infix expression language would also bring in precedence rules, parentheses,
and a whole second way of reading code. It would be an extra language inside of
the language. There are a ton of parsing libraries for this, but it's still
harder and slower to parse than the rest of Define.

Applying statements in order gets us composition without any of that. The fused
multiply-add above is two statements, each of which does one thing, and you read
them top to bottom like every other block in Define. It's obnoxious to read and
horrible to write, but it works very well for what we are trying to do.

### Why a Name Type?

When I first designed this system, logical operations had a special syntax that
went inside of a block after `execute the encoding operation`. It looked like
`with view<result> set to the sum of view<a> plus view<b>.` That read nicely,
but every logical operation needed its own grammar (because they could all have
different views) and the parser and compiler needed new code for each one.

That syntax also would have made it very hard to support extending the
compiler's logical operations in the future, something I hope to be able to do
later.

The syntax was especially awkward when you had more than one output view on an
operation. I don't expect that to be common, for logical operations, but we
couldn't box ourselves into a corner and basically forbid it in the syntax of
the language itself.

Using a name type and the `execute the` syntax gives us exactly the syntax and
semantics we have for our other operation types, very similar forward
compatibility guarantees, much simpler parsing, etc.

Also, using the full name system gives us an organizing principle where you can
see how logical operations are related to each other (there's a set of name ops,
a set of boolean ops, etc.). Plus, it makes grepping for things simpler; all
operations are shaped the same way and you just are looking for a known name
type that you'll never see anywhere else in the language (other than perhaps
inside a literal or comment).

The weird part about using a name type is that the compiler has to know the name
exists, so why allow what looks like extensibility? Well, I think some day we
actually will allow compiler extensions that define other logical operations, so
even that objection goes away. It would be a bit of speculative generality,
though, if that was the only reason. Since we have the other reasons above, I
feel more comfortable with the decision.

### Why Remove `execute the encoding operation`?

Essentially, the reason here was that `execute the encoding operation` doesn't
actually do what we need.

If our goal is maximum optimization, the compiler needs to be able to reason
through the whole program and choose how to combine logical operations into
hardware operations, in any pattern. It's not just mapping a single value
operation to a single encoding operation, although it often will be, especially
for our lowest-level value operations. At some level it's going to have to
involve reading the whole DAG of logical operations and deciding what the best
form is for that to go into the hardware.

Now that we _have_ logical operations, it made more sense to just specify the
logical operations and the minimum hardware operations that _must_ map to those
(so that you at least _can_ compile a program if the optimizer can't figure it
out). We leave the full power of backend optimization to future proposals, since
we aren't designing the optimization system here (that's too much speculative
generality, too much to fit into one proposal, and way too early in the design
of Define to make those decisions now).

Operations that have no logical meaning (like I/O) were the other reason to tie
operations to Encoding Operations. A future proposal will cover how we solve
that problem.

### Why not declare calculations on the output view?

One design direction I explored was putting a description on each output view
about how that output view was calculated. It would have looked something like
`its value is the sum of view<a> plus view<b>.` in the definition of the output
view.

That brought back all the complexities of custom syntax. It put calculations and
meaning into two different places. It ended up making much more sense to just
have logical operations written out in the logical operations block.

### Declaring what the whole value operation is

Another approach I had explored, early on in the design of logical operations,
was only allowing a value operation to declare that it represents some specific,
single logical operation, like `it implements the logical operation<sum>.`

That gets us into all sorts of trouble. The first is that you then need some
rule to match up the value operation's views with the logical operation's
operands. The next is: what happens when your value operation has to be more
than one logical operation, how do they compose? And then, do you need to just
define one logical operation per value operation, as a result? So then why do we
even have value operations?

So that obviously didn't work.

### Why Local Views?

This solves the Intermediate Values problem. With Single Assignment, an
intermediate result can never go in a view that's written again later. You can't
just keep dumping intermediate results into `view<result>`. There has to be
somewhere else to put them, and potentially many "somewhere else" locations if a
computation gets complex.

Temporarily overwriting an input view also doesn't work. An input view looks at
the caller's position, so writing a value into it would violate the value
operation's guarantees.

It doesn't actually have to _cost_ anything at runtime. The compiler decides how
to compute a local view, and whether to store it at all.

### Why Logical Operations Can't Alias

When I was first working on this it looked like logical operations needed an
exception to the Views May Not Alias rule, so that we could more directly
express things like "multiply this value by itself." Like, perhaps we could
allow input views to alias, provided we didn't write to them separately?

The value of doing that would be that it's much easier to see locally that two
values are the same value, without inference. However, in order to actually know
whether two values _are_ the same value, you'd end up having to do inference
anyway, because there would be situations in which we could prove that two
different positions contain the same value even when they aren't the same
position. So you'd get a shortcut, but then you'd just have to go and implement
the inference anyway.

Forcing Single Assignment and an explicit separate name keeps the Single
Assignment behavior of value operations totally consistent and only requires the
compiler to reason one way about how values flow through a program and what an
Operation Arguments Block means (and what's allowed in it).

Another point here was that I realized that what you actually care about is
_all_ forms of relationships between the two values that are used as operands,
not just whether they're equal. For example, if you know that one is less than
the other, then you can do some optimizations (like eliminate bounds checking on
array access, in the future). Although we can't yet express such relationships,
future DLPs will allow us to.

### Why Single Assignment?

This solves a bunch of problems, primarily standardizing how the language works
so that there is only one way to write the code and giving us a form that we are
confident the compiler can easily analyze.

If a view could be written to more than once, a fused multiply-add could be
implemented in multiple ways:

1. Store the product of `a` and `b` in `result`. Then add `c` to `result` and
   store that back into `result` again.
2. Put the product of `a` and `b` in a local view called `intermediate` and then
   add `c` to `intermediate` and store that in `result`.

With Single Assignment, the product has to go in a local view, so there's only
one way, which we can guarantee will be consistent across all Define programs.

That gets even weirder if you have an intermediate result that doesn't fit into
the result view (like having to temporarily store a negative number for
saturating subtraction even though the result is a natural). So those would
_have_ to use their own local views...except in the rare case where the
intermediate _happened_ to fit...it's just confusing.

Also, with Single Assignment, nobody reading an operation has to ask "which
`view<result>` is this?" In actions, we already differentiate that because we
have particles, but value operations don't see that.

Passing a read/write view to a read/write view of an executed operation is
allowed even though it _looks_ like that one statement both reads and writes it.
In reality, the executed operation follows these same rules: it always reads the
value it was given before it writes the new one. Thus, the rule is never
actually violated.

It is a bit awkward that we don't allow passing _local_ views into a read/write
interface view of a value operation (because it violates single assignment for
them). My suspicion is that the need for this will be rare and this should not
cause too much trouble, but we will see what happens.

This is also how compilers already work inside. LLVM, MLIR, GCC, and most other
optimizing compilers convert programs to _static single assignment_ form (SSA),
where every value is assigned exactly once and every use of a value refers to
exactly one assignment. In SSA, the compiler can follow any value straight to
where it came from, which is what makes analyses like constant propagation,
range analysis, and dead code elimination simple and fast. Converting a normal
program to SSA takes some work, because it has to rename every variable that's
assigned more than once. Programs with branches also need special "φ" (phi)
nodes, which pick a value depending on which branch ran. An Operation Statements
Block with Single Assignment is _already_ in SSA form, and since it has no
branches, it never needs φ nodes. The compiler gets SSA for free, and so does
anybody reading the code.

The cost is that you sometimes have to specify a bunch of local views, and you
might have to depend on compiler errors to tell you what you can and can't do.
That's annoying, but it seemed like the best way to keep value operations
simple.

Once again, I don't expect a ton of value operations to be written, so I'm okay
with imposing even more confusing and draconian restrictions on them than we do
on the rest of Define, especially if it makes compilation faster and simpler, or
makes the program easier to reason about for the compiler.

### Why The View Setting Restrictions?

Originally I just blocked copying from one interface view to another, or copying
from one local view to another.

Copying from one interface view to another is obviously bad. Allowing a direct
copy from one interface view to another lets you write a Value Setting Statement
hidden inside of a Value Operation as a View Setting Statement. It enables two
ways to do the same thing, one of which doesn't make any sense.

For local views the story was a little more complex. Local views were added into
the language to enable Single Assignment, non-aliasing, and intermediate values.
However, forcing that you can't copy between two local views caused an obnoxious
problem that made things worse, not better:

Imagine a value operation `complex_multiply(ar, ai, br, bi)` that does complex
number multiplication, where the `r` variables are the Real components and the
`i` parts are the Imaginary components. It returns
`(ar*br − ai*bi, ar*bi + ai*br)`.

Now imagine for some reason that somebody needed to do something wild like write
a single value operation that adds two complex numbers and squares the sum. In
math syntax that looks like:

```python
zr = wr + vr
zi = wi + vi
(result_r, result_i) = complex_multiply(zr, zi, zr, zi)
```

Uh oh, we pass the same values twice (aliasing)! The only way to write it
without aliasing is to compute the sum again from scratch:

```python
zr = wr + vr
zi = wi + vi
zr2 = wr + vr
zi2 = wi + vi
(result_r, result_i) = complex_multiply(zr, zi, zr2, zi2)
```

Although a compiler could "see through" that specific recomputation and realize
it only needed to do the computation once, what if the second calculation got
written in some way where the compiler couldn't figure that out? A recomputation
of one formula could be any equivalent formula. Recognizing that any two
arbitrary formulas are identical can be computationally expensive, and is
undecidable in the limit. Thus, forcing people to write out recomputations got
us into very difficult optimization territory. Also, it's very easy to write a
recomputation in many different ways, so it also led us down a path of tempting
people to write the same program in more than one way.

Also, it turns out, it wasn't even doing what we needed anyway. You could still
write a totally unnecessary View Setting Statement by setting a local view to
the value of an interface view and then pass that local view to an operation,
for no reason.

It was better to lay out the _purposes_ of View Setting Statements and then come
up with a set of rules that enforced those purposes.

People can still do recomputations, but at the very least, it would now be quite
unnatural to do so.

We ban literals in View Setting Statements because they duplicate what you would
otherwise do with a Value Setting Statement outside of a Value Operation, and I
couldn't think of a legitimate reason for them to exist.

### Why Value Qualities Declare Their Logical Operations

Something has to say what operations are legal on what values. The language has
to have some way to express that you can add naturals and you can't add
booleans.

They're in alphabetical order so there's only one way to write any value
quality's list.

### Why Support Statements Have Direction Statements

We had to add `it may be written` and `it may be read` onto Logical Operation
Support Statements because not all value qualities are valid in both the input
and output of a logical operation. For example, it makes no sense to pass a
natural to an `absolute_value` function, but it certainly can return that type!

I considered having two separate sections instead of making it a block on the
Logical Operation Support Statement. However, what sold me on the current syntax
was limiting the number of times the _name_ of the operation has to be written,
and that basically the lookup the compiler has to do is logically "I see the
name of the operation, now I see the view, now I see what direction the view
allows" so it made sense to structure the syntax for the Support Statement in a
similar way.

I also originally had them say `it is read` and `it is written` like View
Direction Statements, but that just didn't make sense, and they aren't really
the same thing.

## Forward Compatibility

New logical operations can be added without conflicting with anything, because
each one is a distinct name. A value quality can start supporting a new logical
operation by adding a Logical Operation Support Statement, which can't break any
existing program.

The compiler has to know what every logical operation means, so for now, the set
of logical operations will be closed and defined by the compiler.

In the future, we may want a way to extend the compiler with logical operations
that somebody else implements, as machine code that the compiler calls while it
runs (or some other mechanism). `define the logical_operation` already gives us
the syntax for that.

Most value operations won't need an extension at all, though, because anything
that can be written as a sequence of existing logical operations already works.

We've also made the strictest choice about writing views: each view is written
at most once. That can be relaxed later without breaking existing programs.

## Refactoring Existing Systems

Operations in other languages that map to hardware primitives usually have clear
mathematical meanings, so translating them should be straightforward. The tricky
parts are when the meaning of an operator is contextual, like C++ operator
overloads or languages like Perl where the meaning of an operator can't be known
until runtime.
