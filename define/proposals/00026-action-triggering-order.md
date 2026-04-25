# Define Language Proposal 26: Action Triggering Order

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** January 22, 2026
- **Date Finalized:**

## Problems

We are able to define actions. We will get around to defining their trigger
conditions and how you define what they do. But first, we have to resolve a
problem: if multiple different actions trigger based on the same conditions,
what happens?

For example, imagine this program:

```
define the potential position<mv:example.com:example:/run_triggers>.
define the potential position<mv:example.com:example:/my_ball>.
define the potential position<mv:example.com:example:/left>.
define the potential position<mv:example.com:example:/right>.

define the potential action<mv:example.com:example:/move_left> {
    this dimension point must have the position<mv:example.com:example:/my_ball>.
    this dimension point must have the position<mv:example.com:example:/left>.
    this dimension point must have the position<mv:example.com:example:/run_triggers>.


    it happens when {
        the position<mv:example.com:example:/run_triggers> has a dimension point.
    } and it does {
        move the dimension point in position<mv:example.com:example:/my_ball> to position<mv:example.com:example:/left>.
    }
}

define the potential action<mv:example.com:example:/move_right> {
    this dimension point must have the position<mv:example.com:example:/my_ball>.
    this dimension point must have the position<mv:example.com:example:/right>.
    this dimension point must have the position<mv:example.com:example:/run_triggers>.

    it happens when {
        the position<mv:example.com:example:/run_triggers> has a dimension point.
    } and it does {
        move the dimension point in position<mv:example.com:example:/my_ball> to position<mv:example.com:example:/right>.
    }
}

define the position<x> {
    it may only contain dimension points where {
        it has the action<mv:example.com:example:/move_right>.
        it has the action<mv:example.com:example:/move_left>.
    }
}
create a dimension point in position<x>.
create a dimension point in position<x>::position<mv:example.com:example:/my_ball>.
create a dimension point in position<x>::position<run_triggers>.

define the position<new_spot>.
create a dimension point in position<x>::position<mv:example.com:example:/my_ball>.
move the dimension point in position<x>::position<mv:example.com:example:/my_ball> to position<new_spot>.
```

Essentially what that program does is create a ball, move it to two different
locations ("left" and "right"), then create another ball and move it into a new
spot. It's a rather confusing program, but it's a _valid_ program.

What actually happens when that program runs, though? How do we know what order
the triggers run in? When do they finish and return control to the program after
that? We have a few options for what can happen.

### Forbid Multiple Actions From Triggering

We could implement a rule in the compiler that multiple actions may not trigger
on the same set of conditions, and cause an error to occur if that happens. In
addition to this being extremely limiting, it leads to breaking programs in
unexpected ways when two different parts of a program (or two different
libraries) suddenly trigger on the same set of positions.

### Ban Triggers on Shared Positions

You could say that an action may only trigger based on the positions it defines
(and not positions it depends on). This is the "safest" solution as it
guarantees there is no simultaneity in the language. Of course, we would
eventually need some way to express concurrency, as many real universes need
concurrency, and when we did, we could end up back in the same situation again:
what happens if two concurrent threads both attempt to modify an action's
defined positions? So in reality, this option sounds nice, but it doesn't really
solve our problems in the long term.

There are mechanisms of simultaneity that would theoretically still work, but
every way I think about them, they would require zero data sharing between
simultaneous threads, essentially meaning you were running two separate
universes in parallel that can't interact with each other or with the original
universe that spawned them. I'm not sure what the point is of having that as
language semantics.

There is possibly still an automatic concurrency mechanism in this model, where
the compiler traces through the action graph and determines which actions don't
depend on each other and thus can be run in parallel. One of the dangers,
though, is that if you accidentally introduce some data dependency between
multiple actions, the runtime behavior of the program changes (it stops running
things in parallel when it was doing so before).

Also, doing the static analysis for that automatic concurrency model might
require very complex static analysis, although it can probably be simplified by
making the compiler expose what shared positions an action depends on (which our
syntax already exposes).

### Defined Ordering

We can somehow specify an order for the triggers to resolve in. In this model,
we would say one trigger runs, completes fully, and then another trigger runs
and completes fully.

#### Definition Order

The first way we could pick an order is that we could say "whichever action was
defined first triggers first." In the above program, that means the ball would
first move left and then move right. Then we would create a new ball and move it
to `new_spot`.

The problem with this is that it is not super clear to the programmer what will
happen. What's even more confusing is: those definitions are actually going to
be in separate files. So what does "first" mean? It would have to mean "the
order that the compiler encountered them in." Except in a larger program, that
order might as well be random. So this option doesn't work.

#### Assignment Order

We could choose to order actions in the sequence that they were _assigned_ to
the dimension point. In the above example, this would cause the ball to move
right, then move left, and then we would create a new ball and then move it to
`new_spot`.

This gives some very unintuitive and unexpected semantics to the order in which
you write the `it has the` statements in a position definition (or the order in
which you manually assign qualities to a dimension point). However, more
importantly, it's possible for actions to be assigned to a dimension point via
quality requirement statements. (In other words, it's possible for actions to be
dependencies of other actions.) This means that actions get assigned to a
dimension point in an order that is invisible to the programmer and can randomly
change as you change what actions require what other actions.

#### Explicit Ordering

There are two ways to do explicit ordering.

The first is to create some method where actions can inherently have some sort
of priority over other actions. This either requires assigning numeric
priorities to actions or inventing some complex algorithm that attempts to
analyze actions to determine which one should go first. Both of those options
are incredibly hard for programmers to maintain, confusing to understand in
terms of which actions go first, and are very hard to guarantee get implemented
correctly in the compiler.

The second is to require that every time the program sets off triggers, the
programmer has to explicitly order them. This is actually the solution that
almost every programming language chooses by making people explicitly call
functions (or register "event handlers" in languages like C#). The problem is
that it requires the programmer to know in advance everything that could
possibly trigger based on their actions.

In Define as we currently have it, programmers don't explicitly know that they
are going to trigger an action; it's not super clear in the code that triggers
it. This is a problem we may need to solve elsewhere, but it's also a real
problem in real universes: you don't always know what's going to happen when you
hit a button or walk through a door, and many different things could happen. The
button can be labeled, and hopefully it's labeled correctly, but you never
really know.

As such, in Define, requiring explicit ordering of triggers would mean you'd
have to update every single place in the program that triggers something every
time you added a new action that was triggered by the same positions. This is
very likely to break forward compatibility when code that is distant from you
adds triggers based on what your code is doing. (Whether or not that's a good
idea is a separate discussion, but right now we intend to allow that. Remember,
Define can write bad programs.)

### Simultaneous Triggers

In this option, every action that is triggered by a set of conditions happens at
exactly the same time. Because Define does its best to avoid entering the
concept of time into programs (it generally supports _sequence_ but not
_time_---see the [Concepts](../spec/concepts.md)) this means that both triggers
really happen at the _exact_ same time, conceptually. In other words, the code
of both of them occurs instantaneously, together.

This would require us to solve a few problems.

#### Paradoxes

The program we described above creates a paradox. It moves `my_ball` into both
`left` and `right` simultaneously: a fundamental violation of the nature of
universes: one dimension point cannot be in multiple places at once. Now,
perhaps there are universes where what would really happen is that space would
_bend_ so that `left` and `right` _became the same position_.

This is one of the first places we have to acknowledge the limits of Define
Exactly and hope there is a better solution in Define Approximately. In Define
Exactly, we can't "bend space." All positions are in exact locations that can't
"become each other."

There are other versions of this paradox. One action could assign a quality to
the dimension point while another action destroys the dimension point, or take
any other action on a dimension point while destroying it simultaneously. (The
physical universe in which we live seems to have solved this specific one by
forbidding the destruction of dimension points, but we have to allow destruction
in our universes in order for Define programs to function.)

#### Returning to the Caller

When does execution continue in the program after multiple triggers fire? That
is, in our example program above, when do we define `new_spot` and move
`my_ball` into it?

Because simultaneity is _possible_, we now have to make this decision for
_every_ trigger, because they need to behave consistently whether we trigger one
action or many (otherwise we unpredictably change the behavior of programs when
we create multiple triggers). We have a few options:

1. **Full Async**: Every action triggers asynchronously and execution continues
   immediately, simultaneous with the actions.
2. **Concurrently Execute and Return**: Actions trigger concurrently but pause
   the execution of the current code and return to it when all the triggers are
   complete.
3. **Yield At Conflicts**: The instant that the program encounters a paradox or
   a position in an uncertain state (because that position is being modified by
   another action) it pauses and waits for some other action to resolve the
   paradox, but otherwise everything continues on simultaneously---both the
   async triggers and the original code.
4. **Return After the First Completes**: Actions trigger concurrently but return
   execution to the current code whenever one of them finishes.

Some people might argue that there is some fourth option where you explicitly
specify when they return, but that's similar enough to the "Explicit Ordering"
option above for serial execution that I don't think we need to discuss it here
as a separate option.

We can immediately discard Return After the First Completes as an option: it
creates confusing, unpredictable behavior for programmers. That leaves us with
the remaining options.

##### Full Async

If we choose Full Async, programmers will have to explicitly make their code
wait for some condition that indicates the actions they triggered are complete.

In our above example, the code that creates `position<new_spot>` and then moves
a new ball into it would have to throw a compiler error, because in the Full
Async model, there are _three_ actions that are all trying to do something with
`my_ball` simultaneously: `move_left`, `move_right`, and our original code.

Thus, the language would need some syntax that says "wait until these conditions
are true, and then do the next steps." That's essentially identical to the
action syntax, so we would essentially need to be able to have anonymous actions
inside of the Action Statements Block.

In this model, the compiler can trace a directed graph through action triggers
to determine which are actually synchronous and execute them synchronously on
the computer. Full Async also gets us very powerful concurrency in the language
as an inherent construct of the language itself. It allows the compiler to
determine what should be executed in parallel and what should be executed
synchronously, instead of forcing the developer to figure that out.

One of the downsides of this model is that the programmer has to _know_ that a
trigger will happen when they move a dimension point, and also know what the
"return condition" is of that action (like, "I see a dimension point is created
in `position<return_value>` and so I will move that into my own position"). This
means that adding simultaneous actions into an existing program could trigger
unexpected behavior that the programmer now has to "hunt" through their program
to solve.

##### Concurrently Execute and Return

In this model, programmers don't have to understand what the triggers they are
calling are modifying or even that they are running. The program pauses, the
simultaneously-executed triggers run, and then the program continues. In our
above program, `move_left` and `move_right` would happen simultaneously, and
then (assuming we somehow resolved the paradox) the new `my_ball` would be
created and moved into `new_spot`.

This option most matches the _intent_ that programmers have when they write
lines of code in sequence. It allows for the addition of new triggers on the
same conditions without disrupting the behavior of the program.

It is a less-powerful concurrency mechanism than Full Async, as concurrency only
happens when explicitly requested by the programmer, and so programmers now have
to think about what should or shouldn't be running concurrently (one of the
harder programming problems to get right).

We still have to handle paradoxes in this model, although the scope of analysis
we have to do in the compiler is smaller. It's not "everything in the whole
program is running in parallel," it's "these actions are running in parallel, do
they do something in conflict?" Of course, if you start those actions at the
start of your program and then all of your logic is inside of them, that can get
pretty complex!

This also still leaves us with the problem that some other part of the program
could introduce a paradox that we don't expect and break our code.

##### Yield at Conflicts

In this model, the compiler draws a dependency graph about how all actions can
affect all points. It then forces a sequencing of actions _only_ when there is a
dependency. It _fully_ pauses when there is a paradox and waits for something
else to resolve the paradox, and ideally the compiler informs the programmer
about unresolved paradoxes as a compiler error.

In our example above, what would happen is that `move_left`, `move_right`, and
the code to create a new ball would all cause a paradox together. However, if
something somehow resolved the paradox between `move_left` and `move_right`,
then the compiler would know to trigger the `new_spot` code right after the
action that resolved the paradox.

This option is pretty cool in that, to the programmer, it looks like all actions
complete immediately, and all they have to do is access the newly-modified
position in space (whatever the trigger returned or modified). However, in the
backend, the compiler automatically runs everything in parallel when
appropriate. This moves almost all decisions about parallelism to the compiler
and out of the hands of the programmer.

It does mean that parts of a program can execute in parallel in an unexpected
manner as you add more trigger conditions. It also means that parts of a program
that _were_ executing in parallel could suddenly stop executing in parallel when
you accidentally introduce some data dependency deep in the call stack.

### Resolving Paradoxes

There are a few potential models for resolving paradoxes, when we allow
simultaneity. Some are described above, but there are also other options that
are worth discussing, mostly from other programming languages that have tried to
solve this problem. Some of these solutions end up being conceptually similar or
identical to the potential solutions above, but they are still worth analyzing.

#### Forbid Paradoxes

The compiler detects if you will produce a paradox and throws an error. This
means that if any part of the program introduces a paradox against any other
part of the program, it will be detected immediately and forbidden.

#### Explicit Ordering Only For Conflict Resolution

One option is that we only require the programmer to express ordering when a
conflict is detected by the compiler. In our example above, the compiler would
detect that `move_left` and `move_right` conflict, and force the programmer to
express an explicit order _only_ because they conflict.

This still leads to situations where programmers unexpectedly have to write code
to resolve conflicts---conflicts they may not understand that are caused deep in
some action call stack far away from the code they are writing. Some library you
depend on adds some trigger that suddenly causes parallelism, and now you're
stuck making manual human decisions at every single place you call that library.

#### Explicit Conflict Resolution Instructions

There is a type of logic used in some languages called "Join Calculus" to solve
these problems. In Join Calculus, you define a "Chord"---a pattern of messages
that must all be present before the code runs. For example:

```csharp
// Standard handlers
when (move_left()) { ... }
when (move_right()) { ... }

// A Chord: This code ONLY runs if we receive 'move_left' AND 'move_right' at the same time.
when (move_left() & move_right()) {
   explode_ball();
}
```

In essence, you define what to do with the _specific conflict_, not the ordering
of the full actions. This does require the programmer to predict all conflicts,
but if they encounter a conflict, it allows them to say "here's what should
happen in that situation."

The problem is: what if the conflict is in some part of the system far away from
the part that you maintain? It can be very hard to reason through how to resolve
conflicts with something you don't understand. Also, what if you're maintaining
a library, and you are introducing potential conflicts into the code of your
users without you knowing it? How do you decide what to do about those
conflicts?

#### Positions Become "Lattices"

In a language called `Bloom^L` and in the concept of CRDTs (Conflict-free
Replicated Data Types) variables are not individual points in space, but instead
they are "lattices." Essentially, a lattice is the result of running a bunch of
"merge" operations on instructions the lattice received over time. One machine
says `position<x> is green` and another says `position<x> is blue` and those get
merged and it has both colors. When there are conflicts, the system knows the
order in which it received the conflicting instructions and it resolves them in
that order (with instructions for what to do if the lattice's value becomes
"deleted" before other things try to change it). When there are real conflicts
that happen at the same instant, the program has an arbitrary mechanism for
determining which goes first. In general, a lattice has some strategy for
merging different operations that it executes.

This all sounds nice until you realize that it doesn't actually resolve the
paradox issue that we have, in a system that runs in zero time. In `Bloom^L`
what happens with _real_ paradoxes is that the value of the position becomes an
error---in other words, any part of the program that attempts to access that
position afterward throws an error and crashes the program.

Bloom does have an interesting approach to dealing with the other aspects of
parallelism, however. Bloom programs are sets of unordered logic rules. To make
them run, the compiler analyzes the dependencies:

1. **Monotonic Logic (Safe)**: Rules that just add information (e.g., "If ball
   is at A, mark A as occupied"). These can run in any order, or simultaneously,
   and the result is always the same.
2. **Non-Monotonic Logic (Unsafe)**: Rules that depend on the absence of
   something or change a value (e.g., "If ball is NOT at B...").

The compiler then breaks the program into Strata (layers):

- **Stratum 1**: Run all the safe, additive logic until it settles (reaches a
  fixed point).
- **Stratum 2**: Now that we are sure about what is true in Stratum 1, we can
  run the "unsafe" logic that depends on it.

In Define we would have to do those steps over and over as the compiler moves
through a program, as later safe code could depend on the behavior of earlier
unsafe code. Bloom solves that problem by introducing the concept of sequence,
where the programmer must explicitly indicate that some code happens after other
code, but only when there are logical conflicts that _require_ you to make that
decision. That once again gets us back into the problem of explicit conflict
resolution.

#### Optimistic Concurrency (Software Transactional Memory)

Languages like Haskell do something called Optimistic Concurrency with Software
Transactional Memory. It works by treating actions like database transactions.
Here's how it does that:

1.  **The Recording Phase**: When an action (transaction) starts, it creates a
    private log.
    - Every time it reads a variable (like `my_ball` position), it records the
      version it saw.
    - Every time it writes to a variable, it writes to the private log, not the
      real universe.

2.  **The Validation Phase (Commit)**: When the action finishes, the STM runtime
    pauses for a microsecond to check the "Real Universe."
    - It asks: "Has any variable I read changed since I started?"

3.  **The Resolution**:
    - **Success**: If nothing changed, the private log is flushed to the real
      universe instantaneously.

    - **Conflict**: If `move_left` finished 1 nanosecond ago and moved the ball,
      the `move_right` transaction realizes its snapshot is stale. It
      automatically abandons everything.

4.  **Retries**: When a transaction fails, the runtime automatically restarts
    it.

This is super cool, but it doesn't solve our problems for Define, because it
means that when we statically analyze the program, we can't know whether
`my_ball` will be in the `left` position or the `right` position, which breaks
all of our guarantees and safety.

#### Fail Paradoxes

One option is to simply deny _both_ paradox actions from happening. In our
example above, `move_left` and `move_right` would both try to move `my_ball` to
a different position, and it would simply _fail_. That is, `my_ball` would stay
right where it is, and then the code that attempts to create a new dimension
point in `my_ball` would fail, as would any code later in `move_left` and
`move_right` that depended on something being in `left` or `right`.

I suspect that this is what happens in the physical universe, but it is nearly
impossible to observe because it is nearly impossible to make two things happen
at "the exact same time."

For us, this is _very_ similar to "forbid paradoxes," since the compiler will
know that the dimension point didn't move and then some later code will fail. It
will be a much more confusing error message, though, because it won't tell you
when the paradox occurred.

## Solution

We choose Simultaneous Triggers with Full Async, we Forbid Paradoxes, and we
introduce a new syntax for waiting for async actions to return.

### Simultaneous Triggers

All actions triggered by the state of a set of dimension points conceptually
trigger and complete their actions instantaneously at the same time. The
compiler may choose to run them in sequence or with any form of
concurrency/parallelism it deems most efficient and effective, when it delivers
the actual implementation, but conceptually it treats them as instantaneously
simultaneous.

### Full Async

Statements in an Action Statements Block execute in sequence, instantaneously
one after the other. They do not wait for actions they have triggered to
complete, they just keep running. The compiler may choose to re-order such
statements or combine them into single actions in the computer as long as that
does not change the semantics of the program.

### Forbid Paradoxes

The compiler detects and forbids any potential paradox. It implements this in a
fashion that does not require whole-program analysis that grows unbounded in
complexity as the size of a program grows. Implementing this modularity may mean
that the compiler rejects programs that are in fact valid because it _looks_
like they will cause a paradox. We will of course strive to accept all valid
programs when possible.

The compiler only has to inform the developer of two conflicting actions or
statements involved in the paradox. In other words, if there are 3+ actions all
trying to modify the same position, the compiler might only inform the developer
of 2 of them, then the developer fixes one of them, runs the compiler again, and
discovers another conflict. The compiler _may_ inform the developer about more
than 2 conflicts, but it does not _have_ to.

The compiler assumes that all code that would execute after the paradox is
invalid and does only minimal validation on it (for example, ensuring that
position names are valid).

My current belief for how this will be implemented is that the compiler will
track all shared positions that actions interact with, and it will expose what
type of action they perform on the position. This will create a "stack" of
modular constraints that we can then solve when we encounter concurrency.
However, this proposal is not mandating an implementation, just a set of
requirements.

### Waiting for Actions

In order to write programs as a series of instructions in order with our Full
Async model, we need a syntax that expresses two things at once: (1) I triggered
an action that I expect to finish (2) I am waiting for that action to finish.

This also solves one of the basic problems of Define: "it's not clear that I
triggered an action, and if it stops triggering I will not be informed by the
compiler."

The syntax looks like:

```
wait until {
    # Trigger Conditions Block
}
```

This syntax may only appear inside of an Action Statements Block.

The Trigger Conditions Block has the same syntax as an action's Trigger
Conditions Block. Until further notice, the lexer, parser, and all other parts
of the compiler may treat them identically.

Conceptually, what this does is two things:

1. It turns all of the statements _after_ this block into a new, anonymous
   action that triggers based on the conditions in the Trigger Conditions Block.
   Thus, it triggers exactly the same way any action does.
2. It expresses the intention that the "wait until" conditions _must_ occur.

The "must occur" aspect is enforced by the compiler---if it can prove that a
`wait until` block _cannot ever_ trigger, it will throw an error. There may be
situations where the compiler is uncertain if the block will trigger, in which
case it can provide that information diagnostically (as an option) to the
programmer, but it will not throw a hard error.

The compiler may choose to convert `wait until` statements into synchronous
execution of actions in order, and very often will, in order to create
idiomatic, performant code in various languages.

## A Real Program

The program in the Problems section throws an error about a paradox. It is only
required to inform the developer about two of the three conflicts involved
(between `move_left`, `move_right`, and the creation of a new dimension point in
`my_ball`) but it may inform the developer of all three.

A valid program would look like this:

```
define the potential action<mv:example.com:example:/create_ball> {
    define the position<run>.
    define the position<ball>.

    it happens when {
        the position<run> has a dimension point.
    } and it does {
        create a dimension point in position<ball>.
    }
}

define the position<ball_creator> {
    it may only contain dimension points where {
        it has the action<mv:example.com:example:/create_ball>.
    }
}
create a dimension point in position<ball_creator>.
create a dimension point in position<ball_creator>:: action<mv:example.com:example:/create_ball>::position<run>.

wait until {
    the position<ball_creator>:: action<mv:example.com:example:/create_ball>::position<ball> has a dimension point.
}

define the position<new_spot>.
move the dimension point in position<ball_creator>:: action<mv:example.com:example:/create_ball>::position<ball> to position<new_spot>.
```

That triggers an action that creates a ball, "waits" for the ball to be created,
and then moves it into a new position. (As a note, this is also how the
traditional programming language concept of "return values" work in Define.)

Any of those actions could also have been a shared position, instead of being a
position defined by the action. It was just simplest for this example to show
positions defined by the action.

## Why This is the Right Solution

### Why Simultaneous Triggers with Full Async?

One of the most significant arguments for simultaneous triggers is that this is
how almost all real universes (such as the physical universe) are most likely
operating. One could imagine a universe with different rules (almost any of the
rules above) but the material universe _seems_ to be full async. It's hard to
imagine that the material universe could be fully sequencing the movement of
every particle; it seems like it would show up very anomalously in physics if
this were happening. It seems that the only way it's really possible to set up
machines in the physical universe is "when this thing happens, do this other
thing," and then a long series of "statements" like that.

However, it turns out there is one slight difference between real universes and
what we expect for computer programs. In a real universe, you define a set of
triggers and then whatever happens, well, that's what happens. However, in a
computer program, you're not just defining a universe---you're defining a
predictable universe where you have certain expectations that things _will_
happen, and you want the compiler to tell you if your expectations are false.

In a real universe, you can choose Full Async and Fail Paradoxes, and then
that's _just what happens_. The rest of the "program" doesn't run, or fails in
some spectacular way. Oops, you made a mistake, but you didn't know until
"runtime." In a programming language, we want the compiler to tell us if that's
going to happen.

So really, this exposes to us that _programming_ isn't just about designing a
universe---it's also about setting expectations about what is going to happen
and then being informed if that's _not_ what is actually going to happen.

### Why Forbid Paradoxes?

We need to guarantee safety and correctness of the program. After a paradox
occurs, it's impossible to guarantee that. That said, we could possibly enable
some advanced techniques like chords or lattices in the future if we want to
allow optimized resolution of certain types of conflicts. I'm not sure it's
correct for us to introduce that _in the language_, though---it might just be
some library.

For now, choosing Forbid Paradoxes gives us maximum flexibility for forward
compatibility, because it allows us to defer any decision about what to do with
paradoxes into the future.

### Alternative Implementations

Essentially: why have the "wait until" syntax instead of just continuously
re-writing `it happens when { } and it does { }`? Well, when I was experimenting
with the language, that's exactly what I did. The syntax is fine, except that:

1. It doesn't tell you when the trigger fails to fire. It doesn't express an
   expectation.
2. It forces extreme levels of nesting in the program. Yes, verbosity is fine,
   so maybe that's not our most important issue, but it did make programs very
   hard to read.

Possibly the syntax could be `wait until { } and then { }` instead, although
that gets us back into nesting. It would allow us to have multiple "sub actions"
occur within an action, anonymously, though (because you could have two
`wait until` statements in the same scope). It may be necessary to switch to
this syntax in order to describe some other languages' constructs, but we will
see.

## Forward Compatibility

Forbidding paradoxes has an obvious forward compatibility value, which is that
if you _can't_ do something, we are open to changing our minds about it in the
future, since the problem won't exist in any valid Define program.

Theoretically, one would imagine there's a forward compatibility problem caused
by libraries being able to introduce paradoxes. However, if you think it
through, our rules forbidding global name circular dependencies actually prevent
this from happening. A library can't depend on a position defined in its
consumer. Thus, all paradoxes can be known _within_ a universe.

Deciding now that Define is Full Async is very important, as that would be
difficult to change if we had started off being fully synchronous (though a lot
of it would be possible---you would just have to detect action completion
conditions and insert `wait until` statements). However, this decision is
somewhat difficult to change our mind about. We can detect _some_ patterns and
know that they represent sync execution, but not all patterns will be detectable
and convertable to a different syntax.

## Refactoring Existing Systems

I believe it is possible to convert both the sync and async behavior of every
language into this syntax. The one exception is that you can't encode race
condition bugs because the compiler will detect them as paradoxes. The one
danger beyond that is if our paradox detection is over-eager, it could prevent
some valid programs in other languages from being translated into Define. We
will cross that bridge when we get there. (That is, once we actually have a
paradox detection algorithm, we can tweak and improve it over time.)
