# Define Language Proposal 23: Dimension Points Define Other Positions

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** January 20, 2026
- **Date Finalized:**

## Problems

In [DLP 22](00022-atomic-qualities.md) I explained how qualities will actually
be atomic, and that we will "assign" actions or other positions to dimension
points. This involved a decision that was hidden behind the scenes:

Can dimension points actually define the location of other dimension points, or
should we just limit ourselves to some concept of a form, and only forms can
define groups of dimension points?

I need to explain how I made this decision and why.

## Solution

The decisions were:

1. Positions are inherently defined by the location of other dimension points.
   The first dimension point ever defined in a program is essentially the "view
   point" and all other dimension points are defined in relation to it. Thus,
   positions define other positions directly.
2. Forms will exist, but they will only exist when necessary to express
   concepts. They are not mandatory for expressing positions.

## A Real Program

N/A in this proposal, because we are only explaining and justifying decisions.

## Why This is the Right Solution

As I was originally working on the design of Define, I had thought perhaps that
forms and qualities would be entirely distinct---that positions would not be
qualities, and that we would have a concept of a "form" that was the only way to
define positions (or perhaps the only way to group positions together). Only
constraints and actions would be qualities. However, this quickly got us into
trouble. Let's explain why:

I want to describe a bank account. It has a balance, a transaction history, an
action to withdraw from the balance, and an action to deposit to the balance.
Conceptually in a traditional object-oriented language, this looks something
like (in a Python-like syntax):

```Python
class BankAccount:
    account_id: int
    balance: float

    def withdraw(self, amount: float):
        self.balance -= amount

    def deposit(self, amount: float):
        self.balance += amount
```

In the way we think about it, `balance` and `account_id` are dimension points
with value. You then have an action named `withdraw` and an action named
`deposit`. Thus `BankAccount` is both a form (it contains multiple dimension
points) and a set of qualities (it has two actions). That sounds like two
separate concepts, right? A form and a set of qualities. Well, the problem is,
all these things are inherently tied together. Let's look at this example as
code to see the problem more concretely (in an imaginary Python-like syntax):

```Python
form BankAccountValues:
    account_id: int
    balance: float

quality BankAccountActions:
    def withdraw(self, amount: float):
        self.balance -= amount

    def deposit(self, amount: float):
        self.balance += amount
```

As you can see, this is very awkward. The `BankAccountActions` quality can
_only_ really be applied to something that has the `balance` field from
`BankAccountValues`. In essence, all we have done is split the required
definition of a quality across two different concepts. In fact, we've done
something awkward, because `BankAccountActions` _doesn't_ need `account_id`. No
matter how I looked at this, positions and actions were tied together if they
wanted to update state on a dimension point.

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

## Forward Compatibility

Once we decide to allow actions to reference "this dimension point", we can't
convert to being a pure functional programming language. That's the primary
forward compatibility issue we would face. However, we don't intend to be a pure
functional programming language---we intend to be able to model any universe (or
at least, any universe that any programming language that exists today could
model). So our fundamental philosophy indicates that this is okay.

## Refactoring Existing Systems

I believe this decision still leaves us flexible enough that we could refactor
every existing programming language into Define and keep its logic (including
the enforcements of its compiler) intact.
