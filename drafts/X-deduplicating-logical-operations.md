# Deduplicating Logical Operations

Many logical operations can also be written as a sequence of other logical
operations. For example, the maximum of a and b can be written as:

1. Negate a.
2. Negate b.
3. Take the minimum of those.
4. Negate that.

If we add `standard:/number/maximum`, there are two ways to write the same
thing, which goes against having one way to do things. The longer way is also
harder to read, and the compiler has to recognize the pattern to turn it back
into one instruction.

## Idea

A logical operation could declare that it's equivalent to a sequence of other
logical operations, with `it is equivalent to` and a block that has the syntax
of an Operation Statements Block, except that its views have no qualities (and
maybe no directions):

```define
define the logical_operation<standard:/number/maximum> {
    define the view<a> {
        it is read.
    }
    define the view<b> {
        it is read.
    }
    define the view<result> {
        it is written.
    }

    it is equivalent to {
        define the view<negated_a>.
        execute the logical_operation<standard:/number/negate> {
            with view<a> looking at view<a>.
            with view<result> looking at view<negated_a>.
        }
        define the view<negated_b>.
        execute the logical_operation<standard:/number/negate> {
            with view<a> looking at view<b>.
            with view<result> looking at view<negated_b>.
        }
        define the view<smaller>.
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
```

The compiler would then track those patterns in Operation Statements Blocks and
make it an error to write the long form when the short form exists, so the only
valid way to write a maximum is `standard:/number/maximum`. This could come with
an autofix that replaces the long form.

Any logical operation that we add beyond the smallest set, because it's more
efficient or more precise than writing it out, always comes with its equivalent
sequence.

Only logical operations declare equivalences. Value operations don't.

### Matching

The view names in the equivalence are only placeholders. A match is about the
shape of the statements: which logical operations are executed, and which
results feed into which operands. It doesn't matter what any view is named,
either in the equivalence or in the program. Conceptually, it's like comparing
two syntax trees after replacing every name with a generic placeholder.

Some other things should probably still match:

- Statements that don't depend on each other can be in any order, like the two
  negations above.
- Some logical operations don't care about the order of their operands, like
  `add`, `minimum`, and `equality`.

The intermediate values should only match if nothing else reads them.

Matching doesn't have to be especially cheap. Programs should define value
operations very rarely, and logical operations even more rarely, so it's fine
for checking their Operation Statements Blocks to be expensive.

### Checking the Equivalence

The compiler can't prove that a logical operation is equivalent to its declared
sequence, because the compiler's knowledge of each logical operation is its own
implementation, not something it can reason about. But the compiler has two
implementations of everything that declares an equivalence: the logical
operation itself, and the sequence. So it can generate tests that run both on
the same inputs and check that they agree, including edge cases like zero,
negative numbers, and the limits of whatever encodings are involved.
