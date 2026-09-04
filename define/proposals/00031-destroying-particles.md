# Define Language Proposal 31: Destroying Particles

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** January 24, 2026
- **Date Finalized:**

## Problems

Computer programs have to be able to say "this particle no longer exists." So,
we need a syntax for that.

### Cascading Destruction

Destroying a particle has consequences for any position it defines. They can no
longer be referenced, and thus must also somehow be destroyed. Imagine this
program:

```
define the potential position<mv:example.com:example:/walls> {
    it also assigns the position</paint_color>.
}

define the potential position<mv:example.com:example:/room> {
    it also assigns the position</floor>.
    it also assigns the position</walls>.
    it also assigns the position</ceiling>.
}

define the position<house> {
    it may only contain particles where {
        it has the position<mv:example.com:example:/room>.
    }
}
create a particle in position<house>.
create a particle in position<house>::position</floor>.
create a particle in position<house>::position</walls>.
create a particle in position<house>::position</walls>::position</paint_color>.
create a particle in position<house>::position</ceiling>.

destroy the particle in position<house>.
```

How does one implement that, conceptually? Does every particle vanish
instantaneously, all simultaneously? Do we do them in order, somehow?

### Block Ending and Automatic Destruction

One of the interesting questions for Define is what happens to variables only
defined in an Action Statements Block when that block ends?

Many modern programming languages handle destruction for you (garbage
collection). They just track when particles (variables, objects, etc.) no longer
can possibly be relevant and then free up the memory associated with that
particle. Most of the time, we need to control the existence of particles more
directly, in Define. However, at the end of an Action Statements Block there is
no longer any way to reference any of the positions indicated in that block, so
there is no point in keeping the particles around.

### Trigger Paradoxes

There are a few weird situations that happen with destruction and triggers.
Consider this action and it being defined on this particle:

```
define the potential action<mv:example.com:example:/ensure_floor> {
    it also assigns the position</floor>.

    it happens when {
        NOT the position</floor> has a particle.
    } and it does {
        create a particle in position</floor>.
    }
}

define the position<house> {
    it may only contain particles where {
        it has the action</ensure_floor>.
    }
}
create a particle in position<house>.
```

All right, so far so good. What happens when we do this is pretty clear:

`destroy the particle in position<house>::position</floor>.`

But what happens when we do this?

`destroy the particle in position<house>.`

Does the `ensure_floor` action occur or not? If it does, do we get into an
infinite loop because we keep trying to delete and re-create `floor`? We have to
figure out what's supposed to happen, there. What if the action's behavior is
necessary in order to ensure something gets cleaned up that exists outside the
program (like deleting a temporary file)?

## Solution

Particles can be explicitly destroyed by doing:

`destroy the particle in position<name>.`

This is called a destruction statement. It may be contained in an Action
Statements Block.

It is an error to attempt to destroy a particle that does not exist, and the
compiler will forbid it.

### Automatic Destruction

At the end of an Action Statements Block, all particles still existing in
positions that are only defined locally within that Action Statements Block are
simultaneously automatically destroyed.

Currently, the language allows the compiler to deterministically know which
positions will or won't contain particles, so the compiler can know exactly how
and when to perform auto-destruction.

In the future, if the compiler is uncertain about whether a position still
contains a particle, the compiler will insert code that only destroys particles
in positions if there is a particle there.

The overall principle is: automatic destruction occurs when a position can no
longer possibly be referenced.

### Optimization of Destruction

In situations where the compiler knows that destruction is free of side effects,
the compiler may choose to automatically destroy local particles within an
Action Statements Block the instant they are no longer relevant to the code in
the Action Statements Block.

### Forbidding Action Triggering on Absence

Actions may not trigger due to the _absence_ of a particle. This solves the
Trigger Paradox problem entirely. The necessary functionality that is enabled by
that behavior in other programming languages will be solved in a different way
in a future proposal.

### Simultaneous Transitive Destruction

When a particle is destroyed, all of the particles in the positions it defines
are also destroyed.

Conceptually, both the destroyed particle and all of its transitive children are
destroyed instantaneously, except where other rules of Define would impose a
dependency order between those destructions.

## A Real Program

Here is a direct destruction with two levels of child positions:

```
define the potential position<mv:example.com:example:/leaf>.

define the potential position<mv:example.com:example:/branch> {
    it also assigns the position</leaf>.
}

define the potential action<mv:example.com:example:/destroy_tree> {
    it happens when {
        this particle is created.
    } and it does {
        define the position<tree> {
            it may only contain particles where {
                it has the position</branch>.
            }
        }
        create a particle in position<tree>.
        create a particle in position<tree>::position</branch>.
        create a particle in position<tree>::position</branch>::position</leaf>.

        # This also destroys the particles in position</branch> and
        # position</leaf>; every transitive child particle is destroyed.
        destroy the particle in position<tree>.
    }
}
```

Destruction works the same way when another action performs it:

```
define the potential position<mv:example.com:example:/furniture>.

define the potential position<mv:example.com:example:/room> {
    it also assigns the position</furniture>.
}

define the potential action<mv:example.com:example:/demolish> {
    define the position<target> {
        it may only contain particles where {
            it has the position</room>.
        }
    }
    define the position<run>.

    it happens when {
        the position<run> has a particle.
    } and it does {
        # This destroys the target particle and every transitive child particle,
        # including the particles in position</room> and position</furniture>.
        destroy the particle in position<target>.
        destroy the particle in position<run>.
    }
}

define the potential action<mv:example.com:example:/renovate> {
    it happens when {
        this particle is created.
    } and it does {
        define the position<building> {
            it may only contain particles where {
                it has the action</demolish>.
            }
        }
        create a particle in position<building>.
        create a particle in position<building>::action</demolish>::position<target>.
        create a particle in position<building>::action</demolish>::position<target>::position</room>.
        create a particle in position<building>::action</demolish>::position<target>::position</room>::position</furniture>.

        # Triggering action</demolish> destroys all three particles created in
        # its position<target> chain, without the caller naming each Destroy.
        create a particle in position<building>::action</demolish>::position<run>.
    }
}
```

## Why This is the Right Solution

Destroying all particles simultaneously is essentially choosing _no_ ordering of
destruction. It is the safest baseline from which to start, and then other rules
of Define impose the ordering.

It _does_ mean that compiler implementation details can change the sequence in
which code actually executes, meaning that we cannot know _exactly_ what will
happen statically in a program, in a way. The real constraint it imposes upon us
is that (unless some dependency is imposed on destruction order by other rules)
that we have to make it such that a program analyzes identically regardless of
the actual order in which destruction occurs, or that all analyzers behave as
though particles are all destroyed instantly at the same time together (which is
the safer analysis assumption).

My present belief (having actually done extensive work to implement this in the
compiler at the time I'm writing this) is that it's actually much simpler to
implement the analysis for simultaneous destruction than it was to implement the
analysis for ordered destruction.

The limitation this solution places on us is that any form of destruction
ordering that is required _outside_ of the program must be imposed upon Define
programs as internal dependency ordering. However, I believe that's fine,
because I think programs _must_ express those dependencies naturally. For
example, a buffer that must be flushed before a file is closed, there is some
dependency relationship there that can be exploited to enforce that order. Every
situation that I could come up with, when represented properly in a program,
enforced an actual dependency relationship within the program, and the syntax
and semantics of Define seemed like they would enforce that relationship
successfully. There's still a risk if we fail to implement parts of the standard
library correctly, directly expose syscalls to the programmer, or allow other
forms of unsafe direct access to the "outside world." However, within the
confines of Define itself, I believe this decision to be safe.

### Previous Solution: The Destruction Cascade

This proposal used to describe a system where child particles were destroyed
before parents, and all particles were destroyed in reverse order of how their
_qualities_ were assigned to their parent particle. This was called the
"destruction cascade."

At the time, I believed that triggering actions upon the absence of particles
would be a necessary part of Define, and this reverse-order cascade seemed to be
the simplest way to guarantee correctness in that world. It also seemed to
create a predictable world for static analysis.

The primary problem I Was trying to solve was the ability to refer to particles
during the process of destruction, before they were destroyed. However, it
turned out to be much simpler to simply ban triggering actions on particle
absence, which solves the whole problem in a different way.

Particles in local positions were destroyed in reverse order to when their
positions were defined. Action interface positions were destroyed in a similar
order (reverse definition order). I chose that order because I believed we
needed some deterministic ordering so that we could statically analyze programs
and know exactly what happens, and because definition order was the easiest
sequence for the compiler to check within a single action (position definition
order is completely static). It also protected us if we ever introduced a future
syntax that allowed positions to refer to each other in their definitions (it
would give us some hope that that syntax continues to work correctly during
destruction).

However, imposing a fixed ordering on destruction became impossible to reason
through across actions. If one action defines child positions in one order but
the caller defined them in a different order, which order did we choose? We
would have had to go back to the creation point of every particle to know how to
destroy it, which created a computationally untenable (and very complex) static
analysis problem in large programs.

### Alternative Solutions

Another option would be to forbid destruction if a particle defines any other
particles besides itself, but that just creates toil for the human developer
that they can get wrong, not to mention a maintenance nightmare where you have
to update destruction statements any time you add a new required position to an
action.

We also could require explicit destruction statements for all created local
particles, but why? Why keep something around that you can't reference anymore
anywhere in the program?

Originally I chose to auto-delete particles in reverse order of their creation
instead of reverse order of their position definitions, but that gets a bit
confusing when you move particles around (especially if you moved a particle
from an action-defined position into a local position, where you have no idea
when the action-defined position was created). There was an interesting lesson
there, though: creation has to do with positions and can reason about positions,
but destruction always has to do with the particle, because it could have moved
from its creation position into a position with different (looser) constraints.

## Forward Compatibility

Refusing to set an order and requiring that order to happen simultaneously
leaves some of the aspects of destruction up to the implementation details of a
compiler. However, having any form of safe simultaneity does tend to lead toward
similar properties across implementations. Plus, given that any future required
dependencies would have to be expressed in Define code, analysis would still
tell us the required _partial_ order of destruction. Thus we could preserve that
partial order in future implementations if we change our mind.

In a way, we are choosing to impose _no_ restriction, which actually makes it
quite easy to change our minds in the future, since "run this in any order" is a
superset of any given order that we choose. Plus it's not _really_ "any order,"
it's simultaneous.

## Refactoring Existing Systems

I believe this is actually better than the destruction semantics of most
programming languages, because we _have_ the topology of how positions depend on
each other (at least, currently, for potential positions assigned to particles).
However, it is also different than the destruction semantics of other languages.
That means that when we refactor those languages into Define, we may need to
explicitly implement their destruction semantics in some cases.

Otherwise, there was no previous destruction syntax or semantics in Define to
refactor.
