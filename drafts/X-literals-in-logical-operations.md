# Define Language Proposal X: Literals In Logical Operations

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** October 27, 2026
- **Date Finalized:**

> **Note:** This draft was written by Claude and requires extensive revision.

## Problems

[DLP 52 (Literals)](../define/proposals/00052-literals.md) defined literals for
places that have a value quality: the right side of `set the value of`, and
views that an operation doesn't write to. There, a literal is logically
identical to a particle with "the value quality needed in order to make the line
of code where the literal is specified be valid," and the compiler converts the
literal's text with a parser from the literal's encoding to the destination's
encoding.

[DLP 55 (Logical Operations)](../define/proposals/00055-logical-operations.md)
added logical operations, and value operations use literals in logical operation
executions all the time. For example, this subtracts 1 from a natural, but stops
at 0:

```define
execute the logical_operation<standard:/number/equality> {
    with view<a> looking at view<a>.
    with view<b> looking at literal<standard:/number>"0".
    with view<result> looking at view<is_zero>.
}
execute the logical_operation<standard:/number/add> {
    with view<a> looking at view<a>.
    with view<b> looking at literal<standard:/number>"-1".
    with view<result> looking at view<decremented>.
}
execute the logical_operation<standard:/choose> {
    with view<condition> looking at view<is_zero>.
    with view<if_true> looking at literal<standard:/number>"0".
    with view<if_false> looking at view<decremented>.
    with view<result> looking at view<result>.
}
```

`view<a>` and `view<result>` are naturals, and `view<decremented>` is an
integer. But a logical operation's views have no value qualities, and nothing in
a logical operation execution has an encoding yet. So the way DLP 52 gives a
literal its meaning doesn't work here.

### 1: The Compiler Has to Reason About the Literal

The compiler doesn't just pass a literal along. It reasons about it. A range
check ([DLP 56](../define/proposals/00056-range-constraints.md)) needs to know
that the literal is exactly -1, and so does adding it to something, comparing it
to something, or noticing that multiplying by a literal 1 does nothing. So while
compiling, the compiler has to turn the literal's text into the logical value it
stands for: a number or a truth value.

That translation has to be exact. `"0.1"` has to be exactly one tenth, even
though no binary floating-point encoding can hold that. It also has to be able
to fail, because `"12x"` isn't a number.

How does the compiler get the exact logical value of a literal's text, while
compiling?

### 2: Knowing What a Literal Must Be Doesn't Say What It Is

The place a literal is used tells the compiler a lot about it. The logical
operation says what kind of value it takes (`standard:/number/add` only takes
numbers), and the views around it can say more, like that the result has to be
from 0 to 255. But that's still a set of things the literal could be, not which
one it is. `"10"` is ten in decimal, two in binary, and sixteen in hexadecimal,
and all three are numbers from 0 to 255.

So something has to say how to read the text. It could be the kind of value the
literal has to be, the literal itself, or both together. Choosing between
readings by which one fits the constraints would mean that a literal's meaning
changes whenever a constraint somewhere else changes.

Where does the way to read a literal's text come from?

### 3: Value Qualities Don't Say What Kind of Value They Hold

DLP 55 says that a view's value quality "says what kind of values it holds," but
the definition of a potential value only lists the logical operations it
supports. Nothing says that `standard:/number/natural` holds numbers, or that
`standard:/boolean` holds truth values, except indirectly, through the logical
operations they support. So a literal that has to become a value of some value
quality has nothing to look at to know what kind of value that is.

How does the compiler know what kind of logical value a value quality holds?

### 4: Where Does a Literal's Value Quality Come From?

A logical operation's own views have no value qualities, but every view of the
value operation that executes it does, including its local views. So there are
two places a literal's value quality could come from:

- The views that the logical operation's other views look at. But in the example
  above, `standard:/number/add` adds `view<a>`, a natural, and the literal -1,
  which isn't a natural.
- The view that the logical operation's result goes to. That makes -1 an
  integer, which is right. But the result of `standard:/number/equality` is a
  truth value even though it compares numbers, so that doesn't work for the
  literal 0 that's compared to `view<a>`. And `view<condition>` of
  `standard:/choose` is a truth value even when it picks between numbers.

Some literals have no other view to go by at all, like the exponent of
`standard:/number/power`, which DLP 55 already requires to be a literal natural.

Where does a literal in a logical operation execution get its value quality, if
it needs one?

### 5: What Has to Be True of the Literal Itself?

If a literal gets a value quality from where it's used, should it have to be a
valid value of that value quality? That would catch `"1.5"` given to an
operation on integers right at the literal. But it also rejects correct
programs. If `x` is an integer from 3 to 10, adding the literal -3 to it always
gives 0 to 7, which can go in a natural, even though -3 isn't a natural. And
whether a result fits is already checked where it's written.

What has to be true of a literal by itself, apart from the results it's used to
compute?

### 6: Literals That Are More Than One Value

Some things people want to write as literals aren't one number or one truth
value, like a date, an IP address, or an amount of money in some currency. In
Define, those are more likely several values on child particles. But logical
operations only take numbers and truth values, and a literal in a logical
operation execution stands for one value.

Can a literal stand for more than one value, and if it can, what does that mean
in a logical operation execution?

### 7: The Standard Literals Aren't Defined

DLP 55 uses `literal<standard:/boolean>"true"`, but there's no potential literal
`standard:/boolean`. And `literal<standard:/number>` has the encoding
`standard:/number/decimal/ascii`, which isn't defined either.

What are the standard library's potential literals, and how are they defined?

### 8: Which Encoding Does a Literal Get?

When the compiler generates code, a literal needs some encoding, like an
instruction's immediate operand or a constant in memory. DLP 52 picks it based
on the value the literal is assigned to. But a literal in a logical operation
execution may never be stored anywhere, and the compiler may compute it as part
of an intermediate value that's wider than any view (DLP 55, Problem 10).

How does the compiler choose the encoding of a literal in a logical operation
execution?

## Solution

We add a new name type, `logical_value`, for the kinds of values that logical
operations work on. Value qualities and the views of logical operations say
which logical value they hold. A potential literal says how its text is written
and which logical values that text can become, and the place a literal is used
decides which one it does become.

### Logical Values

A logical value is a kind of value that logical operations work on, like numbers
or truth values. It's the "what is this, mathematically?" part of a value, with
no encoding, no constraints, and no particular value quality.

Logical values are global names, defined in the global scope with
`define the logical_value` followed by the name and a terminator:

```define
define the logical_value<standard:/number/rational>.
define the logical_value<standard:/boolean>.
```

This proposal defines two:

- `logical_value<standard:/number/rational>` is the exact rational numbers.
  Every number a logical operation works on is one of these, and every
  `standard:/number` logical operation is exact on them.
- `logical_value<standard:/boolean>` is the truth values, true and false.

Like logical operations, logical values are part of the compiler, even though
they're names in the standard library. The compiler has to know what every
logical value is in order to know what logical operations do with it. A program
can't define its own logical values, and the compiler throws an error for a
`define the logical_value` that it doesn't know about.

### Value Qualities Say What They Hold

The block of a potential value may now start with a Logical Value Statement:
`it holds the` followed by a logical value name and a terminator.

```define
define the potential value<standard:/number/natural> {
    it holds the logical_value<standard:/number/rational>.
    it supports the logical_operation<standard:/number/absolute_value>.
    it supports the logical_operation<standard:/number/add>.
}
```

Every value of that value quality is one of that logical value's values. Which
ones is still up to the value quality. The compiler knows that naturals and
integers are whole numbers, as it does now, and constraints say the rest.

A value quality that has Logical Operation Support Statements must have a
Logical Value Statement, and every logical operation it supports must have an
input view that holds that logical value. A value quality with no Logical Value
Statement has values with no logical meaning. They can still be passed around,
set, and moved, but no logical operation can take them (except as
`view<if_true>` and `view<if_false>` of `standard:/choose`, which never look at
what their values are), and no literal can become one of them.

This replaces the rule in DLP 55 that supporting `standard:/number/add` is what
says a value quality's values are numbers. It also replaces the special rule
that the compiler knows `value<standard:/boolean>` is the value quality of truth
values. Any value quality that holds `logical_value<standard:/boolean>` holds
truth values.

### Logical Operation Views Say What They Hold

Each view of a logical operation now has a Logical Value Statement after its
View Direction Statements. It's either `it holds the` followed by a logical
value name, or `it holds the same logical_value as` followed by another view of
the same logical operation:

```define
define the logical_operation<standard:/number/less_than> {
    define the view<a> {
        it is read.
        it holds the logical_value<standard:/number/rational>.
    }
    define the view<b> {
        it is read.
        it holds the logical_value<standard:/number/rational>.
    }
    define the view<result> {
        it is written.
        it holds the logical_value<standard:/boolean>.
    }
}

define the logical_operation<standard:/choose> {
    define the view<condition> {
        it is read.
        it holds the logical_value<standard:/boolean>.
    }
    define the view<if_true> {
        it is read.
        it holds the same logical_value as view<result>.
    }
    define the view<if_false> {
        it is read.
        it holds the same logical_value as view<result>.
    }
    define the view<result> {
        it is written.
    }
}
```

`it holds the same logical_value as` is only for logical operations that work on
any logical value, like `standard:/choose`. The view it names must be the
logical operation's output view, and that output view has no Logical Value
Statement of its own. Its logical value is whatever the logical value of the
view it's written to is, in each execution.

That always works out, because a logical operation's output view always looks at
a view of the value operation (a local view or an output view), and that view
always has a value quality.

When a logical operation's view looks at a view of the value operation, the
value quality of the value operation's view must hold the same logical value as
the logical operation's view. This replaces the rules in DLP 55 that the
`standard:/number` logical operations only take numbers and that
`view<condition>` of `standard:/choose` must look at a truth value. It's in
addition to the rule that the value quality must support the logical operation.

### Potential Literals Say What They Can Become

A potential literal's encoding says how its text is written. It doesn't say what
the text means. The text `"5"` in `literal<standard:/number>` is a decimal
number, but what it becomes depends on where it's used.

So the block of a potential literal now lists the logical values its text can
become, after its encoding, with `it may become the` followed by a logical value
name and a terminator:

```define
define the potential literal<standard:/number> {
    it has the encoding<standard:/number/decimal/ascii>.
    it may become the logical_value<standard:/number/rational>.
}
```

There must be at least one, they must be in alphabetical order, and each logical
value may only be listed once.

For each encoding the compiler knows, the compiler defines which logical values
text in that encoding can become, and how. A potential literal may only list
logical values that the compiler can convert its encoding to. Otherwise, it's an
error on that statement.

### What a Literal Becomes

Every place a literal can be used says which logical value the literal has to
become:

- On the right side of `set the value of`, it's the logical value of the
  position's value quality.
- In a value operation execution, it's the logical value of the value quality of
  the view the literal is given to.
- In a logical operation execution, it's the logical value of the logical
  operation's view that the literal is given to. If that view holds the same
  logical value as the output view, it's the logical value of the view the
  output view is written to.
- In the definition of a value quality (like the limits of predicates in DLP
  56), it's the logical value of the value quality being defined.

The literal's potential literal must list that logical value with
`it may become the`. Otherwise, it's an error on the literal.

Then, while compiling, the compiler converts the literal's text into an exact
value of that logical value. If the text can't be converted (like `"12x"` as a
decimal number), it's an error on the literal. That exact value is what the
compiler reasons with everywhere the literal is used.

Nothing else about the place a literal is used changes what it becomes. In
particular, constraints never do. They only check the result.

In `set the value of` and in value operation executions, everything else in DLP
52 still applies. The literal's value has to be a valid value of the value
quality it's given to, and it has to meet the constraints there. The only
difference is that the compiler converts the literal's text to its logical value
first, and then to whatever encoding the destination has.

### Literals in Logical Operation Executions

In a logical operation execution, a literal is just its logical value. It has no
value quality and no constraints, and nothing is checked about it other than
that it can become the logical value its view holds. So in the example in the
Problems, the literal -1 becomes the rational number -1, and it doesn't matter
that `view<a>` is a natural.

Whether a result is valid is checked where it's written, the same way it always
is in DLP 55: every possible value written to a view must be a valid value of
that view's value quality and meet its constraints. So adding the literal `1.5`
to an integer and writing the result to an integer is an error on the statement
that writes it, because the result is never a whole number.

The compiler chooses how to encode a literal in a logical operation execution
the same way it chooses how to encode an intermediate value. It may never store
it at all, as with an instruction's immediate operand, or it may compute it as
part of a wider intermediate value.

### A Literal Is One Value

A literal always becomes exactly one value of one logical value. A literal for
something that's made of several values, like a date, isn't part of this
proposal.

### The Standard Literals

The standard library defines two encodings and two potential literals:

```define
define the encoding<standard:/number/decimal/ascii>.
define the encoding<standard:/boolean/ascii>.

define the potential literal<standard:/number> {
    it has the encoding<standard:/number/decimal/ascii>.
    it may become the logical_value<standard:/number/rational>.
}

define the potential literal<standard:/boolean> {
    it has the encoding<standard:/boolean/ascii>.
    it may become the logical_value<standard:/boolean>.
}
```

Text in `standard:/number/decimal/ascii` is an optional `-`, then one or more of
the digits `0` to `9`, then optionally a `.` followed by one or more digits. It
becomes exactly the rational number that decimal stands for, so `"0.1"` is one
tenth and `"-0"` is 0. Nothing else is valid: no `+`, no spaces, no exponents,
and no separators like `_` or `,`.

Text in `standard:/boolean/ascii` is exactly `true` or `false`, and it becomes
that truth value.

## A Real Program

### Standard Definitions

The standard value qualities and logical operations from DLP 55, with their
Logical Value Statements:

```define
define the logical_value<standard:/boolean>.
define the logical_value<standard:/number/rational>.

define the potential value<standard:/boolean> {
    it holds the logical_value<standard:/boolean>.
    it supports the logical_operation<standard:/boolean/equality>.
}

define the potential value<standard:/number/integer> {
    it holds the logical_value<standard:/number/rational>.
    it supports the logical_operation<standard:/number/absolute_value>.
    it supports the logical_operation<standard:/number/add>.
    it supports the logical_operation<standard:/number/equality>.
    it supports the logical_operation<standard:/number/less_than>.
    it supports the logical_operation<standard:/number/minimum>.
    it supports the logical_operation<standard:/number/multiply>.
    it supports the logical_operation<standard:/number/negate>.
    it supports the logical_operation<standard:/number/power>.
}

define the potential value<standard:/number/natural> {
    it holds the logical_value<standard:/number/rational>.
    it supports the logical_operation<standard:/number/absolute_value>.
    it supports the logical_operation<standard:/number/add>.
    it supports the logical_operation<standard:/number/equality>.
    it supports the logical_operation<standard:/number/less_than>.
    it supports the logical_operation<standard:/number/minimum>.
    it supports the logical_operation<standard:/number/multiply>.
    it supports the logical_operation<standard:/number/negate>.
    it supports the logical_operation<standard:/number/power>.
}

define the logical_operation<standard:/number/add> {
    define the view<a> {
        it is read.
        it holds the logical_value<standard:/number/rational>.
    }
    define the view<b> {
        it is read.
        it holds the logical_value<standard:/number/rational>.
    }
    define the view<result> {
        it is written.
        it holds the logical_value<standard:/number/rational>.
    }
}

define the logical_operation<standard:/number/equality> {
    define the view<a> {
        it is read.
        it holds the logical_value<standard:/number/rational>.
    }
    define the view<b> {
        it is read.
        it holds the logical_value<standard:/number/rational>.
    }
    define the view<result> {
        it is written.
        it holds the logical_value<standard:/boolean>.
    }
}
```

Every other `standard:/number` logical operation is like `standard:/number/add`,
except that `standard:/number/less_than` is like `standard:/number/equality`.
`standard:/boolean/equality` is like `standard:/number/equality`, with
`logical_value<standard:/boolean>` for `view<a>` and `view<b>`.
`standard:/choose` is as shown in the Solution.

### Decrementing to Zero

The example from the Problems, as a whole operation:

```define
define the operation<mv:example.com:example:/decrement_to_zero> {
    define the view<a> {
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
        define the view<is_zero> {
            it may only contain particles where {
                it has the value<standard:/boolean>.
            }
        }
        execute the logical_operation<standard:/number/equality> {
            with view<a> looking at view<a>.
            with view<b> looking at literal<standard:/number>"0".
            with view<result> looking at view<is_zero>.
        }
        define the view<decremented> {
            it may only contain particles where {
                it has the value<standard:/number/integer>.
            }
        }
        execute the logical_operation<standard:/number/add> {
            with view<a> looking at view<a>.
            with view<b> looking at literal<standard:/number>"-1".
            with view<result> looking at view<decremented>.
        }
        execute the logical_operation<standard:/choose> {
            with view<condition> looking at view<is_zero>.
            with view<if_true> looking at literal<standard:/number>"0".
            with view<if_false> looking at view<decremented>.
            with view<result> looking at view<result>.
        }
    }
}
```

- The first `"0"` is given to `view<b>` of `standard:/number/equality`, which
  holds `logical_value<standard:/number/rational>`, so it becomes the rational
  number 0. The equality's result is a truth value, but that doesn't matter.
- `"-1"` is given to `view<b>` of `standard:/number/add`, so it becomes the
  rational number -1. It doesn't matter that `view<a>` is a natural and -1
  isn't. What's checked is that every possible result is an integer, because
  it's written to `view<decremented>`.
- The second `"0"` is given to `view<if_true>` of `standard:/choose`, which
  holds the same logical value as `view<result>`. That's written to the
  operation's `view<result>`, a natural, which holds
  `logical_value<standard:/number/rational>`. So it becomes the rational
  number 0.

### Errors

```define
execute the logical_operation<standard:/number/add> {
    with view<a> looking at view<a>.
    # Error: literal<standard:/boolean> can't become
    # logical_value<standard:/number/rational>.
    with view<b> looking at literal<standard:/boolean>"true".
    with view<result> looking at view<sum>.
}
```

```define
execute the logical_operation<standard:/number/add> {
    with view<a> looking at view<a>.
    # Error: "12x" isn't a valid standard:/number/decimal/ascii number.
    with view<b> looking at literal<standard:/number>"12x".
    with view<result> looking at view<sum>.
}
```

```define
# Error: an integer plus 1.5 is never a whole number, so it can't be written to
# view<sum>, which is an integer. The literal itself is fine.
execute the logical_operation<standard:/number/add> {
    with view<a> looking at view<an_integer>.
    with view<b> looking at literal<standard:/number>"1.5".
    with view<result> looking at view<sum>.
}
```

```define
define the potential value<mv:example.com:example:/photo>.

# Error: value<mv:example.com:example:/photo> holds no logical value, so no
# literal can become one of its values.
set the value of position<photo> to literal<standard:/number>"5".
```

## Why This is the Right Solution

### How a Literal is Written Isn't What It Means

The core of this proposal is that a literal's text and its meaning are separate.
A potential literal says how the text is written. The place the literal is used
says what kind of value it has to become. A conversion, defined by the compiler,
connects the two.

That's the only arrangement that handles both of the things we need. The
compiler gets one exact value to reason with (Problem 1), and the same literal
can become different kinds of values in different places. The text `"5"` is the
number 5 today, and when Define has strings, the same
`literal<standard:/number>"5"` can become a string where a string is needed.
Adding that conversion won't change what any existing literal means, because
every existing literal is used in a place that needs a number or a truth value.

It's also what DLP 52 already does. DLP 52 converts from the literal's encoding
to the destination's encoding. This proposal puts a logical value between those
two, which is what lets the compiler reason about the literal before it has
chosen any encoding.

### The Kind of Value Comes From Something Written

A literal's logical value always comes from a Logical Value Statement that's
written down: on the value quality it's given to, or on the logical operation's
view. The compiler never guesses it from the literal's neighbors or from where a
result goes (Problem 4), and it never uses constraints to choose between
readings (Problem 2). So you can always tell what a literal becomes by reading
the line it's on and the definitions it names.

### Why Literals in Logical Operations Have No Value Quality

Giving a literal in a logical operation execution a value quality would mean
checking the literal against it, and that rejects correct programs, like adding
-3 to an integer that's always at least 3 and writing the result to a natural
(Problem 5). It would also mean inferring a value quality, which there's no good
rule for. Without one, a literal is just a number or a truth value, and the
check that already happens where results are written catches every literal that
would make a result invalid.

### Why a Name Type?

Logical values could have been built in, like keywords. But Define gives every
other kind of thing that programs refer to a name type: `value`, `encoding`,
`literal`, and `logical_operation`. As a name type, a logical value can be
referred to the same way from value qualities, logical operations, and potential
literals, and grepping for `logical_value<standard:/number/rational>` finds all
of them. It also leaves room for more logical values, like strings, without new
syntax.

### Why Rational Numbers?

DLP 55 has one `standard:/number/add` for both naturals and integers, so there's
one logical value for numbers, not one for each kind of number. It has to be
exact, because the compiler reasons with it. The rationals are exact, they're
closed under every `standard:/number` logical operation in DLP 55, and they'll
still be closed when division is added. Calling it something like "real" would
claim more than the compiler can do exactly. Naturals and integers are then
rationals that are whole numbers, which is how Define already thinks of them.

### Why Value Qualities Say What They Hold

DLP 55 said what a value quality's values are by which logical operations it
supports. That's indirect, and it doesn't work for a value quality that supports
no logical operations but still needs literals. Saying it directly makes it one
statement that the compiler, the reader, and every literal can look at. The
support statements still say which logical operations a value quality allows,
which is a separate question.

### Why "The Same Logical Value As"?

`standard:/choose` picks between two values of any kind. Without a way to say
that its views hold the same logical value as its result, it would need a
separate logical operation for every logical value, or its views would have to
hold no logical value, and then a literal given to `view<if_true>` couldn't
become anything. Only allowing it to name the output view keeps it simple: the
output view is always written to a value operation's view, so its logical value
is always known.

### Why Potential Literals List What They Can Become

A potential literal could just get every conversion the compiler has for its
encoding. But listing them means that a reader can see what a literal can be
used for without knowing the compiler, and that a mistake like giving a truth
value literal to a number shows up as a clear error on the literal.

## Forward Compatibility

Programs can't define their own literal forms yet. This was true before this
proposal, too: DLP 52 has the compiler convert every literal with its own code,
so a program can define a new potential literal, but only with an encoding the
compiler already knows. There are two ways this could change:

- A compiler extension mechanism, like the one DLP 55 describes for logical
  operations, could provide new conversions. It would have to be exact,
  deterministic, and always finish, like the conversions the compiler has.
- Once Define has strings and loops, a literal's text is itself a value of a
  string logical value. Then a conversion could be a value operation from that
  string to the logical value the literal becomes, run while compiling. That
  needs no extension at all. Define has no recursion and no unbounded loops, so
  running it while compiling always finishes.

Either way, it would add conversions for potential literals, and the rules for
what a literal becomes stay the same.

New logical values, like strings, can be added without changing any existing
program. A potential literal can start listing a new logical value with
`it may become the`, which doesn't change what it becomes in any place it's
already used.

A literal that becomes several values (Problem 6), like a date, would be its own
proposal. It would probably create a particle with children, and it would only
be allowed in places that take a particle, not in logical operation executions.

Whether a value quality's values are whole numbers is something the compiler
knows about the standard value qualities, but a program can't say it about its
own value qualities. That could be a predicate in a later proposal, next to the
minimum and maximum in DLP 56.

If we ever need a literal to mean different things for different value qualities
that hold the same logical value (like `"50"` meaning 0.5 for a percentage),
that can be a new potential literal with its own conversion, without changing
what existing literals mean.

## Refactoring Existing Systems

Every potential literal needs `it may become the` statements for the logical
values it's used as. For the standard library, that's what's in The Standard
Literals above.

Every value quality that's given literals, or that supports logical operations,
needs a Logical Value Statement. Every logical operation's views need Logical
Value Statements.

The rules in DLP 55 about which kinds of values logical operations take, and the
special rule that the compiler knows `value<standard:/boolean>` holds truth
values, are replaced by Logical Value Statements. The rule in DLP 52 that a
literal gets "the value quality needed in order to make the line of code where
the literal is specified be valid" is replaced by What a Literal Becomes, above.

A value quality that holds no logical value could take literals before, as long
as the compiler had a parser for its encoding. It can't anymore. Any program
that does that needs to give the value quality a Logical Value Statement.

In other languages, literals usually get their meaning either from their own
syntax (like `5` vs `5.0` vs `"5"`) or from the type they're assigned to. A
literal translated into Define becomes a literal whose potential literal matches
the original syntax, used in a place whose logical value matches the original
type.
