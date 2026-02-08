# Define Language Proposal 29: Joining Multiple Conditions

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** January 22, 2026
- **Date Finalized:**

## Problems

We need to be able to specify more than one condition for a Trigger Conditions
Block. We may also need to do the same for constraints in various places in the
future. Essentially, we need ways to join logical statements together.

## Solution

We allow basic boolean logic inside of Trigger Conditions Blocks. Also, anywhere
else that Define allows basic boolean logic, it will follow the same rules
described in this proposal.

### Basic Boolean Operators

Trigger Conditions Blocks may use standard boolean operators along with
parentheses `()` to create compound statements: `AND`, `OR` and `NOT`. These
operators follow standard boolean logic. They are case-sensitive. Unlike the
rest of Define, they are capitalized, to avoid syntax conflicts with other
Define syntax in the future (because they are just one word).

We are deferring `XOR` to a later proposal because it causes some unique
problems.

### Binding Order

Parentheses _must_ be used to resolve ambiguous binding orders of `AND` and
`OR`. The language does not specify a binding order, so if a binding is
encountered that would be ambiguous (such as `x AND y OR z`) the compiler throws
an error instructing the developer to add parentheses for clarity. This happens
any time there is both `AND` and `OR` in the same parenthetical scope.

`NOT` binds as described below in the formatting section. The binding of `NOT`
cannot be ambiguous, so we don't have to specify ambiguity rules for it.

### Formatting Boolean Logic

When joining single statements (non-parenthesized) `AND` and `OR` must be on the
its own line. If they open a parenthesized statement, the opening parenthesis
must be on the same line as the operator, one space after it, with a newline
after the parenthesis.

Thus, the syntax for `AND` and `OR` looks like this:

```
(
    condition;
    AND
    condition;
)
OR (
    condition;
    AND
    condition;
)
```

```
condition;
OR condition;
OR (
    condition;
    AND
    condition;
)
```

Unnecessary parentheses are not allowed and must be collapsed. For example, this
is not allowed:

```
condition1;
AND (
    condition2;
    AND
    condition3;
)
```

`NOT` has the same rules as `AND` and `OR` for formatting, except that it must
be on the same line, prefixing `AND` or `OR` when that does not create
ambiguity. When `NOT` is prefixed to a single statement (as opposed to a
parenthetical statement), it modifies only that statement. For example:

```
NOT condition1;
AND condition2;
```

Means "the inverse of condition1 must be true, and condition2 must be true."
However, this:

```
NOT (
    condition1;
    AND condition2;
)
```

Means that both condition1 and condition2 must be false. And here's one more
formatting example:

```
condition1;
AND NOT (
    condition2;
    OR condition3;
)
```

This formatting is mandatory and enforced by the compiler.

### Shortcuts

The program at runtime will only attempts to check conditions until it
determines the statement must be false. In other words, if you check three
conditions all joined by AND, and the first one is false, the program at runtime
might only choose to check the first one as an optimization.

However, the compiler might also choose to re-order condition statements when it
knows that is safe (produces identical logic) and believes that re-ordering
would produce a more optimal program. So ordering triggers will not prevent
paradoxes. That is, the compiler will act like the trigger is "reading from" all
of those positions and will deny paradoxes against them.

### Checking Conditions

As noted in [DLP 28](00028-triggering-actions.md), actions only _check_ their
conditions when the state of dimension points in the program change. However, at
that time they will check all of their conditions. So for example, imagine you
have these conditions:

```
the position<foo> has a dimension point
AND
NOT the position<bar> has a dimension point
```

Let's pretend that when that action was assigned, the `position<foo>` already
had a dimension point, and `position<bar>` was already empty. Then the program
destroys the dimension point in `position<foo>`. Nothing happens, because the
trigger conditions don't match. However, then we create a dimension point in
`position<foo>`. The action would fire, even though nothing has changed about
the _state_ of `position<bar>`.

In other words, only one of the positions listed in a trigger condition has to
change its state in order for the action to check its conditions.

## A Real Program

```
define the potential action<define-lang.org:bank:/account/transfer_to> {
    this dimension point must have the position</account/balance>.
    this dimension point must have the action</account/withdraw>.

    define the position<run>.
    define the position<to> {
        it may only contain dimension points where {
            it has the action</account/deposit>.
        }
    }
    define the position<amount> {
        it may only contain dimension points where {
            it has a value that is a decimal.
            it has the constraint</positive>.
        }
    }

    it happens when {
        the position<run> has a dimension point.
        AND
        the position<to> has a dimension point.
        AND
        the position<amount> has a dimension point.
    } and it does {
        # A bunch of stuff to transfer money to another account.
    }
}
```

## Why This is the Right Solution

There are other forms of logic besides this straightforward boolean logic. I
explored many of them when looking at the overall design of constraints for
Define. Almost all forms of logic, however, at some point rely on these
statements (AND, OR, and NOT) as well as using parentheses for precedence. There
was no good reason to choose other forms; they all decrease readability of the
code and don't gain us any advantages for the types of constraints we have
defined.

It is possible that Define Approximately would need different constructs, as
continuous values are not exactly true or false.

## Forward Compatibility

The reason the formatting restrictions exist is to force Define programs into
forms where (1) the logic is unambiguous and (2) it is easy to parse by both
human readers and raw string processors (systems that don't have access to
Define's parser). In general, this sort of strictness helps us guarantee forward
compatibility because we know exactly what Define programs must look like.

## Refactoring Existing Systems

With just position constraints, the `has a dimension point` trigger condition,
and these boolean operators, you can express almost every trigger condition in
every existing programming language today, as well as some conditions that those
languages would have a _very_ difficult time expressing.

There are still a few other pieces we would need to cover _every_ reasonable
trigger condition, which will come in later proposals.
