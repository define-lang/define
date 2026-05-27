# Define Language Proposal 22: Atomic Qualities

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** January 19, 2026
- **Date Finalized:**

## Problems

Once we start to think about defining qualities, we realize that those qualities
will define other names. For example, imagine this syntax:

```
define the quality<mv:example.com:example:/color> {
    define the position<hue>.
}

define the position<ball> {
    it may only contain particles where {
        it has the quality<mv:example.com:example:/color>.
    }
}
create a particle in position<ball>.

# We can now reference position<ball>::position<hue>.
```

This immediately gets us into a problem: if multiple qualities define a thing
with the same name (a position or action) and you apply those qualities all to
the same particle, what happens?

Conceptually, if two qualities want to both talk about the same position in
space, what happens?

Here are a few examples where this could happen:

```
define the quality<mv:example.com:example:/ball> {
    define the position<color> {
        it may only contain particles where {
            it has the quality<standard:/color>.
        }
    }
}
define the quality<mv:example.com:example:/crayon> {
    define the position<color> {
        it may only contain particles where {
            it has the quality<standard:/color>.
        }
    }
}
```

```
define the quality<mv:example.com:bank:/bank_account> {
    define the position<balance> {
        it may only contain particles where {
            it has the quality<mv:example.com:bank:/money_value>.
        }
    }
}
define the quality<mv:example.com:park:/skateboarder> {
    define the position<balance> {
        it may only contain particles where {
            it has the quality<mv:example.com:human:/sense_of_balance>.
        }
    }
}
```

There are a few options for how to resolve such conflicts.

#### Forbid Conflicts

One of the simplest options is to simply say "you may never have conflicts," and
the compiler just throws an error. The downside of this is that any time a
quality defines a new position, it potentially breaks every existing program
that uses that quality. (The new position _might_ have the same name as another
position that is on the same particle.) This breakage would require complex
human intervention to fix.

#### Rules for What Wins

For example, you could say that the first quality that was assigned "wins" and
all later qualities simply don't get a position there.

This leads to numerous complexities and logical conflicts. For example, Quality
A expects Position X to be a ball. Quality B expects Position X to be a dog. The
rest of the program thinks "if a particle has Quality B, then Position X is a
dog." But Quality A was applied first, so Position X is a ball. All the
guarantees of the program fail.

Also, this sort of "silently ignore the programmer's instructions" behavior is
extremely confusing for programmers.

#### Merge Definitions

In this option, we define an algorithm for how definitions combine when multiple
qualities are assigned to the same particle. It must be predictable,
deterministic, and forward compatible for every way we could evolve the language
in the future.

The danger here is that sometimes names are synonyms (two names that mean the
same thing) but other times they are homonyms (two words that are spelled the
same but mean completely different things). Examples:

- **Synonyms**: Two qualities both define `color`. They likely mean the same
  thing. Merging might work here.
- **Homonyms**: A Bank Account has a `balance` (money). A Skateboarder has a
  `balance` (equilibrium). These share a name (a string of characters), but they
  are fundamentally different concepts. Merging them is illogical.

There is no way for the compiler to know whether two names are synonyms or
homonyms. Thus, there is no way to automatically merge definitions.

As an interesting note, this is one of the first times we run into a fundamental
problem with how we have designed Define. In a real universe made of space, it
would be apparent whether two positions were actually the same position.
However, since we have to use _names_ to talk about the _concept_ of positions,
two different names that _intend_ different positions can accidentally become
the _same_ position.

Real universes most likely use this "merge" solution, because they _know_
whether two points in space are the same point or not.

#### Create Views of Particles

In this solution, we always have to say what single quality we are considering a
particle to have when we talk about it. For example, if we have a `position<x>`
that is both a `bank_account` and a `skateboarder`, whenever we reference
`position<x>`, we have to say whether we are referencing that position as a
`bank_account` or a `skateboarder`.

C# allows something like this: it allows multiple interfaces to define the same
function name, and then when you want to be explicit about which function you're
calling, you cast the object to that interface:

```csharp
interface IReadable {
    void Read();
}

interface IDisplayable {
    void Read();
}

class Document : IReadable, IDisplayable {
    void IReadable.Read() {
        // Read as readable document
    }

    void IDisplayable.Read() {
        // Read as displayable document
    }
}

// Usage:
Document doc = new Document();
((IReadable)doc).Read();  // Explicitly call IReadable.Read()
((IDisplayable)doc).Read();  // Explicitly call IDisplayable.Read()
```

In other words, what positions are _there_ depends on how you're "looking" at
the particle. That's great when different parts of the program each know the
particle has one particular quality. What this doesn't resolve inherently is:
what if you're looking at a particle that you know has both qualities and that
you _need_ to have both qualities? It also starts to get awkward---why even
allow multiple qualities on a particle if you're just going to have to specify
which one you're looking at, all the time, in order to deterministically avoid
name conflicts?

#### Different Choices Every Time

You could require the programmer to explicitly specify how to resolve every
conflict. You could choose to do this in the quality definition itself (meaning
the programmer has to anticipate any possible conflict they could be
introducing) or you could do it on the definitions of positions (so every
position definition has to be updated when a conflict occurs).

Both of those options create unmaintainable programs:

- **Predicting it in the Quality Definition**: It's impossible to predict every
  conflict in advance, or understand what to do with conflicts you haven't even
  seen yet.
- **Updating Every Definition**: Forcing every position to update its definition
  is also untenable. It forces every programmer who _depends_ on your code to
  have to make human decisions about what will happen when you break them. This
  breaks Define's forward compatibility guarantees.

#### Atomic Qualities

You only allow every quality to have exactly one named definition it creates.
Thus, the programmer always knows that they are creating a conflict between one
thing that defines `position<x>` and another thing that defines `position<x>`.
Unexpected conflicts only occur if a programmer renames the thing defined inside
of the quality.

This does lock a developer into never renaming things, which can create some
pretty awkward-looking programs when a developer realizes they used the wrong
name for something.

It also makes it harder to reason about programs and prevents some necessary
patterns from being written. For example, let's say you want to have a particle
that represents a bank account. In this model, you give it one quality that says
"it has a balance" and another quality that says "it has an action called
deposit" and another one that says "it has an action called withdraw." But the
constraint on `withdraw` has to be "the requested amount for withdrawal is less
than or equal to the balance." So the `withdraw` action _has_ to know about the
balance.

You could theoretically solve this by saying: "balance must be a position
defined by the `withdraw` action so you can 'pass in' the balance to the
`withdraw` function." That would then put the burden on the programmer to be
sure they passed in the `balance` correctly every time to the `withdraw`
function. (This creates a pure functional universe, more or less.)

Another potential solution is to create a dependency tree: You allow the
`withdraw` quality to say that it requires the `balance` quality. This has a ton
of nice properties. It allows you to re-use every component of a quality instead
of just re-using the atomic quality. It makes it clear what parts of the code
actually depend on other parts of the code. However, it still can lead to
conflicts. For example, if I later give the same particle a `ride_skateboard`
action, it would depend on a `balance` that has a totally different meaning.

One could solve _that_ by requiring that all actions and positions defined as
part of qualities have names in the global name scope instead of local names
inside of qualities. A program written with this system might look like:

```
define the potential position<mv:example.com:bank:/account/balance> {
    it may only contain particles where {
        it has the quality<standard:/number/decimal>.
        it has the quality<standard:/number/constraints/non_negative>.
    }
}

define the potential action<mv:example.com:bank:/account/withdraw> {
    it requires position<mv:example.com:bank:/account/balance>.

    define the position<amount> {
        it may only contain particles where {
            it has the quality<standard:/number/decimal>.
            it has the quality<standard:/number/constraints/non_negative>.
        }
    }

    it happens when {
        the position<amount> is not empty.
    } and it does {
        set the value in position<mv:example.com:bank:/account/balance> to position<mv:example.com:bank:/account/balance> - position<amount>.
    }
}

define the potential action<mv:example.com:bank:/account/test_withdraw> {
    it triggers when {
        this quality is assigned.
    } and it does {
        define the position<my_account> {
            it may only contain particles where {
                it has the action<mv:example.com:bank:/account/withdraw>.
            }
        }
        create a particle in position<my_account> {
            with the required qualities.
        }
        create a particle in position<my_account>::trigger<mv:example.com:bank:/account/withdraw>::position<amount> {
            with the required qualities.
            set the value to 100.
        }
    }
}
```

All of those top-level definitions would have to be in different files.

And then the compiler can run `test_withdraw` by creating a particle and giving
it `action<mv:example.com:bank:/account/test_withdraw>`. In this model, the
whole concept of "a quality" as an entity mostly disappears, except potentially
as a convenient grouping of functionality.

One downside is that many more names become very long (global names). Also,
these names get spread all over the program (though our plans for deterministic
automated refactoring should make it pretty easy to rename or move things).

It does allow for massive flexibility and composability in a way that no other
language allows (to my knowledge). The only similar system is the Entity
Component System used in game engines or simulation systems (Unity, Unreal
Engine, Bevy, or the simulation language Ecsact).

#### Only Allow Explicit Composition

We could change the syntax of define such that every particle may only be
assigned a single quality. Then if you want to assign multiple qualities to the
same particle, you have to create a new quality that's "composed" of other
qualities. This is how most programming languages work---they only allow you to
assign a single "type" to a variable, and you have to create a new type if you
want to compose multiple types together.

In other words, instead of having a ball that is `red` and `heavy`, you have a
ball with the single quality `red_heavy`.

This solves most problems by forcing the programmer to create an extremely rigid
structure that decides exactly how all conflicts will be resolved. The
`red_heavy` quality has to decide exactly how `red` and `heavy` combine.

It does get fairly awkward when you have three, four, or more different
qualities that you potentially want to combine on many different particles. You
have to start creating a _lot_ of composed qualities to solve that problem. It
also makes removing qualities more awkward. The compiler has to understand that
a `red_heavy` ball _is_ both `red` and `heavy`, otherwise all the parts of the
program that expect only a `heavy` ball will fail.

Although we are used to this system, as programmers, in reality it is
unintuitive. I simply want to say that a ball is red and it's heavy, and an
elephant is gray and heavy. I don't want to say a ball is RedHeavy or an
elephant is GrayHeavy. Yes, programming languages have come up with numerous
methods to solve these problems throughout the years, but fundamentally the
_idea_ is unintuitive that you must combine all qualities into a single quality.

#### Require Global Names

In this option, there is never a `balance` position. Instead, the name of the
position is always prefixed with the name of the quality. So when you access it
on a position, it looks like:
`position<x>::quality<mv:example.com:bank:/account>::position<balance>`. This
prevents name conflicts entirely, as long as you make it so that the name prefix
is guaranteed to be globally unique (which our global naming system does).

This feels extremely verbose even for Define, but it simply stops conflicts from
happening on names.

It has the downside of spreading the name of the quality all over the
program---at every point you reference any position on the object, instead of
just where it is assigned. It also means that every time you rename the quality
or move its file location, you have to fix every position reference for every
particle the quality is assigned to. Theoretically, Define's automated
refactoring systems should make that easy, though.

## Solution

I have chosen a particular form of Atomic Qualities combined with Global Names
as the solution for Define. This solution _inherently_ implements "Merge
Definitions."

This requires us to make several changes to the language.

### Potential Positions and Potential Actions

We introduce the concept of _potential_ positions and actions that don't exist
until they are "applied" to a particle. This concept always existed, but it
didn't require its own syntax---it was implied by a position being defined
inside of a quality definition. Now we must be more explicit.

In the global name scope, one may use the syntax:
`define the potential position<name>` to create a _potential_ position that only
actually exists once it is assigned to a particle. It allows all the same syntax
as a real position.

Similarly, one may use the syntax: `define the potential action<name>`. This is
the only way to define a named action, but we use the word "potential" to make
it clear that the action does not _exist_ until it is assigned to a particle.
All other aspects of action-definition syntax remain the same. They may define
positions of their own, just as before.

Potential positions and potential actions may only be defined in the global name
scope and (as with everything defined in the global name scope) must have global
names.

### Qualities Do Not Exist

At this time, the name type `quality` is removed from the language. Instead,
when we talk about "qualities" we mean potential positions or potential actions
that can be assigned to a particle.

### Assigning Potential Positions or Potential Actions

Instead of writing `assign the quality<name>` one must write
`assign the position<name>` or `assign the action<name>`. This will cause the
particle to have that position or action on it. The name remains the global
name. Thus if you assign `position<mv:example.com:example:/foo>` to
`position<ball>`, you can reference it as
`position<ball>::position<mv:example.com:example:/foo>`.

### Guaranteeing Qualities on Positions

In position definitions, instead of `it has the quality<name>`, one must write
`it has the action<name>` or `it has the position<name>`. This will require that
the particle in that position have the specific quality listed.

### Dependencies

Potential positions and actions may express that they auto-assign other
positions and/or actions to a particle when they are assigned to it, using this
syntax:

`it also assigns the type<name>.`

Where `type` is `position` or `action`. We call this a "quality implication
statement." In shorthand, we refer to this as "implying" a quality.

Logically, that syntax says that the existence of this quality implies the
existence of another quality on the same particle. Qualities can transitively
imply other qualities, so this creates a "dependency tree" of qualities that are
assigned to a particle.

The actual implementation is that when assigning qualities to a particle, their
implied qualities are automatically assigned to them _first_. In other words, if
the `withdraw_money` action implies a `balance` position, then the `balance`
position is assigned to the particle _first_, and the `withdraw_money` action is
assigned second.

To understand how this works, imagine an action that withdraws money from a bank
account:

```
define the potential action<mv:example.com:bank:/account/withdraw> {
    it also assigns the position<mv:example.com:bank:/account/balance>.

    define the position<amount> {
        it may only contain particles where {
            # Imaginary syntax for values and constraints on values.
            it has a value that is a decimal.
            it has the constraint</positive>.
        }
    }

    it happens when {
        # Imaginary syntax for a trigger condition.
        the position<amount> has a particle.
    } and it does {
        # Imaginary syntax for setting a value.
        set the value in position<mv:example.com:bank:/account/balance> to position<mv:example.com:bank:/account/balance> minus position<amount>.
    }
}
```

As we see, the action may then refer to
`position<mv:example.com:bank:/account/balance>` with no prefix, because it is
part of the same particle as `action<mv:example.com:bank:/account/withdraw>`.
Any other action on that particle may also refer to
`position<mv:example.com:bank:/account/balance>` and it will be the exact same
position. In other words, you can have both a `withdraw` and a `deposit` action
that both affect the same `balance` position. In this way, multiple actions can
coordinate with each other without "knowing about" each other.

### Duplicate Assignments

While manually _writing_ duplicate assignments (multiple `assign the` or
`it also assigns the` statements with the same exact arguments in the same local
name scope) should be forbidden by the compiler, quality implication statements
across different definitions may attempt to assign the same quality more than
once to the same particle. If this happens, only the first assignment actually
occurs, and all later assignments are ignored by the compiler.

For example, imagine this program:

```
define the potential action<mv:example.com:bank:/account/withdraw> {
    it also assigns the position<mv:example.com:bank:/account/balance>.
}
define the potential action<mv:example.com:bank:/account/deposit> {
    it also assigns the position<mv:example.com:bank:/account/balance>.
}

define the position<account> {
    it may only contain particles where {
        it has the action<mv:example.com:bank:/account/withdraw>.
        it has the action<mv:example.com:bank:/account/deposit>.
    }
}
create a particle in position<account>.
```

That program only assigns the `position<mv:example.com:bank:/account/balance>`
once.

In other words, the `it also assigns the` syntax really means: assign this
quality to the particle _if it does not already have this quality_.

### Forbidding Circular Dependencies

Circular dependencies created by quality implication statements are forbidden.
The compiler will throw an error indicating that this is forbidden.

### No Dead Dependencies

If a definition contains a quality implication statement, the definition must
actually somehow reference the quality that was implied. Otherwise the compiler
will throw an error indicating that the quality implication statement is
unnecessary.

## A Real Program

See the example in "Atomic Qualities" for the closest approximation of what a
real program would look like. There are also examples above in the Solution
section.

## Why This is the Right Solution

Most potential solutions are clearly dismissed in their problem descriptions.
The only real options were:

1. Atomic Qualities
2. Only Allow Explicit Composition
3. Require Global Names

Originally, I went with Require Global Names, but it was extremely unsatisfying.
It spread global names all throughout the program just to avoid name conflicts.
It forced the programmer to do manual composition of different concepts if they
_wanted_ composition, because it was now impossible to say "these two different
`color` positions both really mean _color_."

Explicit Composition, in addition to the downsides mentioned in its description,
just doesn't intuitively match how universes actually _work_. That was my first
hesitation. The next is that once you have composition, you either have to (a)
leave it all up to the programmer (so they are always writing extra "wrapper"
functions around other functions just to group two concepts together) or (b)
come up with your own very involved composition system. I love composition
systems and I've used them a lot, but it becomes very possible to "draw yourself
into a corner" with significant design mistakes if you don't _very_ carefully
design your program to avoid them. In other words, they don't obviously lend
themselves to good design. They _enable_ good design, but they don't require it.
Plus, down the line you still end up with a lot of confusing naming conflicts.

Our solution not only solves the name conflict problem, it solves numerous other
problems created by traditional object-oriented systems. It almost entirely
eliminates the "god object" antipattern where multiple different pieces of
unrelated functionality are grouped together into the same class. It almost
_enforces_ the "single responsibility principle" that is the hallmark of good
object-oriented design. One could still write actions that are too complex, but
creating a _structure_ that is too complex becomes (a) harder and (b) much more
obvious, because you can see it in the dependency tree.

Atomic Qualities also allow us to keep most of the positive properties of "Merge
Definitions" by allowing multiple different actions to refer to the same point
in space, as long as it really is _exactly_ the same point in space.

### Alternative Syntaxes

Originally quality implications were called "quality requirements" and the
syntax was `this particle must have the` instead of `it also assigns the`. I
chose that because it looked similar to the `it has the` syntax for position
constraints, but that was a significant mistake. The AI agent that was helping
me write the compiler became extremely confused about how "quality requirements"
and "position constraints" were different, especially because they both
essentially _required_ something.

One of the tricks is getting an AI or a programmer to understand that
implications assign qualities to _this_ particle (the same one we are assigning
the current quality to) and Position Constraint Blocks create _child_ positions.
So I wanted a program syntax and English terminology that makes that clear.

The sense that I wanted to convey was: "assigning this quality to this particle
means that we will first auto-assign another quality to this particle," and that
_logically_ what was happening was implication: the existence of quality A
implies the existence of quality B. Here are various other syntaxes that I
considered and discarded:

- `require position</foo>`: Unclear what it's doing, too brief (forward
  compatibility issue).
- `this also assigns the`: using "this" was inconsistent with everywhere else
  that we use `it`.
- `implies position</foo>` or `it implies position</foo>`: Good if you want to
  think about the program like propositional logic, but I don't think that's how
  most programmers think about their programs. It seemed better to explain it in
  an active way.
- `assign position</foo>`: Assign it to what? That's confusing. I doubt AI
  agents or humans would be able to understand what's happening.

## Forward Compatibility

We have changed nothing about Define's forward compatibility guarantees via this
change. In fact, we have guaranteed them by eliminating name conflicts. Every
aspect of this proposal is deterministic, unambiguous, and surrenders completely
to static analysis.

## Refactoring Existing Systems

No real systems exist. However, we could go from the `assign the quality` syntax
to the current syntax by a process roughly like:

1. Analyze all actions to determine what positions they depend on.
2. Create a directory named after the quality, if it doesn't exist.
3. Factor out the positions into their own files. Because files can contain more
   than one global definition, and previous files would have contained only
   `quality` definitions, this action is guaranteed to be safe.
4. Refactor all references that assign or require qualities to require the
   relevant actions or positions instead.

Though complex, that is completely accomplishable thanks to the forward
compatibility guarantees we have enforced thus far.
