# Define Language Proposal X: Defining Qualities

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** January 17, 2026
- **Date Finalized:**

## Problems

In [DLP 12](00012-definitions-in-the-universe-of-reflection.md) I specified a
syntax for how things are defined in general. However, we need to give a body to
a quality definition.

This introduces a few problems. However, in this proposal, we will just cover
the problem of syntax and what can be contained in a quality definition.

## Solution

Qualities may create a new local name scope, like this:

```
define the quality<mv:example.com:example:/name> {

}
```

They may contain the definitions of positions and actions.

Qualities must be defined in the global name scope. That means that quality
definitions may not contain the definitions of other qualities.

## A Real Program

```
define the quality<mv:example.com:bank:/account> {
    define the position<balance> {
        it may only contain dimension points where {
            it has the quality<standard:/numbers/decimal>.
            it has the quality<standard:/numbers/constraints/non_negative>
        }
    }

    define the action<withdraw> {
        define the position<amount> {
            it may only contain dimension points where {
                it has the quality<standard:/numbers/decimal>.
                it has the quality<standard:/numbers/constraints/non_negative>.
            }
        }

        # Note that all the syntax inside of these two blocks is
        # imaginary, at this point.
        it happens when {
            the position<amount> is not empty.
        } and it does {
            set the value in position<balance> to: position<balance> - position<amount>.
        }
    }
}
```

## Why This is the Right Solution

There are two big questions: why are qualities allowed to define positions, and
why can't qualities define other qualities?

There should be little question about qualities being able to define
actions---that's the whole reason we're writing a programming language, so that
we can write code that defines machines.

So let's dive into the other questions.

### Why Can Qualities Define Positions?

As I was originally working on the design of Define, I had thought perhaps that
forms and qualities would be entirely distinct---that qualities would not be
able to define positions, and that only forms would be able to define positions.
Qualities would only define constraints and actions. However, this quickly gets
one into trouble. Let's explain why:

I want to describe a bank account. It has a balance, a transaction history, an
action to withdraw from the balance, and an action to deposit to the balance.
Conceptually in a traditional object-oriented language, this looks something
like (in a Python-like syntax):

```Python
class BankAccount:
    balance: float
    transactions: list[float]

    def withdraw(self, amount: float):
        self.balance -= amount
        self.transactions.append(-amount)

    def deposit(self, amount: float):
        self.balance += amount
        self.transactions.append(amount)
```

In the way we think about it, `balance` is a dimension point with a value, and
`transactions` is a form---a list of past withdrawals and deposits. You then
have an action named `withdraw` and an action named `deposit`. The problem is,
all these things are inherently tied together. Let's look at this example as
code to see the problem more concretely (in an imaginary Python-like syntax):

```Python
form BankAccountValues:
    balance: int
    transaction: list[float]

quality BankAccountActions:
    def withdraw(self, amount: float):
        self.balance -= amount
        self.transactions.append(-amount)

    def deposit(self, amount: float):
        self.balance += amount
        self.transactions.append(amount)
```

As you can see, this is very awkward. The `BankAccountActions` quality can
_only_ really be applied to something that has exactly the fields from
`BankAccountValues`. In essence, all we have done is split the required
definition of a quality across two different concepts. No matter how I looked at
this, positions and actions were tied together if they wanted to update state on
a dimension point.

You can certainly argue that all actions should be pure functions and never
update shared state (basically, that qualities _shouldn't_ define positions) but
remember that in Define we need to be able to model all forms of programming,
and one of those forms is object-oriented development, which involves updating
shared state on objects. You can still choose to model a functional system in
Define, and in fact, that's one of the advantages of the language: if you want
to write pure functional code, you can still use a library written with
object-oriented concepts, and vice versa. (One interesting note is that this
seems to clarify the epistemological difference between functional and
object-oriented systems: whether you can refer to and update something about
"this dimension point" inside of an action, or not.)

On a conceptual level, I realized that separating out forms and qualities that
way was not working because it doesn't match what a form actually is: an
abstract concept about a set of dimension points. It's the dimension points that
exist, not the forms. Most simply: In the universes I can logically consider, a
machine triggers based on dimension points that occupy specific _positions in
space_, and it affects dimension points in specific positions in space.

### Why No Inner Qualities?

Qualities are just "containers" for other definitions. When you assign them,
they do nothing other than apply those definitions to a dimension point.

This is logically meaningless:

```
define the quality<mv:example.com:bank:/account> {
    define the position<balance> {
        it may only contain dimension points where {
            it has the quality<standard:/numbers/decimal>
            it has the quality<standard:/numbers/constraints/non_negative>
        }
    }

    define the quality<overdrafted> {
        define the quality<by_amount> {
            it may only contain dimension points where {
                it has the quality<standard:/numbers/decimal>
                it has the quality<standard:/numbers/constraints/non_negative>
            }
        }
    }
}
```

It _looks_ nice, because it makes it visually apparent to us as programmers that
the `overdrafted` quality is related to the `account` quality. But assigning the
`account` quality to a dimension point doesn't somehow cause the _definition_ of
`overdrafted` to come into existence. It obviously already existed---it's right
there, we're reading it. So what happens? Does assigning `account` automatically
assign `overdrafted`? Do we have to explicitly assign `overdrafted`? After I
assign `account` to `position<x>`, do I have to refer to the inner quality as
`position<x>::quality<overdrafted>` when I assign it?

Other languages have this because it allows for access control (saying things
like "only `account` can assign or remove the `overdrafted` quality") but we
will have a much more thorough and complete access control system that solves
that problem.

Essentially, allowing inner qualities gives us a bookkeeping system (these two
qualities are associated) and that's it. It is confusing because the inner
quality doesn't behave the same way as any other part of the quality definition.
All the other definitions become "part" of the dimension point when the quality
is assigned to the dimension point.

## Forward Compatibility

Once we decide to allow positions in quality definitions, we can't convert to
being a pure functional programming language. That's the primary forward
compatibility issue we would face. However, we don't intend to be a pure
functional programming language---we intend to be able to model any universe (or
at least, any universe that any programming language that exists today could
model). So our fundamental philosophy indicates that this is okay.

Otherwise, all the syntax inside of a quality definition is unambiguous, so we
could change it to other syntax. If we wanted to split qualities into more
atomic pieces (like splitting out forms and qualities) we could, because we can
statically see what triggers depend on what positions. If we wanted to re-order
the definitions inside of a quality, we could do that by a topological sort on
which definitions depend on which other definitions in the file.

## Refactoring Existing Systems

I believe the variable and function-definition syntax of any existing
programming language could be refactored into this syntax.

There are various _difficult_ situations, but Scala's path-dependent types are
probably the hardest to reason about, in our system:

```scala
class Graph {
  class Node
  var nodes: List[Node] = Nil
}

val g1 = new Graph
val g2 = new Graph

// In Scala, g1.Node and g2.Node are DIFFERENT types.
// You cannot put a g1.Node into g2's list.
```

However, even there there is really a pattern happening underneath, in the Scala
compiler implementation, that we _can_ represent, even if it's complex.

When you compile that example Scala does three things:

1. **Mangling (Globalizing the Name)**: It effectively lifts the inner class
   `Node` to the global scope. In the JVM bytecode, `Node` becomes a global
   class named `Graph$Node`.
2. **The Hidden "Outer" Field**: It silently adds a `private final` field to the
   `Node` class. This field holds a pointer back to the specific instance of
   `Graph` that created it.
3. **Erasure**: It erases the specific type distinction (`g1.Node` vs `g2.Node`)
   in the bytecode. Both just become objects of type `Graph$Node`.

And you can see that we actually could represent that in our system.

In general, almost all questions about "how do I translate this language to
Define" can be answered by: what does the compiler of that language _really do_?
