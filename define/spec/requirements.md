# Requirements for Define

These are invariants that the language must not break.

## Nullity

Accessing undefined variables is a constant source of error in many other
programming languages.

It must be impossible for a program to access an undefined variable. The
compiler must catch it.

This means there is no concept of "null" in Define, there is only "a position
that is empty," which the compiler will forbid any interaction with other than
filling the position or checking if it is empty.

## Knowledge Does Not Have Side Effects

Knowing a symbol must never cause code to execute. There are no "static
initializers" in define. Simply loading a file of define code does not run the
code (other than what the compiler and runtime need to do behind the scenes to
make the symbols available or do any optimizations).

The only way action occurs is by a user triggering an action by requesting that
it run, and then the programmer triggering other actions inside of that action.

## Ambiguity is Forbidden

The language must never "figure out" on the developer's behalf what they meant.
It must require the developer to always specify exactly what their intention is,
in the code.

Generally this means that all ambiguity is an error if no intention is
specified. Name conflicts are not allowed.

Define attempts to forbid even the _possibility_ of ambiguity. For example, its
system of global and local names are attempt to prevent any _possible_ naming
conflict where two logically separate things have the same name. Requiring that
universes have a single project root is also an attempt to prevent the
possibility of ambiguity.

## Statements Do Not Start With Names

We do not create syntax in define that looks like:

`type<name> takes some action`

It's much harder to parse that successfully than if we start the statement with
keywords and put the name inside of the statement.

Just as one point, it makes it much harder for developers to do dumb parsing of
files. For example, imagine you want to write a regular expression to
successfully find all particle creations. It's much harder for programmers to
get it right if the name starts the line. The regex
`/^(\w+<\w+>) now has a particle/` is much harder than
`/^create a particle in (.+)\./`. Also, the first regex is what developers would
probably write and it would actually be wrong, because names can be configured
to have more characters allowed than `\w`.

It's also the only way we can both be consistent _and_ create intuitive
sentences. We want there to be one right way in Define, and so if names are
going to start lines, I would want them to _always_ start lines. However, in
most situations, starting lines with the name forces developers to write a bunch
of passive statements like `quality<foo> is defined as`, when really the
programmer is taking decisive action by providing statements of intent.

Finally (and this isn't the most important point, but it's still true) it
requires more lookahead from the parser.

## Constraints Must Be Statically Provable

The compiler must be able to know whether a constraint holds, while compiling.
This is one of the earliest goals of Define, from the
[philosophy](../philosophy.md). There are many statements you could attempt to
make in a constraint syntax that would not be statically provable. We need to
make those situations impossible.

In general, there are a few qualities of a logical system that tend to make it
"undecidable" (meaning that there are unprovable statements within the logic):

1. Unrestricted quantification over relations or sets: ("for all relations that
   could possibly exist" or "for all sets that could possibly exist")
2. Unbounded recursion (we can't tell if a graph of conditions or triggers will
   terminate)
3. Unbounded minimality (the ability to keep reducing something to smaller and
   smaller pieces infinitely: functions that do not converge at their limit,
   Zeno's Dichotomy Paradox, etc.)
4. Ability to encode arithmetic (multiplication in particular, because the Godel
   Incompleteness Theorem proves that once you introduce multiplication into
   logic, the logic becomes undecidable, but only if you allow the logic to be
   self-referential). This doesn't mean "don't _do_ arithmetic." It means "don't
   create a system of logic that itself can define math like
   [Peano arithmetic](https://en.wikipedia.org/wiki/Peano_axioms)."
5. The ability to create Turing machines (obviously this causes the halting
   problem)

Thus, we need to be very careful not to allow those things in constraints.

The constraints that are easiest to decide are when you only have boolean
variables and the connectives (AND, OR, NOT).

### Constraints May Not Reference Themselves

No constraint at any time may ever reference _itself_. For example,
`constraint<foo>` may not contain statements about `constraint<foo>`. Nor may it
do so via a causal loop (such as `foo` refers to `bar` and `bar` refers to
`foo`).

Almost every failure in history of logical systems comes about from forms of
logic that allow things to refer to themselves. For example, Russell's Paradox
("consider the set of all sets that do not contain themselves") comes about
because in set theory, sets could refer to themselves. The Godel Incompleteness
Theorem comes about by allowing logical statements to refer to themselves. We
have ample evidence in history that this is a bad idea. Don't allow it.

### Constraints Must Also Be Tractable

There are some constraints that are theoretically provable, but the time it
would take a computer to prove them is much too long. You can mostly solve this
problem by restricting the logical operations you allow to only certain
operations.

According to my current investigations, these features tend to make resolving
constraints intractable:

1. Aliasing. This means allowing two pointers to possibly point to the same
   value. It causes the number of potential paths through a program to
   combinatorially explode. This is the most important thing to forbid if you
   want to ensure verifiability. We should likely forbid this by default.
2. Logical quantifiers ("for all values that could ever he put into this
   formula, the following is true" and "there exists at least one X for which
   the following is true"). Doing statements like this over small finite arrays
   is fine, AFAIK, but not over logically infinite sets.
3. Nonlinear arithmetic. `ax + by ≤ c` is generally easy for solvers (you're
   multiplying something by a known constant and checking if it's less than or
   equal to a constant). `x * y = z` is hard (you're multiplying two variables
   and checking if they are then equal to another variable---there's a huge
   explosion of logical possibilities there).
4. Doing Non-Boolean Operations on Boolean Bitvectors. A bitvector is a way to
   encode a bunch of boolean states into a single integer. It's fine to do that.
   What's not fine is to then do any operation on it other than flipping bits
   and running boolean logic against it. For example, if you do arithmetic with
   the "integer" then you've exploded the possibilities of what could happen.
   Even bitwise operations like bitwise AND or OR can be a nightmare because you
   are shifting _so many_ conditions all at once.
