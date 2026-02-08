# Define Language Proposal 27: Shortening Common Names

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** January 22, 2026
- **Date Finalized:**

## Problems

The syntax mandated for global names in
[DLP 5](00005-global-names-local-names-and-scopes.md) is necessary in order to
avoid naming conflicts inside of programs. However, constantly using it within
code over and over tends to make programs unreadable.

This shows up most clearly in long programs. However, most Define programs that
do anything serious are very long. So it ends up happening in basically every
Define program. For example, see this program (don't try to hard to understand
it, it's very hard to read):

```
define the potential action<mv:example.com:bank:/do_transfers> {
    define the position<run>.

    it happens when {
        the position<run> has a dimension point.
    } and it does {
        define the position<account1> {
            it may only contain dimension points where {
                it has the action<mv:example.com:bank:/account/withdraw>.
                it has the action<mv:example.com:bank:/account/deposit>.
                it has the action<mv:example.com:bank:/account/transfer_to>.
            }
        }
        create a dimension point in position<account1>.
        create a dimension point in position<account1>::action<mv:example.com:bank:/account/deposit>::position<amount>.
        set the value in position<account1>::action<mv:example.com:bank:/account/deposit>::position<amount> to 100.
        create a dimension point in position<account1>::action<mv:example.com:bank:/account/deposit>::position<run>.

        define the position<account2> {
            it may only contain dimension points where {
                it has the action<mv:example.com:bank:/account/withdraw>.
                it has the action<mv:example.com:bank:/account/deposit>.
                it has the action<mv:example.com:bank:/account/transfer_to>.
            }
        }
        create a dimension point in position<account2>.
        create a dimension point in position<account2>::action<mv:example.com:bank:/account/deposit>::position<amount>.
        set the value in position<account2>::action<mv:example.com:bank:/account/deposit>::position<amount> to 50.
        create a dimension point in position<account2>::action<mv:example.com:bank:/account/deposit>::position<run>.

        wait until {
            the position<account1>::action<mv:example.com:bank:/account/deposit>::position<run> is empty.
            AND
            the position<account2>::action<mv:example.com:bank:/account/deposit>::position<run> is empty.
        }
        create a dimension point in position<account1>::action<mv:example.com:bank:/account/transfer_to>::position<amount>.
        set the value in position<account1>::action<mv:example.com:bank:/account/transfer_to>::position<amount> to 50.
        move the dimension point in position<account2> to position<account1>::action<mv:example.com:bank:/account/transfer_to>::position<to>.
        create a dimension point in position<account1>::action<mv:example.com:bank:/account/transfer_to>::position<run>.

        wait until {
            the position<account1>::action<mv:example.com:bank:/account/transfer_to>::position<run> is empty.
        }

        move the dimension point in position<account1>::action<mv:example.com:bank:/account/transfer_to>::position<to> to position<account2>.
        create a dimension point in position<account2>::action<mv:example.com:bank:/account/transfer_to>::position<amount>.
        set the value in position<account2>::action<mv:example.com:bank:/account/transfer_to>::position<amount> to 200.
        move the dimension point in position<account1> to position<account2>::action<mv:example.com:bank:/account/transfer_to>::position<to>.
        create a dimension point in position<account2>::action<mv:example.com:bank:/account/transfer_to>::position<run>.
    }
}
```

I personally find that very hard to read, and I designed the language. (What
it's doing is defining two bank accounts and then attempting to do transfers
between them.)

In experimenting with the language, I discovered the primary reason this is hard
to read is that the constant repetition of `mv:example.com:bank:` creates visual
noise that makes it hard to differentiate lines of code from each other.

## Solution

Any definition that is _inside_ of another definition must not use the
fully-qualified universe name for global names defined in the same universe as
the containing definition.

In other words, in the above example, the only use of `mv:example.com:bank:`
would be in the `define the potential action` section. All other global names
would start with a `/` only.

To be clear, this is required, so that we enforce there being only one way to do
things.

## A Real Program

This turns the above program into:

```
define the potential action<mv:example.com:bank:/do_transfers> {
    define the position<run>.

    it happens when {
        the position<run> has a dimension point.
    } and it does {
        define the position<account1> {
            it may only contain dimension points where {
                it has the action</account/withdraw>.
                it has the action</account/deposit>.
                it has the action</account/transfer_to>.
            }
        }
        create a dimension point in position<account1>.
        create a dimension point in position<account1>::action</account/deposit>::position<amount>.
        set the value in position<account1>::action</account/deposit>::position<amount> to 100.
        create a dimension point in position<account1>::action</account/deposit>::position<run>.

        define the position<account2> {
            it may only contain dimension points where {
                it has the action</account/withdraw>.
                it has the action</account/deposit>.
                it has the action</account/transfer_to>.
            }
        }
        create a dimension point in position<account2>.
        create a dimension point in position<account2>::action</account/deposit>::position<amount>.
        set the value in position<account2>::action</account/deposit>::position<amount> to 50.
        create a dimension point in position<account2>::action</account/deposit>::position<run>.

        wait until {
            the position<account1>::action</account/deposit>::position<run> is empty.
            AND
            the position<account2>::action</account/deposit>::position<run> is empty.
        }
        create a dimension point in position<account1>::action</account/transfer_to>::position<amount>.
        set the value in position<account1>::action</account/transfer_to>::position<amount> to 50.
        move the dimension point in position<account2> to position<account1>::action</account/transfer_to>::position<to>.
        create a dimension point in position<account1>::action</account/transfer_to>::position<run>.

        wait until {
            the position<account1>::action</account/transfer_to>::position<run> is empty.
        }

        move the dimension point in position<account1>::action</account/transfer_to>::position<to> to position<account2>.
        create a dimension point in position<account2>::action</account/transfer_to>::position<amount>.
        set the value in position<account2>::action</account/transfer_to>::position<amount> to 200.
        move the dimension point in position<account1> to position<account2>::action</account/transfer_to>::position<to>.
        create a dimension point in position<account2>::action</account/transfer_to>::position<run>.
    }
}
```

Note that some of the syntax above is imaginary; it exists just to prove the
point about global name prefixes.

That still has some readability challenges, but it's much easier to read. (Once
you have syntax highlighting, it's _considerably_ easier to read than the
previous version, too.)

## Why This is the Right Solution

It still keeps global names exactly unique. It does prevent refactoring
everything with pure regular-expression matchers or raw string matching, but for
most programs it won't really matter---you could still string-match what you're
looking for.

For the refactoring tools and static analysis guarantees of Define, these
shorter names are still guaranteed to be unique.

It doesn't solve the problem of libraries (other universes that you depend on)
where you would still have to use their full global name prefixes. We can solve
that in the future if it becomes too problematic.

## Forward Compatibility

As noted above, we are still guaranteeing the ability to change our minds later;
we could easily deterministically refactor this back to the previous syntax, and
after that, we could make any other naming change we want to make.

## Refactoring Existing Systems

This has a trivial solution; you just remove the prefix where you know that you
can, and "know that you can" is made extremely easy by the guarantees of Define.
