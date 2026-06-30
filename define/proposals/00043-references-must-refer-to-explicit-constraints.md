# Define Language Proposal 43: References Must Refer to Explicit Constraints

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** June 30, 2026
- **Date Finalized:**

## Problems

Currently, you can write code like this:

```define
define the position<foo> {
    it may only contain particles where {
        it has the position</parent>.
    }
}
create a particle in position<foo>.
create a particle in position<foo>::position</child>.
```

As long as `position</parent>` implies `position</child>`, you can refer to
`position</chlid>` even though the constraints in this file did not indicate
that `position</child>` was available. This causes a few problems.

### 1: It's Confusing

A programmer reading the above code has no idea where `position</child>` came
from. It looks magical.

### 2: Maintenance

When doing static analysis or large-scale refactoring on Define programs, you
have to expand the transitive implications of a position just to know if written
lines of code are referring to valid names, instead of just using information
available in the AST.

Yes, you still have to load the definitions of global names in order to know
that children of those global names exist, but at least when you do that, the
information about which children can be validly _referenced_ is entirely
contained in the AST of _that_ global definition.

### 3: Access Control

In the future Define will have access control, and one of the simplest forms of
access control is "you may or may not reference this name." If we allow
transitively-implied names to be referenced, it becomes much more complex for
the compiler to reason about access and for the human programmer to think
through how access works.

## Solution

In order for a name to be referred to as a child position or an implied position
in any Action Statements Block, it must be explicitly written. Concretely, this
means:

1. **Local Positions**: When any statement refers to a child name of a local
   position, that child name must be listed as an explicit constraint on the
   definition of that child position.
2. **Global Positions**: When any statement refers to a child name of a global
   position, that child name must be listed as an explicit constraint on that
   global position.
3. **Implied Qualities**: When any statement refers to a quality that _this
   action_ implies (a chained name that starts with a global name), _this
   action_ must itself directly imply that quality.

## A Real Program

All of the programs below are _invalid_. They are examples of what is forbidden.

### Invalid Local Name Child

```define
define the potential position<example.com:example:/child>.

define the potential position<example.com:example:/parent> {
    it also assigns the position</child>.
    it may only contain particles where {
        it has the position</child>.
    }
}

define the potential action<example.com:example:/invalid> {
    define the position<run> {
        it may only contain particles where {
            it has the position</parent>.
        }
    }

    it happens when {
        the position<run> has a particle.
    } and it does {
        create a particle in position<run>::position</child>.
    }
```

In order for that to be valid, `position<run>` would have to specify
`position</child>` as an explicit constraint.

### Invalid Global Name Child

```define
define the potential position<example.com:example:/other_child>.

define the potential position<example.com:example:/child> {
    it also assigns the position</other_child>.
}

define the potential position<example.com:example:/parent> {
    it may only contain particles where {
        it has the position</child>.
    }
}

define the potential action<example.com:example:/invalid> {
    define the position<run> {
        it may only contain particles where {
            it has the position</parent>.
        }
    }

    it happens when {
        the position<run> has a particle.
    } and it does {
        create a particle in position<run>::position</parent>::position</other_child>.
    }
```

In order for that to be valid, `position</child>` would have to specify
`position</other_child>` as an explicit constraint.

### Invalid Transitive Implication Access

```define
define the potential position<example.com:example:/child>.

define the potential position<example.com:example:/parent> {
    it also assigns the position</child>.
}

define the potential action<example.com:example:/invalid> {
    it also assigns the position</parent>.
    define the position<run> {
        it may only contain particles where {
            it has the position</parent>.
        }
    }

    it happens when {
        the position<run> has a particle.
    } and it does {
        create a particle in position</child>.
    }
```

In order for that to be valid, `action</invalid>` would have to specify
`position</child>` as an explicit implication.

## Why This is the Right Solution

Originally this was allowed, and it caused all of the problems described in the
Problems section.

One of my original reasons for allowing this was that I thought that having to
be explicit would be a somewhat annoying maintenance burden---when you added a
new field and you wanted to reference it, you would have to explicitly update
the constraints on whatever position you were touching. It was a bit of "you
have to update two places to make one change," which is a general thing I try to
avoid in the design of the language. It was simpler, from the perspective of the
_write_ phase of an automated refactoring tool, to simply allow transitive
references. However, honestly, the write phase is rarely the complex part of
static analysis---usually it's being confident that your query hit the right
target (the "read" phase). Being explicit dramatically simplifies that,
especially for tools that aren't the compiler itself.

It was also somewhat "confusing" to the compiler. It is much simpler if we can
just reason through "everything that gets touched in this action is what's
written on the definition." Otherwise you have to first validate the whole
action to know what the complete set of touched children are. When you combine
the "only explicit references" rule with the "no dead constraints" rule, you can
be confident that the set of constraints written on anything is the exact set
that will be interacted with (or in the case of a destructor, at least
eventually required).

## Forward Compatibility

Either decision here is actually forward compatible. We can change our minds
about this at any time.

## Refactoring Existing Systems

You just have to add the missing explicit constraints, which we know are valid,
to the relevant positions.
