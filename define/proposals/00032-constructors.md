# Define Language Proposal 32: Constructors

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** January 26, 2026 (but rewritten entirely on July 28, 2026)
- **Date Finalized:**

## Problems

### 1: Guaranteeing Initial State of a Particle

In programs, you often want to guarantee that a variable is in a particular
state immediately after it is created, reliably. For example, you may want a
count to always start at `1`, or a countdown to always start at `60`. If you're
creating a shared piece of code, you don't want to rely on every user of that
code to set the initial state correctly; you want the variable to just come
"prepackaged" with the right initial state.

These requirements can get even more cmoplex, when you want to initialize the
state of an entire _form_ of particles. For example, if you have a locked queue,
you want to set the mutex to unlocked and the queue to be an empty array (or
perhaps a pre-allocated list of a certain size, for efficiency).

Object-oriented programming languages traditionally solve this with a concept
called "constructors," where you create a special function that is called every
time the object is created.

### 2: Multiple Constructors

Languages have to decide what to do when you want to be able to construct the
same object more than one way. Most languages decide there will be multiple
constructors all with the _same name_ but different arguments. However, then you
are limited only to differences in the set of arguments, and if you want more
logic on top of that, you have to write if/else statements inside of the
constructors. That logic cannot easily be seen as static preconditions or
analyzable facts by external callers, and even in languages that have
preconditions, you only get one set of those preconditions for any given set of
typed arguments.

Other languages solve it by requiring you to have only one constructor and
saying they can take optional arguments and then the programmer has to write out
the logic inside of the constructor for what happens when the optional arguments
are specified.

### 3: Tying Constructors to Data

What really logically matters in most objects is that a subset of their data
members get initialized in a particular way. In fact, usually most
initializations are entirely independent of each other---one member variable
doesn't care at all how another member variable is initialized.

Sometimes this initialization logic actually is shared everywhere the same sort
of variable is used in the whole program, but you have to write it out
everywhere. That's often not a major problem, because it just looks something
like `var = new Dictionary();` or something like that. But other times it's a
whole complex initialization function that you end up writing and calling
everywhere across the program.

In other words, it's really the _data_ that cares about its own initialization,
more than it being a property of an object, although some objects do have
special needs for how a variable is initialized or how two variables relate to
each other.

This may not seem obvious until you look at an object that is violating the
Single Responsibility Principle and realize that one of the best ways to figure
that it's violating the principles is seeing that there are sets of fields that
are interacted with by totally distinct sets of methods. In other words, two
different sets of data objects that have two different sets of behaviors,
combined into a single concept. What this makes you realize is that data and the
functions that work on it are the _real_ core concept of an object.

### 4: Constructors and Errors

In languages like Java and Python, there's a design _principle_ that you should
not throw exceptions during a constructor, but the language doesn't actually
enforce it. It's left up to the developer as to whether or not a constructor can
throw an error.

The principle exists first and foremost because the state of an object during
construction is unknown. You can't reliably call a destructor on it because the
compiler hasn't really _made_ the thing yet, officially. Some languages even
leak memory for objects the constructor has already created, if you throw an
exception during the constructor (because the traditional cleanup methods that
deallocate memory might not run, depending on how you chose to write your code).

This is super confusing for developers writing constructors and those consuming
them. Will it throw an error, or not? _Should_ it throw an error, or not? What
state is the object in when that error is thrown?

### 5: Constructors Doing Work

In most languages there's a design principle that constructors should not do
significant "work." While this is probably a good design principle in general (I
don't expect "construct a frisbee" to throw the frisbee or buy me four more
frisbees) it's also backed up in many languages by the fact that the object is
in a weird semi-initialized state during a constructor, and thus the
compiler/runtime of that language is also in a special state during a
constructor that makes some things harder to reason about. Perhaps the design
principle is okay, but the "weird compiler/runtime state" is not, because the
truth is that programmers are going to do what they think they need to do,
regardless of what you write down as "best practices."

## Solution

In Define, constructors are actions assigned to a position that trigger
automatically when a particle is created in that position. This ties
construction only to specific data points or sets of data points, instead of to
an abstract concept of an "object."

Constructors that want to set other fields on the particle can do so simply via
quality implications.

Because Define can reliably track the state of any position at any time, during
compilation, it will know what state that positions are in even if somehow we
abort in the middle of a constructor.

Because constructors are simply actions, the compiler doesn't have to go into
any special mode or state to implement them, nor does the program treat them
differently at runtime than it does any other action.

### Trigger Condition Syntax

We add a new trigger condition for an action:

`this particle is created.`

Any action with that trigger condition is referred to as a "constructor."

### Triggering Semantics

A constructor triggers immediately after a particle is created inside of the
position it is assigned to. This means that the particle has all qualities
assigned to it and all constraints are enforced.

<!-- TODO: This will probably have to change in some way in order to get things
set up for initial constraints, but we'll see when we get there. -->

Note that _moving_ a particle into the position does not trigger a constructor.
However, since the particle must have had that constructor as a constraint in
order to move into the position, we can be sure that it had the same initial
state upon its original creation.

Constructors execute synchronously when a particle is created. However, any
actions they trigger still execute asynchronously.

<!-- TODO: This will need to be reworked for data-dependency concurrency. -->

### Ordering

Constructors trigger in the order in which they were assigned to the position.
However, where the compiler can prove there is no dependency between
constructors, it may run them in parallel.

### Restrictions

There is currently no way to refer to the particle itself within a constructor
(the particle that the constructor was assigned to). This will be handled later,
when we need to set initial values on particles.

Constructors cannot be assigned to particles with a Quality Assignment
Statement. A constructor must have been a constraint on a position---otherwise,
we can't guarantee that particles actually were in a particular state during
their init by virtue of having the constructor assigned to them.

## A Real Program

This shows the simplest case: setting another position on the same particle.

```
define the potential position<mv:example.com:playground:/color>.
define the potential action<mv:example.com:playground:/construct> {
    it also assigns the position</color>.
    it happens when {
        this particle is created.
    } and it does {
        create a particle in position</color>.
    }
}
define the potential position<mv:example.com:playground:/ball> {
    it may only contain particles where {
        it has the action</construct>.
    }
}
```

## Why This is the Right Solution

One of our primary goals here is to simplify both a human's and the compiler's
ability to reason about the program. If we can ensure that positions are always
start in a certain state, it should become easier to enforce various guarantees
about a program. It also makes programs more consistent and easier to maintain,
as it allows the maintainers of global positions to entirely own how they set up
their children (and later, themselves).

### The Old Way: Position Init Blocks

Previously, we didn't have constructors, and instead had a special construct
called "Position Initialization Blocks." These had a special syntax inside of
position definitions that looked like:

```define
after it is assigned {
   # Do some stuff
}
```

They worked by a position being _assigned_ as a quality to a dimension point.

This had two very weird behaviors:

1. There was no way to say what should happen when you created a particle in a
   global position. That global position had to have a parent, and at some point
   you'd hit a parent where you couldn't specify its initialization behavior.
2. The way it "felt" logically was like empty space was taking an action, when
   conceptually a particle has to exist in order for a machine to execute. In
   fact, a position init block (as they were called, shorthand) could take an
   action without ever creating a particle in its own position.

It also added a huge amount of complexity to the compiler, where we had a whole
separate special case for compiling position init blocks and had to constantly
deal with the fact that there were two completely different "types" of actions.

Not to mention it was a bit confusing for developers---when do I make a position
init block, how much work should it do, should I just have a position init block
that triggers an action, should I always create a particle in the init block
(and why, if so), etc.

Finally, it made it very hard to conceive of an object, because there wasn't a
single "owner" that was setting up all of the children, unless you wanted to
have _another_ owner on top of that that had child positions, give those child
positions init blocks, and then have those init blocks (as, basically, empty
space) create either grandchildren or touch other implied positions...if this
sounds hard to understand, it's because it was.

I did it because I wanted some way to be sure a position would always contain a
particle. However, it prevented agency on the part of people defining global
positions, and it's totally easy for them to set up their child positions in
whatever way they want, using constructors.

### Multiple Constructors

This lets you assign multiple constructors to the same particle, and re-use
constructors across the program in a way that I believe is unique or unusual
amongst programming languages.

### More Than One Way to Do It

One of the dangers of having constructors is that it does create two ways to do
the same thing. You can init a position using a constructor or you can manually
create particles outside the block. Possibly the compiler (or linter) should
recommend that you choose the assignment block if it notices you always doing
manual init. However, it _feels_ intuitive to me that one ought to use a
constructor, and later down the road, visibility controls will enforce that you
do so.

### Why Not a Syntax Like "This Position?"

Once upon a time this proposal described a syntax for referencing the current
position via the string `this position`. However, it became very awkward to
implement in the compiler, because it was the only time we referenced a name
without the format `type<name>`. It created an inconsistency, and I also
realized that it would create a special case when you were just string-searching
for every place the position was referenced.

## Forward Compatibility

As far as I can tell, since we have specified the triggering order and these are
otherwise just actions, this should be just as safe as the rest of our action
syntax.

## Refactoring Existing Systems

I believe all constructors in object-oriented languages could be refactored into
this syntax, as every language's constructor system seems to just be "set a
bunch of fields or call a bunch of methods on this object right after (or
during) its creation." The _memory_ semantics of Define's constructors wouldn't
be the same (since there's no concept here of an "uninitialized object") but we
don't aim to preserve memory semantics.
