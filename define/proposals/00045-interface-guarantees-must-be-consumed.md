# Define Language Proposal 45: Interface Guarantees Must Be Consumed

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** August 29, 2026
- **Date Finalized:**

## Problems

In [DLP 42 (Dead Code is Forbidden)](00042-dead-code-is-forbidden.md), we banned
putting particles into the interface position of an action unless those
particles were actually used when triggering that action.

However, there is still a way to get unused interface particles to "stick
around" in interface positions: you can trigger the action, it can create
particles in its interface positions (or move particles there or leave them
there), and then the caller does nothing with those particles.

Supporting this involves some degree of actual complexity in the validation and
code generation phase of the compiler, where we have to support interface
position particles potentially "sticking around."

It also allows memory leaks where an action produces a particle that is never
consumed but which sticks around for longer than necessary.

The question that faces us is: is there any legitimate reason to do that?

One case is actions that must trigger only once. They never destroy the particle
in their trigger position, and a future access-control system prevents external
callers from destroying that particle. This is probably the simplest and most
intuitive way to have single-triggering actions.

However, one _could_ still accomplish single-triggering actions via an implied
position that indicates the action has already run. You would create something
like `position</action_has_run>` and the action itself would fill that and then
a future access-control system would prevent others from modifying it. That's
actually more intuitive in an access-control system, because all you have to say
is "Only `action</foo>` can access `position</action_has_run>` at all" as
opposed to saying "Only `action</foo>` can destroy its own trigger position but
anybody can put something into it," (a slightly more complex rule).

The other case that could matter is optional "return" values from actions. An
action provides a set of outputs that not all consumers need. However, that
actually ends up being bad code for two reasons: (1) it allows for potential
memory leaks (2) that pattern often involves actions doing work they do not need
to do, in order to produce that optional result.

If you really did want optional return values, you could theoretically still
accomplish them by "returning" a position that has child names, and then the
caller doesn't need to access every child name (provided they at least access
the top-level parent name).

Thus, it seems that allowing this pattern creates risks and compiler complexity
in exchange for little to no value.

## Solution

We set a new rule for code in an Action Statements Block.

**Callee**: An action that is triggered within an Action Statements Block.

**Caller**: The action whose Action Statements Block we are analyzing.

**At the end of any Caller's Action Statements Block, there must be no particles
in the interface positions of any Callee.**

In other words, if a Callee has a Guarantee that ensures one of its interface
positions is occupied, that position must be emptied by the time the Caller
ends.

### Never Infer Occupied on Action Interface Positions

When you combine the rule in
[DLP 42 (Dead Code is Forbidden)](00042-dead-code-is-forbidden.md) about
interface particles needing to be used by a callee with our rule here, it has a
surprising consequence:

**We must never infer an occupied requirement on any action interface position
represented within a position reference.**

This doesn't affect the current action's own interface requirements (we can of
course still infer that those are occupied, otherwise you couldn't pass
particles to an action!). It only affects chained names that contain an action
in them.

For example, let's say you had this as the first line of code in an Action
Statements Block:

`create a particle in position<iface>::action</parent>::position<parent_iface>::action</child>::position<input>.`

Where `position<iface>` was one of this action's (the caller's) interface
positions. We would infer that `position<iface>` was occupied, that's fine,
because that's the Caller's position. But we would throw an error about
`position<iface>::action</parent>::position<parent_iface>` being empty---we
would not infer anything.

Considering all of our existing rules, this actually translates into an even
stronger rule than the one above:

**All requirement inference stops at the first action in a chained name.**

At the beginning of an action, every callee interface position is known to be
empty. Therefore nothing beneath that interface position can contribute an
inferred requirement from the caller. Only positions in the chain before an
action can have inferred requirements.

### Implied Actions

If the Caller implies an action and that action implies a position, it's fine
for that position to still be occupied at the end of the Caller. These rules do
not apply to implied actions filling implied positions. They apply only to the
interface positions of actions.

However, the rules _do_ apply to the interface positions of implied actions, so
if you trigger `action</foo>` and it produces `action</foo>::position<output>`
then you must consume `action</foo>::position<output>` in the Caller.

### Implied Positions of Callee Actions

The rules apply in an interesting way when you trigger a non-implied action and
it guarantees implied positions. For all of these examples, imagine that we have
an `action</foo>` that implies (and fills) `position</bar>`, and that
`action</foo>::position<run>` is the trigger position of `action</foo>`.

First, imagine that we do this:

`create a particle in position<box>::action</foo>::position<run>`

That fills `position<box>::position</bar>`.

If `position<box>` is a local position, you don't need to do anything explicit,
because it will be auto-destroyed at the end of the action (and thus all of its
interface positions are inherently "accessed").

But what if `position<box>` is an interface position? Well, it turns out that
you _still_ don't need to do anything, because we are engaged in one of the
_allowed_ forms of guarantee and requirement propagation: we have filled a
_position_ child of our _own_ interface position, which thus must have been
empty at the start of our action.

But now what if `action</foo>` is a grandchild, like this?

```define
create a particle in position<box>.
create a particle in position<box>::action</parent>::position<holder>.
create a particle in position<box>::action</parent>::position<holder>::action</foo>::position</run>
```

That fills `position<box>::action</parent>::position<holder>::position</bar>`.

Uh oh, that's a different story, because we had to create `position<holder>`.
That means we must have to trigger `action</parent>`. And _that_ means that we
_have_ to consume `action</parent>::position<holder>`. So we don't actually have
to worry about `position<holder>::position</bar>` so much, because worrying
about `position<holder>` solves the problem for us. But it's worth noting that
these "grandchild" positions that pass an action boundary will never be
preserved across actions, just like all other positions that cross an action in
a chained name.

### Entry Points May Not Have Interface Positions

This adds one additional rule:

The entry point action of a program may not have interface positions, because it
would be impossible for those interface positions to ever be consumed. (We know
exactly what the view point particle's behavior is, and it never consumes those
positions.)

Some language designers might choose to make specially-named interface positions
that create some sort of guarantee back to the OS, but one of Define's general
principles is not to give special meaning to names like that. Instead, when we
need to do specific OS interactions, there will be special mechanisms for doing
so.

In reality, the way that OSes pass arguments in is by storing data in a special
location in memory, and the way that processes set their exit codes is by
calling a particular syscall or API. Representing these as magical "interface
positions" is the sort of syntactic sugar that Define abhors.

### Conceptual Model

Conceptually, this means that interface positions are now state designed only to
be used directly by an action. If you want shared or persistent state that lives
beyond this action, you must use implied positions or put something in this
action's output interface positions. This also helps give a clearer distinction
between when you would use implied vs interface positions.

## A Real Program

## Why This is the Right Solution

So, I had actually done a _ton_ of work on the compiler to support propagating
guarantees and requirements for interface positions. However, once I got into
implementation for
[DLP 44 (Deterministic Automatic Concurrency)](00044-deterministic-automatic-concurrency.md).
I started to run into a lot of very specific situations in which we had to
support weird or confusing forms of generated code merely to allow for this
pattern that seems like it should never be happening. It also required many
extra tests, and was confusing as a developer _writing_ Define when I was
supposed to use interface positions vs implied positions.

From a conceptual lens, the problem I was running into was the whole "using an
action as a container of data" problem that we were still allowing. Any way I
sliced it, as long as interface positions could somehow stick around after
triggering a callee, the programmer could figure out _some_ way to make an
action into a container of data instead of what it's actually conceptually
_intended_ to be: a machine that a particle can run.

## Forward Compatibility

In general, forbidding patterns is safe for forward compat. It's much more
dangerous to _allow_ this up front and then later discover we have to forbid it,
because that would be a very complex (though possible) refactoring task.

## Refactoring Existing Systems

Thankfully I made this decision before any stable release of Define, so there
are no existing systems to refactor. Those that did require refactoring would
have to logically work through how to convert interface position guarantees on
grandchild callees to mere position children on the current caller's interface
position. That's actually possible, and it's how we fixed most of the tests that
did this. The other option is to logically convert some things to use implied
positions, but the logic for figuring out how to do that is a bit more complex,
statically.
