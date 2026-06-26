# Define Language Proposal 42: Dead Code is Forbidden

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** June 26, 2026
- **Date Finalized:**

## Problems

### 1: The Developer Productivity Trade-off of Dead Code

Dead code is a constant problem that developers have. Cleaning it up doesn't
matter _that_ much, in terms of developer productivity or experience, but it
does have _some_ effect. It removes things that you have to maintain or read.
The problem has always been that it's expensive to detect and to prove that it's
safe to remove, which makes it hard to justify the investment to actually remove
it.

Many languages allow reference things through reflection, too, which makes this
even harder---you can't statically tell whether any symbol is actually
referenced, because the language allows reference mechanisms that _could_ be
used. In a large enough company/codebase, you can't know every mechanism that
everybody is using, and you end up having to either (a) keep around a ton of
dead code or (b) build very complex systems to infer and test whether code is
actually dead (and then you always end up removing some code that actually was
still alive, anyway, and causing some bug or incident).

### 2: Dead Code Can Complicate Compilation

There are certain circumstances in which we can simplify the compiler (and
improve its performance) if we know that certain types of dead code can't
exist---that something will be guaranteed to reference them.

<!-- TODO: I had a specific example for Define but I need to remember it again. -->

### 3: Dead Code Adds Compilation Time

If you have a line of code that doesn't actually do anything, it still has to be
compiled by the compiler. That's not usually a huge deal by itself, but it can
be a pretty big deal if the dead line references a file that otherwise wouldn't
be referenced, causing the compiler to have to load and compile a whole file.

### 4: Dead Code is Often a Mistake

A lot of dead code is just variables the programmer defined while they were
coding in this session and forgot to delete, or lines that were from some
previous attempt at a change and are no longer needed. Even AI coding assistants
do this when they get into long chains of complex changes that are stacked on
top of each other, not realizing that some part of the system is now dead.

### 5: Actions Are Not Containers

It can be very tempting for developers unfamiliar with how Define is supposed to
work to use an action like a container for positions instead of an actual action
that gets triggered. You can just set up a bunch of interface positions, store
things in there, and then never actually call the action. However, this leads to
very strange programs that are very hard to understand. Not only does it cause
questions like "Why does this chain say `action` in it?" it creates flows that
are very hard to comprehend---you have an action with a hundred positions inside
of it that function very similarly to how global variables function in other
programs (and which have a lot of the same problems).

It also violates the general principle of Define that there is only one way to
do things. Although we can't enforce that everywhere, it does seem like this
pattern in particular should be clamped down on.

## Solution

In Define, the compiler will detect and forbid all forms of dead code that it
can.

The definition of dead code is something that could not possibly affect the
logic or intentional behavior of the output program.

Not all dead code can be deterministically detected, but anything that we are
_confident_ is dead should be forbidden.

### Unreferenced Names

The simplest thing to detect is local names that never get referenced in the
local context where they are supposed to be referenced.

- **Unreferenced Interface Positions**: Interface positions defined on actions
  that are never referenced within _that_ action. (Even if they are referenced
  outside of the action, because this is how we forbid the "actions are
  containers" pattern.)
- **Unrefrenced Local Positions**: A position defined inside of an Action
  Statements Block that is never referenced inside of that Action Statements
  Block.
- **Unreferenced Quality Implications**: Already forbidden in
  [DLP 22 (Atomic Qualities)](00022-atomic-qualities.md).

### Unnecessary Quality Assignments on Local and Interface Positions

The compiler can sometimes detect that a quality constraint has been placed upon
a position that is not necessary. The is the simplest on local positions inside
of Action Statements Blocks.

The first thing to know about constraints is that if a _move_ requires the
constraint it is always alive. That is, if I move a particle from position A to
position B, and position B requires a particular constraint to exist on the
particle, that constraint cannot be dead.

The easiest thing to be confident about, in terms of dead code, on a local
position is **untriggered actions**: If an action is explicitly assigned to a
particle and it can be triggered but never is. For example, `action</foo>` has a
trigger on `action</foo>::position<run>` being filled, but that position is
never filled. Actions that get transitively assigned by quality implications
would not be considered to be dead. Destructors also would never be considered
dead, since all particles will eventually be destroyed. Deadness is about what's
written in code.

Dead **child positions** are also detectable: they are not directly referenced
within the action's code and are not required by any moves.

Since we forbid dead interface positions, we can also make these same statements
about an action's interface positions (otherwise we couldn't, because code
outside of the action could be using the interface position as storage).

### Qualities on Global Positions

Tracking the liveness of qualities assigned to global positions is much harder.

Theoretically the compiler could track the liveness of every constraint
reference it sees and report references that it finds to be dead at the end of
compilation. This is made tricker, however, by the fact that we could compile
something that is then consumed later by other things, so we have to be somewhat
conservative. For now, we will not attempt to detect whether a quality assigned
to global position is alive or dead.

### Transitive Dead Code

Code can be "transitively dead," where it's only referenced by dead code.
Attempting to detect that in a single compiler pass can be quite difficult. For
now we will not attempt to detect it. However, the compiler is also not
_forbidden_ from detecting it in a single pass (it's just computationally and
implementation-ally complex).

## A Real Program

### Unreferenced Interface Position

```define
define the potential action<define-lang.org:bank:/deposit> {
    define the position<run>.
    define the position<amount>.  # DEAD: never referenced inside this action.

    it happens when {
        the position<run> has a particle.
    } and it does {
        destroy the particle in position<run>.
    }
}
```

### Unreferenced Local Position

```define
it happens when {
    the position<run> has a particle.
} and it does {
    define the position<scratch>.  # DEAD: never referenced again in this block.
    move the particle in position</states/locked> to position</states/unlocked>.
}
```

### Untriggered Action

```define
define the position<gate> {
    it may only contain particles where {
        it has the action</transitions/coin>.
        # DEAD: assigned and triggerable, but its <run> is never filled.
        it has the action</transitions/force_unlock>.
    }
}
create a particle in position<gate>.
create a particle in position<gate>::action</transitions/coin>::position<run>.
```

### Dead Child Position

```define
define the position<gate> {
    it may only contain particles where {
        it has the position</states/locked>.
        it has the position</states/maintenance>.  # DEAD: never referenced, no move requires it.
    }
}
move the particle in position<gate>::position</states/locked> to position</states/unlocked>.
```

## Why This is the Right Solution

Everything listed in this proposal is code that we can be confident is dead.

There are some downsides to forcing the removal of dead code. For example, a
developer might be in the middle of writing something, and it can be annoying to
get a compiler error just because you're not done with something yet. However,
my view is that the long-term benefits outweigh the minor inconvenience or
annoyance, here.

Another downside here is that this affects the performance of the compiler,
especially in temrs of memory, because it has to track whether things actually
get referenced or not. My view is that this is a reasonable trade-off,
especially because most names _should_ be referenced, and thus the data
structures required to track whether something is referenced or not can actually
shrink over time as the compiler runs.

## Forward Compatibility

Overall, this should actually enhance forward compatibility, because we are only
banning something. It's hard to start off with something being allowed and then
banning it, but it's very easy to start off by banning something, because it's
simply not going to _be_ there in future codebases we have to deal with.

## Refactoring Existing Systems

I actually think this will be a cool advantage for rewriting something into
Define, because if you successfully translate another language into Define,
you'll be able to deterministically remove dead code from the system.
