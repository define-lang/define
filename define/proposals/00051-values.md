# Define Language Proposal 51: Values

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** September 19, 2026
- **Date Finalized:**

## Problems

As part of [DLP 39 (Value Types)](00039-value-types.md), the most important
things that the programmer will interact with the most often are _values_. In
addition to the basic problems in [DLP 39 (Value Types)](00039-value-types.md)
there are some problems that are specific to conceptual value types.

### 1: Specificity

How many different value types do you want to have, in a language? Are unsigned
integers and signed integers different types? For that matter, are decimals a
different type than integers? What about floating point numbers, are they
different than fixed point decimals, at our logical layer?

### 2: Hierarchy

Do we want value types to have relationships to each other? Can you say "a
`/number/integer` is also a `/number`"? If so, does that mean you can set a
`value</number>` to a `value</number/integer>`?

### 3: Conversions

Can you convert somehow between compatible value types? Does it happen
automatically, or do you have to specify it explicitly?

### 4: Multiplicity

Can one particle have more than one value? Conceptually, this would mean that
one particle has, simultaneously, two different meanings. If that's the case,
how do you specify which value you want to work with, on the particle, when
you're performing an operation on it?

### 5: Built-In Constraints

Can a value have a constraint that it always applies when used? For example,
could you define a `value</number/natural>` that has a
`constraint</number/zero_or_greater>` that it always applies?

### 6: Modularity

What happens when a particle that has a value is supplied to an action, but the
contracted position through which it arrived has no `value` constraint? How is
the compiler supposed to behave?

## Solution

A value type is defined as a global name, like this:

```define
define the potential value<mv:example.com:example:/number/rational>.
```

All of the real properties of a value are actually determined by its encoding
operations and associated operations. A value is just an abstract name holding
all of those things together.

Any constraint is always kept separate from the value and applied to positions
separately.

### No Hierarchies

Value types have no hierarchies or relationships.

### No Automatic Conversion

Any conversion between value types happens through explicit value operations
(not converters). The compiler may of course choose to implement and optimize
those converting operations any way it wishes.

### Values as Constraints

Any given particle may have only one `value` constraint. One particle may not
have multiple simultaneous logical meanings. There's no reasonable way to
determine if an operation is legal other than by having the value type specified
on the particle.

Just to be clear, assigning a value constraint looks like this:

```define
define the position<foo> {
    it may only contain particles where {
        it has the value<standard:/number/rational>.
    }
}
```

### Value Operations

Value operations (including `set the value of`) may only be executed on
positions that have their value constraint explicitly specified. In other words,
no inference is done and no cross-action analysis is ever required to determine
the value type of a particle.

When `set the value of` has positions as both the "from" and "to" position,
those positions must have the same value type specified on them.

### Specificity

In general, we strive to have values represent the broadest possible data type
that has the same _logical_ behavior. One way to think of this is that this is a
data type that does not need a constraint in order to define it.

For example, rational numbers and floating point numbers are different types.
That may be unintuitive, but they are fundamentally different from an arithmetic
lens: rationals do exact math and floating point numbers do approximate math
with some very particular behaviors.

## A Real Program

```define
define the potential value<standard:/number/rational>.

define the potential action<mv:example.com:example:/copy_item_count> {
    define the position<item_count> {
        it may only contain particles where {
            it has the value<standard:/number/rational>.
            it has the constraint<standard:/number/integer>.
            it has the constraint<standard:/number/unsigned>.
        }
    }
    define the position<quantity> {
        it may only contain particles where {
            it has the value<standard:/number/rational>.
        }
    }

    it happens when {
        the position<item_count> has a particle.
    } and it does {
        set the value of position<quantity> to position<item_count>.
    }
}
```

## Why This is the Right Solution

[DLP 39 (Value Types)](00039-value-types.md) covers a lot of the logic, here.

### Hierarchy

When I thought about hierarchy, I realized that specifying an overlapping set of
encoding operations and encodings for a value would be essentially the same as
having a hierarchy, but be much more compositional. It's annoying if you just
want to modify the behavior of a value type slightly, so we may need some better
composition model (as discussed briefly in the [Concepts](../spec/concepts.md))
but for now this system works and could be converted into some compositional
system that removes duplication in the future, to some degree. (The thing we
couldn't automatically migrate is realizing that two value types in two
different universes have some overlap in their operation definitions.)

### Specificity

The reason for choosing specificity at a high (very generic) level is me
thinking through _why_ we have value types and what they really represent.
Either we go all-in on having things like "signed integer" and "unsigned
integer" or we have just one high-level type and then we infer the encodings
based on the operation requirements and the constraints on the value type.

We'll provide constraints like `constraint</number/unsigned>` (which will just
check `>= 0`) and `constraint</number/integer>` (which will force the rational
denominator to be 1, and then representationally and in the compiler, we can
just omit the denominator and treat the value as an integer).

### No Automatic Converters

Converting between high-level value types almost always requires some sort of
real encoding conversion, and also has real logical consequences. For example,
if you convert from a float to an integer, you need to explicitly state that
you're doing that, because you're about to lose a whole bunch of precision.
That's not something the compiler should just magically do and hide from you.

This solves the "preventing invalid assignments" problem from DLP 39.

### Singularity

Having more than one value on a particle is super confusing.

Conceptually, it's one of the things that confuses human beings the most often,
like a word that has multiple different meanings (sometimes even conflicting
meanings). In human languages you have to solve that by context. In a
programming language, you want to know what everything means with as little
context as possible, for the purpose of fast compilation and also the
programmer's ability to reason about the code.

It's also confusing programmatically. When I pass a particle to an operation
that has more than one value, what is the operation supposed to do? Do we now
need some whole new syntax to handle the fact that sometimes a particle has more
than one value? We could do it like
`position<foo>::value<standard:/number/rational>` but why make the different
value types special, where a particle can have only one of those but can have
another of a _different_ value type? Super confusing.

The right solution, when you want multiplicity, is child positions. And that's
the other problem with multi-value particles: how would you know when to use
them vs when to use child particles? Child particles are the right abstraction
to map to Define's conceptual model, are much more flexible, and are widely
supported across the language. We don't need some weird new hack to do
multi-value stuff some other way.

### Modularity

I thought a bit about this. At first I was like, "wow, it would be cool to pass
a particle without a value to an action and then it can do stuff with that
particle, and then you get generic behavior for free!" Then I realized that it
would be totally meaningless. What operations are legal for that particle? What
operations do you even _write_, as the programmer? Even if you could discover
what was valid and created generic operations (which we don't have) you would
have to implement code generation similarly to how destruction contracts work,
which would mean either continuation passing or monomorphization, in which case
why didn't you just create separate actions anyway?

## Forward Compatibility

I believe I've made the most restrictive choices available to me. If I change my
mind about specificity, it's easy to add more specific value types. All the
other decisions are similar:

- No hierarchy means no hierarchy system to continue to support.
- The lack of automatic converters means no magical semantics to continue to
  support invisibly.
- Requiring positions in operations to have explicit value constraints is the
  strictest choice we could have made.
- Singular values is the strictest choice we could have made.

All of these can be easily changed and statically analyzed.

## Refactoring Existing Systems

This system should pretty easily map to the existing type systems of other
languages. It would be tricky to map full dependent typing systems like Lean,
that's the only limitation, but also that's because we explicitly _don't intend_
to support the full power of an undecidable type system.
