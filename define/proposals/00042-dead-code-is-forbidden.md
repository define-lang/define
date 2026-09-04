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

For example, if we know that all interface positions are used, it removes all
checks during code generation as to whether or not interface positions are
actually required, and allows us to know that various variables and data
structures can never be empty.

<!-- TODO: There are more good examples, even better ones about correctness. -->

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

### 6: Complex Action Triggering

Theoretically, Define's syntax allows one action to fill an interface position
of an action and then have a _different_ action trigger it. This is
indistinguishable from the "action container" pattern, and also is very
confusing---why would you basically pass an argument to a function and then not
call it?

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
- **Unreferenced Local Positions**: A position defined inside of an Action
  Statements Block that is never referenced inside of that Action Statements
  Block.
- **Unreferenced Quality Implications**: Already forbidden in
  [DLP 22 (Atomic Qualities)](00022-atomic-qualities.md).

### Unnecessary Quality Assignments

The compiler can sometimes detect that a quality constraint has been placed upon
a position that is not necessary. However, this is a bit more complex, so there
are more rules to describe.

There are a few different rules below. The rules about a constraint being alive
override the rules about it being dead.

#### Only Direct Constraints Can Be Dead

Only actual lines of code written inside of an action can be dead code.
Constraints that are assigned _only_ transitively via Quality Implication
Statements are never dead code.

#### Dead Child Positions

Any directly-declared position constraint that is not referenced inside of that
same action is dead code.

#### Untriggered Actions

If an action is directly assigned to a particle and it can be triggered but
never is, it is a dead constraint. For example, `action</foo>` has a trigger on
`action</foo>::position<run>` being filled, but that position is never filled.

#### The Move Use Exception

When a child position is directly referenced on a particle, or an action
assigned to that particle is triggered, the matching constraint is alive both on
the position currently holding the particle and on the position where the
particle originated (where it was created or arrived via an Automatic Action
Requirement).

This handles cases where you move a particle from A to B and then reference
children on B only.

#### The Contracted Position Exception

Satisfying the contracts of actions is sufficient to mark a constraint as alive.

More specifically, a constraint is "alive" (overriding the rules above) on a
position if a particle _originating_ in that position (either it arrived as an
Action Requirement or it was created in that position) either:

1. Is moved into (or originally created in) any contracted position that a
   callee requires occupied (has an Automatic Action Requirement on), and that
   contracted position has that constraint.
2. Has a final position representing an Automatic Action Guarantee of this
   position, and that final position has that constraint. (That is, it ends up
   in a contracted position that our callers expect to be occupied.) To be
   clear, this can happen either by the particle getting moved into that
   position (and then staying there at the end of the action) or being directly
   created in that position (and then staying there at the end of the action).

To be clear, this means that if a particle moves to an intermediate local
position, that does _not_ make all the constraints on that intermediate local
position automatically "alive." For example, moving A to B to C, where A and B
are local positions and C is a contracted position does _not_ make the
constraints on B alive just because they are constraints on C. It would only
make the constraints on A alive.

In order for the constraints on B to be alive, they would have to be referenced
with B as the parent name. So if the constraint is `position</thing>` then the
code would have to explicitly reference `position<b>::position</thing>` in order
for that constraint on `position<b>` to be considered alive.

### Untriggered Implied Actions

If an action is implied and that action itself is not triggered inside of the
implying action (no matter how else it is referenced in the implying action)
then the _implication_ is a dead dependency.

Note that this inherently denies implying constructors or destructors, entirely.

### Untriggered Grandchild Actions

Imagine that we have a line of code like this:

`create a particle in action</foo>::position<iface>::action</bar>::position<input>`

What if `action</bar>` is never triggered? That makes `action</bar>` into dead
code even though it's not a directly-written constraint on any local position.

Thus we have to expand our rules to say that any action that appears in a
position reference is dead code if it's not triggered in this action.

### Unnecessary Use of Interface Positions

There's also a particularly tricky case for dead code, like this:

```define
create a particle in action</foo>::position<iface>.
move the particle in action</foo>::position<iface> to position<local>.
create a particle in action</foo>::position<iface>.
# This triggers action</foo>.
create a particle in action</foo>::position<run>.
```

There is no good reason to write those first two lines of code, and it makes
later analysis more complex in the compiler (especially once we get into code
generation and we have to determine dependencies between actions, as will come
up in a later proposal). It is much simpler for the compiler if it can make a
basic assumption: any particle that arrives in an interface position will be
there when the action executes. Since there's no good reason to allow that code
and it makes things simpler for the compiler, we declare any use of an interface
position as purely a waypoint to be dead code.

This is also dead:

```define
create a particle in action</foo>::position<iface>.
# This triggers action</foo>.
create a particle in action</foo>::position<run>.
destroy the particle in action</foo>::position<iface>.
create a particle in action</foo>::position<iface>.
```

That create is dead, but the destroy before it is alive.

All of that said, this is still perfectly valid:

```define
create a particle in action</foo>::position<iface>.
create a particle in action</foo>::position<run>.
destroy the particle in action</foo>::position<run>.
create a particle in action</foo>::position<run>.
```

In other words, you can keep re-using a particle in an interface position, you
just can't use an interface position as nothing other than a waypoint.

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
especially in terms of memory, because it has to track whether things actually
get referenced or not. My view is that this is a reasonable trade-off,
especially because most names _should_ be referenced, and thus the data
structures required to track whether something is referenced or not can actually
shrink over time as the compiler runs.

### Forcing Action Triggering

Forcing action triggering fixes Problem 6 from above, about different actions
filling in the interface positions of an action but only one of those actions
actually triggering the action.

I'm not 100% confident that this is the right restriction; there could be some
legitimate reason to allow that (very weird) pattern. However, at the moment it
doesn't make sense to me to allow it. If you're going to pass arguments to a
function, you should actually call that function.

This also handles one of the more confusing parts of Define, which is "did I
actually trigger that action or not?" Now you will know that if an action is
referenced, you _always_ triggered it or the compiler will complain. That's
particularly important for a future where your libraries can do automated
refactorings of your code when they upgrade your code---otherwise a library
could accidentally perform a change that caused an action to not be triggered,
and it would be very hard to notice.

### Denying Implied Destructors

The logical reason to imply a destructor would be something like "if this action
_exists_ on a particle, then something must always be cleaned up about this
particle when it is destroyed."

Well, first off, just because you assign an action to a particle, that doesn't
mean the program will actually trigger that action (there is a way for us to
detect that, and maybe a future proposal will do it, but I'm concerned about the
memory requirements for tracking liveness for every action call throughout a
program). So you could be assigning a destructor (which will always run, because
every particle is eventually destroyed as long as a Define program exits
normally) to clean up a situation that never happens.

But let's imagine we could fix that problem, and force all actions to trigger
(which we might be able to do). In that case, let's examine the logic more
deeply by taking a specific example.

Let's imagine that we have an action that takes a lock, and you want to release
the lock when the action's parent particle is destroyed. What would a destructor
actually do in that case? Well, you must have stored the lock as a particle
somewhere that the destructor can access. That means an implied
`position</lock>` that both `action</lock>` and `action</unlock_on_destroy>`
could reference. Oh, so that means the lock is actually a _child_ particle of
the parent, which will get destroyed simultaneously with its parent. So then why
isn't the destructor just on `position</lock>`, which `action</lock>` already
had to reference? That also unlocks the lock no matter what happens or what
action set it.

Well, you could say "but I only want to auto-unlock it if it was set by
`action</lock>`. But implying a destructor doesn't guarantee that
`position</lock>` was set by `action</lock>`! Theoretically, there's a future
where we have access controls on which actions can touch which positions, and
you could make it so that only `action</lock>` and `action</unlock_on_destroy>`
can touch `position</lock>`. Even then, why wouldn't you just put the destructor
on `position</lock>`?

Well, you say, maybe I want a lock that doesn't auto-unlock on destroy. Maybe
it's locking something outside of the program. Well, that sounds like a totally
different position definition, like you'd want `position</auto_lock>` and
`position</manual_lock>` or something.

There's actually probably an even better design for that situation too, where
your lock is a local position and you choose whether you want to add the
destructor or not, without having to change naming.

I'm open to the idea that there's a design pattern that needs implied
destructors, but I'm not aware of one yet.

### Denying Implied Constructors

On constructors, the logic for implying a constructor would be something like
"this action can know that its parent particle was always initialized in a
particular state." However, that doesn't really help the action, because it
can't know whether that state _changed_ since the constructor was called. That
is, no real invariant is actually provided by having a constructor be implied.

## Forward Compatibility

Overall, this should actually enhance forward compatibility, because we are only
banning something. It's hard to start off with something being allowed and then
banning it, but it's very easy to start off by banning something, because it's
simply not going to _be_ there in future codebases we have to deal with.

## Refactoring Existing Systems

I actually think this will be a cool advantage for rewriting something into
Define, because if you successfully translate another language into Define,
you'll be able to deterministically remove dead code from the system.
