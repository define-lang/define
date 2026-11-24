# Define Language Proposal X: Registered Boolean Operations (Backup)

> **Note:** Archived backup of the earlier generic `booleans.defcl` registration
> design for DLP 61, superseded by
> [DLP 61: Standard Boolean Operations](../define/proposals/00061-standard-boolean-operations.md).

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** November 1, 2026
- **Date Finalized:**

> **Note:** Much of this proposal was written by Claude, and it still needs to
> be reviewed.

## Problems

One of our aspirations with Define is to allow there to be, to whatever degree
we can accomplish it, only one way to write any given program.
[DLP 56 (Logical Operations for Boolean Values)](00056-logical-operations-for-boolean-values.md)
defines a minimal core of logical operations for boolean values.
[DLP 59 (No Redundant Boolean Logic)](00059-no-redundant-boolean-logic.md)
forbids computing a value the program already has, and
[DLP 60 (One Order for Boolean Logic)](00060-one-order-for-boolean-logic.md)
gives boolean logic one order. But a program can still write out logic that an
existing operation already computes.

Note: For the background research behind this proposal, see
[Representations of Boolean Logic](background/boolean-logic-representations.md).

### 1: Writing Out an Operation That Already Exists

If the standard library has a value operation for "or," a program could execute
it, or it could write `not (not a and not b)` itself. Both compute the same
thing, so that's two ways to write the same program.

Comparing the structure of the statements isn't enough to notice this, because
the same thing can be written with very different structures. These both compute
whether `a` and `b` are equal:

```python
(a and b) or (not a and not b)
```

```python
not ((a and not b) or (not a and b))
```

### 2: Knowing Which Operations Exist

In Define, files are only loaded by reference
([DLP 8 (Files Are Loaded By Reference)](00008-files-are-loaded-by-reference.md)).
To tell a program that it has written out an operation that already exists, the
compiler has to know about that operation, even though the program never
mentions it. It can't search every file in a project or its libraries for
operations to compare against, for the same reasons as in
[DLP 47 (Value Encoding Associations)](00047-value-encoding-associations.md)
(Problems 5 and 6).

### 3: Every Value and Every Argument

Any value in a value operation could be the same as an existing operation given
any of the values that come before it, and those values don't have to be
anywhere near it in the program. The compiler has to look at all of them, in
every value operation of a program that could be millions of lines long.

### 4: Overlapping Matches

Several different groups of statements in one value operation can each compute
the same thing as an existing operation, and those groups can overlap. Replacing
one of them can make another one disappear. Which one should the compiler tell
the programmer to replace?

### 5: Second Names for an Operation

A value operation whose only statement executes another operation computes
exactly what that operation computes. Executing it and executing the operation
are two ways to write the same thing. But actions can only execute value
operations, so an action that needs `and` or `not` has to execute a value
operation that does nothing else.

## Solution

Projects register the boolean operations that their own value operations have to
use instead of writing them out. No value may always be the same as what a
registered boolean operation computes from values the value operation already
has, or its opposite, and no value operation may be only a second name for a
registered operation. `and` and `not` count as registered operations for every
value operation. This uses the boolean value operations, boolean statements, and
boolean inputs of DLP 59.

### Registering Boolean Operations

A project registers its boolean operations in a new configuration directory,
`operations`, in the file `.define/operations/booleans.defcl`. It has the
format:

```protocol-buffer-text-format
booleans: {
    boolean_operations: [
        "/boolean/equality",
        "/boolean/or",
    ]
}
```

A name in the global name short form refers to a value operation in the current
project. A project can also register a value operation from a project it depends
on, by its full global name, so that its own value operations have to use it.
Each name may only appear once. The order of the list doesn't matter: registered
operations come in an order set by what they compute (see The Order of
Registered Operations).

Every registered operation must be a boolean value operation that reads at most
three views and writes exactly one view, and a project's `booleans.defcl` may
list at most 16 registered operations. The compiler throws an error if a
registration violates either rule.

#### Project Root Config

The new field in the project root config is `has_booleans`, like this:

```protocol-buffer-text-format
    operations: {
        has_booleans: TRUE
    }
```

`has_booleans` defaults to false. The compiler only _looks_ for `booleans.defcl`
if this value is `TRUE`.

#### Which Registered Operations Apply

A value operation has to follow the registered operations of its own project and
of the standard library, and no others. A library's registered operations only
apply to the library's own value operations. So the rules a value operation
follows only change when its own project's `booleans.defcl` changes, or when the
standard library does, and they're the same whether a project is compiled by
itself or as part of another project.

`logical_operation<standard:/boolean/and>` and
`logical_operation<standard:/boolean/not>` are registered boolean operations for
every value operation, without being listed.

The definition of a registered operation only follows some of the registered
operations:

- one of the standard library's follows `and`, `not`, and the standard library's
  registered operations that come before it, and
- one of a project's own follows `and`, `not`, all of the standard library's
  registered operations, and the project's own that come before it.

Both use the order in The Order of Registered Operations.

Two registered operations that apply to the same value operation can't compute
the same thing (the same result for every input, with their read views in some
order). The compiler throws an error if they do.

The compiler only loads the definitions of registered operations when it's
compiling a value operation that has boolean statements, and it can record what
each one computes so that it doesn't have to load it again.

#### The Order of Registered Operations

The registered operations that apply to a value operation come in this order:

1. **`and`, then `not`.**
2. **Fewest `and`s:** the operation that can be written with the fewest `and`s,
   using only `and` and `not`.
3. **Fewest read views.**
4. **The project's own first:** the value operation's own project's registered
   operations, then the standard library's.
5. **More symmetric first:** the operation with fewer interchangeable-view
   groups (so symmetric operations like `or` come before asymmetric ones like
   `implies`).
6. **Results:** the operation whose results come first, with false before true,
   when its results are listed for every combination of its read views in
   counting order, with its first read view changing least often.

Two registered operations never compute the same thing, so this always puts one
before the other. For the standard boolean operations, this gives the natural
order `and`, `not`, `or`, `implies`, `xor`, `eq`, `mux`, `maj`. Apart from which
project registered each operation, it depends only on what each operation
computes, not on how its definition is written or where it's listed.

### No Writing Out a Registered Operation

In any value operation, a **match** is a value that a boolean statement computes
when, for every combination of the value operation's boolean inputs, it's always
the same as what a registered boolean operation computes from at most three
values that come before it, given to the registered operation's read views in
some order. Those values are the match's **arguments**. Each argument has to
matter: for some combination of the boolean inputs, changing it would change
what the registered operation computes. A value that is already an execution of
that registered operation with those arguments isn't a match.

A match is an error. The compiler says which value it found, which registered
operation it's the same as, and which argument goes to which of its read views,
and the programmer has to compute the value with an execution of that operation
instead.

- **The statements of a match** are the ones that executing the registered
  operation instead removes: the statement that computes the value, and every
  statement that nothing reads any more once the value comes from the execution.
  Apart from the spellings in One Spelling for Each Value, a match has to remove
  at least two statements, so a single statement is never a match.
- **Executions are whole.** Executing a boolean value operation is one statement
  that computes what that value operation computes. Only the boolean inputs and
  the values that the value operation's own statements compute can be matches or
  arguments, never the values inside an executed value operation, since the
  programmer can't replace part of an execution.
- **Opposite results count.** A value that's always the opposite of what a
  registered operation computes from its arguments is a match for it too, and
  the programmer has to compute it with an execution of that operation and a
  `not` of its result. Since that adds two statements, it's only a match when it
  removes at least three. If an operation that computes the opposite is
  registered as well, the value is a match for that operation instead. An
  execution of a registered operation and a `not` of its result are never the
  opposite result of any operation. They're only a match for an operation that
  computes the opposite.
- **The largest match is the one reported.** When there's more than one match,
  the compiler reports the one that removes the most statements. If two remove
  the same number of statements, it reports the one whose value's statement
  comes first, then the one whose registered operation comes first (see The
  Order of Registered Operations), and then the one whose arguments, in DLP 60's
  rank order, come first. Once the programmer replaces it, any matches that are
  left show up the next time the program is compiled.
- **Redundant values first.** When a value operation has a redundant value (DLP
  59), the compiler reports that before any match.

#### One Spelling for Each Value

Sometimes a value can be computed by more than one execution of a registered
operation from earlier values. For example, with both an "or" and an "implies"
operation registered, if a value operation already has `not b`, then
`a or (not b)` and `b implies a` compute the same thing, and each one is a
single execution. Only one of these **spellings** is allowed: the one that comes
first in this order.

1. **Fewest negations:** the spelling that gives the fewest values that are a
   `not` of another value to its read views.
2. **Registered operation:** the spelling whose registered operation comes first
   in The Order of Registered Operations, which puts the one that can be written
   with the fewest `and`s first.
3. **Rank order:** the spelling whose arguments, in DLP 60's rank order, come
   first.

A value that's computed by an execution of any other spelling is a match, even
though replacing it doesn't remove any statements, and the compiler names the
spelling that comes first. When the compiler reports any other match, it names
the spelling that comes first too.

A `not` of another value is never a match for another spelling. DLP 59 requires
a value that's always the opposite of an earlier value to be written as the
`not` of that value, so it keeps that spelling even when another one would come
first. For example, if `w` is `x implies (not y)`, then `not w` is always the
same as `x and y`, but it stays `not w`, because `x and y` would be a redundant
value: the opposite of `w`.

This also means a value operation can't compute the same thing as a registered
operation it isn't, because then its whole set of boolean statements would be a
match.

### No Wrappers

A value operation can't be just a wrapper for a registered boolean operation. If
a boolean value operation has only one boolean statement, and that statement
executes a registered boolean operation, the compiler throws an error, because
the value operation is only a second name for that operation. Programs have to
execute that operation directly instead.

Actions can only execute value operations, so an action that needs `and` or
`not` executes a value operation that wraps it. There's exactly one of each, in
the standard library, with the same name as the logical operation it wraps:
`operation<standard:/boolean/and>` executes
`logical_operation<standard:/boolean/and>`, and
`operation<standard:/boolean/not>` executes
`logical_operation<standard:/boolean/not>`. They have the same views as the
logical operations, with the same names and directions, and they're the only
wrappers for `and` and `not` that aren't an error. Programs have to execute them
instead of any other.

- **Not in value operations:** executing either wrapper inside a value operation
  is an error. Value operations have to execute the logical operation directly.
- **Not registered:** neither wrapper can be a registered boolean operation.

## A Real Program

### Configuration

```bash
# .define/project/config.defcl
project: {
    universe_name: "mv:example.com:logic"
    operations: {
        has_booleans: TRUE
    }
}
```

```bash
# .define/operations/booleans.defcl
booleans: {
    boolean_operations: [
        "/boolean/xor",
    ]
}
```

This registers `operation<mv:example.com:logic:/boolean/xor>`, the value
operation in DLP 60's examples, which computes whether exactly one of its two
read views is true. DLP 60's `operation<mv:example.com:logic:/lamp/is_lit>`
executes it, so it still compiles.

### Errors

Writing out the registered operation is an error:

```define
define the operation<mv:example.com:logic:/lamp/bad_is_lit> {
    define the view<switch_a> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }
    define the view<switch_b> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }
    define the view<power> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }
    define the view<lit> {
        it is written.
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }

    it does {
        # Error: view<switches_differ> is always the same as
        # operation<mv:example.com:logic:/boolean/xor>, with view<a> looking at
        # view<switch_a> and view<b> looking at view<switch_b>, even though
        # it's written differently from its definition. Execute it instead of
        # these seven statements.
        define the view<both> {
            it may only contain particles where {
                it has the value<standard:/boolean>.
            }
        }
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<switch_a>.
            with view<b> looking at view<switch_b>.
            with view<result> looking at view<both>.
        }
        define the view<not_both> {
            it may only contain particles where {
                it has the value<standard:/boolean>.
            }
        }
        execute the logical_operation<standard:/boolean/not> {
            with view<a> looking at view<both>.
            with view<result> looking at view<not_both>.
        }
        define the view<not_a> {
            it may only contain particles where {
                it has the value<standard:/boolean>.
            }
        }
        execute the logical_operation<standard:/boolean/not> {
            with view<a> looking at view<switch_a>.
            with view<result> looking at view<not_a>.
        }
        define the view<not_b> {
            it may only contain particles where {
                it has the value<standard:/boolean>.
            }
        }
        execute the logical_operation<standard:/boolean/not> {
            with view<a> looking at view<switch_b>.
            with view<result> looking at view<not_b>.
        }
        define the view<neither> {
            it may only contain particles where {
                it has the value<standard:/boolean>.
            }
        }
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<not_a>.
            with view<b> looking at view<not_b>.
            with view<result> looking at view<neither>.
        }
        define the view<not_neither> {
            it may only contain particles where {
                it has the value<standard:/boolean>.
            }
        }
        execute the logical_operation<standard:/boolean/not> {
            with view<a> looking at view<neither>.
            with view<result> looking at view<not_neither>.
        }
        define the view<switches_differ> {
            it may only contain particles where {
                it has the value<standard:/boolean>.
            }
        }
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<not_both>.
            with view<b> looking at view<not_neither>.
            with view<result> looking at view<switches_differ>.
        }
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<power>.
            with view<b> looking at view<switches_differ>.
            with view<result> looking at view<lit>.
        }
    }
}
```

So is writing a second wrapper for `and`:

```define
define the operation<mv:example.com:logic:/boolean/both> {
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
        # Error: only operation<standard:/boolean/and> can wrap
        # logical_operation<standard:/boolean/and>. Execute one of those
        # instead.
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<a>.
            with view<b> looking at view<b>.
            with view<result> looking at view<result>.
        }
    }
}
```

## Why This is the Right Solution

### Why Not Require a Form?

Another way to get one way to write boolean logic would be to require programs
to write it in a canonical form, like the ordered BDDs that DLP 56 discusses.
But a canonical form only makes the _function_ unique. A program could still
write out "or" in canonical form instead of executing the operation for it, and
that's still two ways to write the same program (Problem 1). So the compiler
would need to find written-out operations anyway.

### Why Compare What Statements Compute?

Comparing the structure of statements can't tell that two very different
compositions compute the same thing (Problem 1). Comparing what they compute
can, for any composition, no matter how it's written.

### Why Any Earlier Values?

A match could be limited to values that its statements read directly, or that
are close to it. But then a value could still be a second way of writing what a
registered operation computes from values the program already has. For example,
with an equality operation registered, if `x` and `y` can never both be true,
then "neither `x` nor `y`" is always the same as "`x` equals `y`," and both
would compile. Over every earlier value, there's only one of them.

Only values that come before a match can be its arguments, so a match is always
something the programmer can replace where it is. In measurements on generated
value operations of up to 256 boolean statements, looking for matches over every
earlier value took a few milliseconds for each value operation: 2–5 ms at 16
boolean inputs and 8–18 ms at 20. See the research repository's
[boolean_equality_checking](https://github.com/define-lang/research/tree/main/boolean_equality_checking)
directory for the measurements.

### Why Count the Statements a Match Removes?

A match's size is the number of statements that replacing it removes. No
replacement makes a value operation bigger: an ordinary match removes at least
two statements and adds one, an opposite result removes at least three and adds
two, and a spelling replaces one execution with another. So every replacement
either makes the value operation smaller, or keeps its size and gives a value a
spelling that comes earlier. In measurements, other ways of counting, or letting
opposite results add as many statements as they removed, let replacements go
back and forth: one replacement made a match that the next one undid. With these
rules, fixing every redundant value and match one at a time ended with a value
operation that compiles every time.

### Why a Configuration File?

The compiler can't search for operations to compare against (Problem 2).
`booleans.defcl` tells it exactly which ones to load, the same way
`encodings.defcl` does for encodings in DLP 47. It only lists names, so nothing
about an operation is written in two places: what it computes always comes from
its definition. And `has_booleans` means the compiler never has to check whether
the file exists.

Registering operations also lets a library keep helper value operations that
nobody else has to use. Only the operations a project registers become the one
way to write what they compute.

### Why This Order of Spellings?

The order puts the most readable spelling first, as far as a rule can tell
what's readable:

- **Fewest negations** first, because logic written with the fewest negations is
  usually the easiest to read: `b implies a` instead of `a or (not b)`, and "`a`
  differs from `b`" instead of "`a` equals (not `b`)."
- **The order of registered operations** next, so that between spellings that
  read equally well, the one that does the least work wins. A project's own
  operations come before the standard library's when they do the same amount of
  work, because the project chose them for its own code.
- **Rank order** last, so there's always exactly one answer.

### Why Order Registered Operations by What They Compute?

The order of registered operations decides which spelling is allowed and which
definitions have to execute which. If it came from how `booleans.defcl` lists
them, reordering the list would change which spellings compile, and so would
rewriting one operation's definition, if the order counted the `and`s in each
definition as written. In measurements, the six standard operations listed in
each of their 720 possible orders gave fourteen different sets of `and` counts,
and with `xor`, `eq`, and `mux` listed before `or`, a value that's `or(u, w)` in
the standard order had to become `xor(u, w)`.

The fewest `and`s that an operation can be written with depends only on what it
computes. A registered operation reads at most three views, so there are only
256 things it can compute (14 equivalence classes under permuting and negating
views and negating the result), and the compiler knows the fewest `and`s for
each one ahead of time. With the order set by what each operation computes, the
same registered operations always give the same rules, however they're listed
and however their definitions are written.

### Why Only the Project's Own Registrations?

If every dependency's registered operations applied, adding a dependency, or
upgrading one that registers a new operation, could make code that compiled
before into errors, because of a decision made in another project. With only the
project's own registrations and the standard library's, a project's code only
has to change when the project decides it should. A project that wants a
library's operation to be the one way to write something in its own code
registers it.

This means there's one way to write boolean logic within each project, not
across every project. Two projects can write the same logic differently if they
registered different operations. The standard library is the one set of
registered operations that every project follows.

### Why Count `and` and `not` as Registered?

Every registered operation is written with `and` and `not`, so a registered
operation can also be used to write `and` itself. With an "if `s` then `x`, else
`y`" operation registered, executing it with `not c`, `c`, and `b` computes
`b and c`. With "or" registered, `(not a) or (not b)` computes `not (a and b)`.
If `and` and `not` didn't count as registered, both ways of writing each one
would compile. Counting them makes the same rules that apply to every other
registered operation leave only `b and c` and `not (a and b)`. They come first
because they're the minimal core that every other operation is written with.

### Why Follow Only the Operations Before It?

Two registered operations can each be written with the other. Equality is the
opposite of exclusive or, so with both registered, equality written out with
`and` and `not` would be an opposite result of exclusive or, and would have to
execute it, while exclusive or written out would have to execute equality.
Neither one could ever be written with only `and` and `not`. When each
definition only follows the operations that come before it, the first one is
written out, and the ones after it can use it.

The standard library's registered operations never follow a project's, so what a
project registers never changes how the standard library has to be written.

### Why the Largest Match?

The largest match replaces the most statements with one execution, so it's the
one that removes the most of the written-out logic (Problem 4). Reporting one
match at a time, and finding the rest on later compiles, keeps the rule simple:
the compiler never has to decide what the best set of replacements for a whole
value operation would be, which is NP-hard. And since the rule for which match
to report only depends on the statements, every compiler reports the same one.

### Why Match Opposites?

If opposite results didn't count, the opposite of a registered operation could
be written two ways: as an execution of that operation and a `not`, or written
out. For example, with `or` registered, "neither `x` nor `y`" could be
`(not x) and (not y)` or `not (x or y)`, and both would compile. Matching
opposites leaves only the second. A library that wants the opposite of an
operation to be one statement, like "not equal," can register it, and then that
operation is the one way to write it.

One case is left with two ways. When writing an opposite out takes only two
statements, like `a and (not b)` for the opposite of `a implies b`, replacing it
with an execution and a `not` doesn't make the value operation any smaller, so
it isn't a match, and both spellings compile. Making either one an error would
let replacements go back and forth between them.

### Why No Wrappers?

A wrapper computes exactly what the operation it executes computes, so executing
the wrapper and executing the operation are two ways to write the same thing
(Problem 5). A single execution isn't a match, so the rule against matches can't
catch a wrapper by itself, and it needs its own rule. A wrapper that only gives
an operation's views different names is still a second name for the operation.

Wrappers for logical operations are the exception, because actions need them.
Logical operations can only be executed inside a value operation, so without a
wrapper, an action couldn't use `and` or `not` at all. So the rules make sure
there's still only one way to write each one:

- **One wrapper for each.** If any project could write its own, every project
  that needs `and` in an action could have a different one. Giving the wrapper
  the logical operation's name means only the standard library can define it.
- **Only in actions.** Inside a value operation, executing the wrapper and
  executing the logical operation would be two ways to write the same statement,
  and neither one is a redundant value or a match.
- **Never registered.** `and` and `not` are already registered operations, and a
  registered wrapper would be a second way to write them.

This only covers the two boolean logical operations. Logical operations for
other kinds of values work for every value quality that supports them, while a
value operation's views name particular value qualities, so one wrapper with the
logical operation's name can't cover all of them. Future proposals for those
logical operations will need their own rule.

### Why These Limits?

- **Three read views for registered operations:** match search over earlier
  values scales as `O(S * (I + S)^(k - 1))` in the worst case for arity `k` (and
  up to `k!` view permutations). Even at 256 statements, an XOR-like arity-4
  registered operation has no forcing prefix until its fourth argument and times
  out (`> 15 s`), whereas arity `≤ 3` stays around `0.1 s` worst case and covers
  every standard boolean combinator (`or`, `implies`, `xor`, `eq`, `mux`,
  `maj`). Larger custom boolean helpers (up to 20 read views) remain available
  as normal unregistered value operations.
- **At most 16 registered operations per project:** keeps match search linear in
  a small fixed constant across every value operation and action in the project
  (the standard library itself only registers 6).
- **One written view for registered operations:** a match computes one value.
  Executing an operation that writes more views than the program needs would
  leave views that nothing reads.

## Forward Compatibility

Raising the limit on registered operations per project doesn't stop any program
that compiles now from compiling, so we can raise it if real programs need it.

When a project registers a new boolean operation, its own value operations may
now have matches. The same is true for every project when the standard library
registers one. But the compiler can fix every one of those value operations
automatically, by replacing each match with an execution, so existing programs
can be refactored deterministically. A dependency that registers a new operation
never changes the rules for the projects that use it.

Future proposals can extend the same ideas to operations on other kinds of
values, like numbers. Those will need a different way to compare what statements
compute, because truth tables only work for boolean values.

## Refactoring Existing Systems

Programs written with the logical operations from DLP 56 may write out
operations that their project or the standard library now registers, or wrap
`and` and `not` in their own value operations. Every rule in this proposal is
computed from the program itself, so a tool can refactor every existing program
automatically: it replaces each match with an execution of the registered
operation, until there are no matches left. It replaces each execution of any
other wrapper with an execution of the operation it wraps, or, in an action, of
the standard library's wrapper.
