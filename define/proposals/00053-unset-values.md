# Define Language Proposal 53: Unset Values

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** September 23, 2026
- **Date Finalized:**

## Problems

When you first create a particle in a position that has a value constraint, what
is the value assigned to the particle?

Define's [requirements](../spec/requirements.md) around nullity forbid accessing
anything that is unset. Nulls in general are quite problematic across
programming languages.

We can detect this state in every situation except one: when a particle is
passed into an action, we don't know if its value has been set or not.

## Solution

Newly created particles that have a value constraint do not have a set value.

Value operations may not take any particle that does not have a _set_ value as
one of their input positions (a position from which they read).

Value Setting Statements may not accept a position on the right side of the
statement whose particle has an unset value.

For particles that arrived in an action via a contracted position, reading their
value before it is known to be set creates a new type of Action Position
Requirement that requires the particle's value be set before triggering the
action. (Other constraints determine what it can be set to---the requirement
just requires that it be set.)

Action Position Guarantees must indicate what is known about the set value state
of a particle. If we know the exact value (say, because it was set by a literal)
we should provide that information. If we know the strictest constraints under
which the particle was set (the maximally strict set of everything that wrote to
the particle, considering the last set value as the determining factor when
necessary) we should include that information in the Guarantee. If we know the
particle was not set, we should include that information in the Guarantee.

## A Real Program

### Reading an Unset Value

```define
define the potential value<standard:/number/rational>.

define the potential action<mv:example.com:example:/copy_unset_value> {
    define the position<recipient> {
        it may only contain particles where {
            it has the value<standard:/number/rational>.
        }
    }

    it happens when {
        the position<recipient> has a particle.
    } and it does {
        define the position<source> {
            it may only contain particles where {
                it has the value<standard:/number/rational>.
            }
        }
        create a particle in position<source>.
        # Error: the newly created source particle has an unset value.
        set the value of position<recipient> to position<source>.
    }
}
```

### Generating an Action Position Requirement

```define
define the potential value<standard:/number/rational>.

define the potential action<mv:example.com:example:/copy_value> {
    define the position<source> {
        it may only contain particles where {
            it has the value<standard:/number/rational>.
        }
    }
    define the position<recipient> {
        it may only contain particles where {
            it has the value<standard:/number/rational>.
        }
    }

    it happens when {
        the position<source> has a particle.
    } and it does {
        # Requires the caller to provide a source particle with a set value.
        set the value of position<recipient> to position<source>.
    }
}
```

### Generating an Action Position Guarantee

```define
define the potential value<standard:/number/rational>.

define the potential literal<standard:/decimal> {
    it has the encoding<standard:/encoding/string/decimal>.
}

define the potential action<mv:example.com:example:/initialize_value> {
    define the position<recipient> {
        it may only contain particles where {
            it has the value<standard:/number/rational>.
        }
    }

    it happens when {
        the position<recipient> has a particle.
    } and it does {
        # Guarantees the recipient's value is 5, even if it arrived unset.
        set the value of position<recipient> to literal<standard:/decimal:5>.
    }
}
```

## Why This is the Right Solution

One of our principles for Define is to deny nullity. Originally,
[DLP 38 (Binary Values)](00038-binary-values.md) solved that by always giving
particles the equivalent of a 1-bit zero value by default. However, upon further
consideration, I decided that was "magical" behavior that causes the program to
do something that is not written.

Instead, I realized that we can detect and deny all uses of "unset" values, and
actually always require the developer to explicitly set values on particles.
Called actions were the one tricky part, but I realized that you can solve that
with action requirements just like we solve position occupancy.

The downside is that, just like our requirement and guarantee inference, this
costs memory and processing time in the compiler. I'm willing to take that
trade-off to get intuitive and safe behavior around unset values.

## Forward Compatibility

We have total static protection against nulls, hard to imagine how that would
cause us any forward compatibility issues. In general, any time we fully
_forbid_ something from happening, we are in pretty safe territory with forward
compatibility.

## Refactoring Existing Systems

Any _safe_ system could be refactored into Define. In fact, you could detect
null pointer errors in existing systems by trying to refactor them into Define,
most likely. Some languages "do operations" on null values, but really what they
are usually doing is treating the null as though it were some other value (`0`,
the string `NULL` to be passed into a SQL query, etc.).
