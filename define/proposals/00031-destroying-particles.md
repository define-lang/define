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

At the end of an Action Statements Block, any particles still existing in
positions that are only defined locally within that Action Statements Block are
automatically destroyed in reverse order of their position definition
statements.

In essence, the compiler inserts destruction statements at the end of an Action
Statements Block to implement this. Currently, the language allows the compiler
to deterministically know which positions will or won't contain particles.

In the future, if the compiler is uncertain about whether a position still
contains a particle, the compiler will insert code that only destroys particles
in positions if there is a particle there.

Hitting a `wait until` statement does _not_ count as exiting the Action
Statements Block, and does not trigger automatic destruction. Automatic
destruction occurs only when a position can no longer possibly be referenced.

### Optimization of Destruction

In situations where the compiler knows that destruction is free of side effects
(there are no action triggers watching for the destruction of that particle,
including no triggers watching any of the other positions that particle
transitively defines), the compiler may choose to automatically destroy local
particles within an Action Statements Block the instant they are no longer
relevant to the code in the Action Statements Block.

When safe, the compiler may choose to destroy multiple particles simultaneously
(in parallel).

### Cascading Destruction

When a particle is destroyed, all of the particles in the positions it defines
are also destroyed.

Conceptually what happens when this occurs is that qualities are unassigned from
the particle in reverse order to how they were assigned to it. (Note: because
requirement statements assign qualities topologically in order according to
their dependency tree, this inherently means that qualities will be removed in
reverse topological order when that matters.)

Before a position quality is unassigned, its particle is destroyed.

Thus, in our example above in the Trigger Paradoxes section, the `ensure_floor`
action would not run when destroying `position<house>`, because that action
would be removed from `position<house>` before `position</floor>` was removed.

During this process we inherently violate position constraints on the particle
we are destroying. As such, this behaves similarly to creating a particle with
respect to position constraints: all constraints defined by the position
definition are suspended at the start of destruction until destruction
completes.

Before removing an action from a particle, destroy all particles that are still
contained in positions defined in the Action Definition Block, in reverse order
of when the positions were defined. (Reverse the order in which the position
definitions are written in the Action Definition Block.) Destroying these
particles may not trigger the action that we are mid removing (but may trigger
another action or `wait until` block). Once we start removing an action from a
particle (and thus have to destroy the particles it defines) it may no longer
trigger or check its conditions.

Destruction completes as though it were a written series of unassignment and
destruction statements in code to perform all necessary unassignments and all
cascading of destruction. Thus, any action that triggers due to destruction of a
particle fires immediately after its destruction is complete. This means that if
a particle defines a position, the destruction of a particle in that child
position may trigger an action asynchronously before the destruction of the
parent particle is complete.

The compiler may optimize this process and does not have to actually manually
unassign every quality, it just needs to ensure identical behavior occurs as if
it _had_ done so.

Actions that would trigger due to the removal of a quality from a particle do
not fire due to this quality removal process that happens automatically during
destruction.

## A Real Program

```
define the potential position<mv:example.com:example:/kitchen>.
define the potential position<mv:example.com:example:/trash_can>.
define the potential position<mv:example.com:example:/backyard>.
define the potential position<mv:example.com:example:/toy>.
define the potential position<mv:example.com:example:/bedroom> {
    it also assigns the position</toy>.
}
define the potential position<mv:example.com:example:/house> {
    it may only contain particles where {
        it has the position</kitchen>.
        it has the position</bedroom>.
        it has the position</backyard>.
    }
}

define the potential action<mv:example.com:example:/enter_house> {
    it also assigns the position</house>.

    define the position<door>.

    it happens when {
        the position<door> has a particle.
    } and it does {
        create a particle in position</house>.
        create a particle in position</house>::position</bedroom>.
        create a particle in position</house>::position</backyard>.
        create a particle in position</house>::position</kitchen>.
        destroy the particle in position<door>.
    }
}

define the potential action<mv:example.com:example:/make_bed> {
    define the position<do_it>.
    define the position<bed>.

    it happens when {
        the position<do_it> has a particle.
    } and it does {
        create a particle in position<bed>.
        destroy the particle in position<do_it>.
    }
}

define the potential action<mv:example.com:example:/get_angry> {
    it also assigns the action</make_bed>.

    define the position<cooled_down>.
    define the position<got_angry>.

    it happens when {
        NOT action</make_bed>::position<bed> has a particle.
    } and it does {
        create a particle in position<got_angry>.
        define the position<toy>.
        create a particle in position<toy>.
        create a particle in position<cooled_down>.
        # The particle toy is now automatically destroyed here.
    }
}

define the potential action<mv:example.com:example:/clean_kitchen> {
    it also assigns the action</enter_house>.
    it also assigns the position</trash_can>.

    define the position<remember_to_clean>.
    define the position<trash>.

    it happens when {
        the position<remember_to_clean> has a particle.
        AND
        the position<trash> has a particle.
    } and it does {
        create a particle in action</enter_house>::position<door>.
        move the particle in position<trash> to position</trash_can>.
        destroy the particle in position</trash_can>.
        destroy the particle in position<remember_to_clean>.
    }
}

define the potential action<mv:example.com:example:/run_program> {
    it happens when {
        # Some syntax that causes it to trigger when the program starts
    } and it does {
        define the position<person> {
            it may only contain particles where {
                it has the action</clean_kitchen>.
                it has the action</get_angry>.
                it has the action</make_bed>.
                it has the position</house>.
            }
        }
        define the position<dog>.
        create a particle in position<dog>.

        # This assigns positions in the following order:
        # 1. position</house>
        # 2. position</trash_can>
        # 3. action</clean_kitchen>
        # 4. action</make_bed>
        # 5. action</get_angry>
        #
        # Most of that happens via quality implication statements.
        create a particle in position<person>.

        create a particle in position<person>::action</clean_kitchen>::position<trash>.

        # This creates the house by calling enter_house. It assigns the following positions
        # to position</house>, in the following order:
        # 1. position</kitchen>.
        # 2. position</bedroom>.
        # 3. position</backyard>.
        #
        # Note that it creates particles in a different order (which doesn't matter).
        create a particle in position<person>::action</clean_kitchen>::position<remember_to_clean>.

        # We are a magical person who can clean the kitchen and make the bed simultaneously.
        create a particle in position<person>::action</make_bed>::position<do_it>.

        # Note that the entry into a wait until section does not count as
        # exiting the current action, so destruction does not yet occur.
        wait until {
            NOT the position<person>::action</clean_kitchen>::position<remember_to_clean> has a particle.
            AND
            the position<person>::action</make_bed>::position<bed> has a particle.
        }

        # This triggers get_angry.
        destroy the particle in position<person>::action</make_bed>::position<bed>.
        create a particle in position<person>::action</make_bed>::position<do_it>.

        wait until {
            the position<person>::action</make_bed>::position<bed> has a particle.
        }

        destroy the particle in position<person>::position</house>::position</bedroom>.
        # Now automatically, at the end of the action, here is what happens:
        # 1. The particle in position<person> starts destruction, which
        #    triggers these changes on that particle:
        #    (a) Destroy the particle in action</get_angry>::position<got_angry>.
        #    (b) Destroy the particle in action</get_angry>::position<cooled_down>.
        #    (c) Remove the action</get_angry>
        #    (d) Destroy the particle in action</make_bed>::position<bed>.
        #    (e) Remove the action</make_bed>
        #    (f) Remove the action</clean_kitchen>
        #    (g) Remove the position</trash_can>
        #    (h) Start destruction of the particle in position</house>,
        #        which triggers these changes on that particle:
        #        i. Destroy the particle in position</backyard>.
        #        ii. Remove the position</backyard>.
        #        iii. Remove the position</bedroom> (already empty).
        #        iv. Destroy the particle in position</kitchen>.
        #        v. Remove the position</kitchen>.
        #   (i) Destruction of the particle in position</house> completes. If
        #       any actions were watching for position<person>::position</house> to
        #       become empty, they would now fire (though this could only be a "wait
        #       until" block).
        # 2. Destruction of the particle in position<person> completes. If any
        #    actions were watching for position<person> to become empty, they would now
        #    fire (though this could only be a "wait until" block.)
        # 3. The particle in position<dog> is destroyed, and any relevant trigger
        #    conditions check themselves.
        # 4. position<person> and position<dog> simultaneously cease to exist and may no
        #    longer be referenced by any part of the program.
    }
}
```

## Why This is the Right Solution

The cascade is specified in the only order that guarantees safe destruction.

We destroy action-defined positions and local particles in reverse order of
their definitions because we need some deterministic ordering (so that we can
statically analyze programs and know exactly what happens) and because that is
the easiest sequence for the compiler to check (position definition order is
completely static). It also might help if we ever introduce a future syntax that
allows positions to refer to each other in their definitions (it would give us
some hope that that syntax continues to work correctly during destruction).

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
when the action-defined position was created).

## Forward Compatibility

Any time we set an order for anything, we create a forward compatibility risk,
as programmers then rely on that being the order. The ordering described in this
proposal should be safe, but there's a slight chance we would have to change the
ordering of destruction for local positions. For the cascade, I believe I have
specified it to occur in the only possible logical order that is safe and
prevents impossible situations (like trying to refer to positions that don't
exist while tearing down a particle).

Otherwise, the syntax is unambiguous. The "end of action" behavior is also
unambiguous because we can tell where actions end in the syntax.

## Refactoring Existing Systems

I believe this is actually better than the destruction semantics of most
programming languages, because we _have_ the topology of how positions depend on
each other (at least, currently, for potential positions assigned to particles).
However, it is also different than the destruction semantics of other languages.
That means that when we refactor those languages into Define, we may need to
explicitly implement their destruction semantics in some cases.

Otherwise, there was no previous destruction syntax or semantics in Define to
refactor.
