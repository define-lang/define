# Define Language Proposal 34: Destructors

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** January 29, 2026
- **Date Finalized:**

## Problems

Since [DLP 31](00031-destroying-particles.md) banned actions that trigger
arbitrarily on the absence of a particle, there is no way to guarantee that any
sort of "cleanup" code will run when you destroy a particle.

However, it's often necessary to guarantee that some action happens when a
particle is destroyed. For example, if you have a library that generates
temporary files, you need to be confident the file will be deleted when the
program ends. If you open a socket, you need to close it. If you have a buffer,
you need to flush it. And so forth.

Most programming languages handle this with "destructors," which are functions
that run right before an object is destroyed. They involve doing all the cleanup
for a whole class.

### Destruction Ordering

We have a particularly special problem. Imagine this program:

```
define the potential position<mv:example.com:example:/file_name> {
    it may only contain particles where {
        it has a value that is a string.
    }
}

define the potential action<mv:example.com:example:/file_handle/construct> {
    it also assigns the position</file_system>.

    it happens when {
        this particle is created.
    } and it does {
        create a particle in position</file_system>.
        # Some code that interacts with position</file_system>.
    }
}

define the potential position<mv:example.com:example:/file_handle> {
    it may only contain particles where {
        it has a value that is an integer.
        it has the action</file_handle/construct>.
    }
}

define the potential position<mv:example.com:example:/buffer> {
    # Imagine we have some syntax to define a byte buffer that we
    # need to write to the disk before the program terminates.
}

define the potential action<mv:example.com:example:/temp_file/create> {
    it also assigns the position</file_name>.
    it also assigns the position</file_handle>.

    define the position<run>.
    define the position<completed>.

    it happens when {
        the position<run> has a particle.
    } and it does {
        create a particle in position</file_name>.
        set the value in position</file_name> to "/tmp/foo". # Imaginary syntax
        create a particle in position</file_handle>.
        set the value in position</file_handle> to 1.
        create a particle in position<completed>.
    }
}

define the potential action<mv:example.com:example:/temp_file/construct> {
    it also assigns the position</buffer>.

    it happens when {
        this particle is created.
    } and it does {
        create a particle in position</buffer>.
    }
}

define the potential position<mv:example.com:example:/temp_file> {
    it may only contain particles where {
        it has the action</temp_file/construct>.
        it has the action</temp_file/create>.
    }
}

define the position<x> {
    it may only contain particles where {
        it has the position</temp_file>.
    }
}
create a particle in position<x>.
create a particle in position<x>::position</temp_file>.
create a particle in position<x>::action</temp_file/create>::position<run>.
destroy the particle in position<x>.
```

This results in a dependency tree that looks like this:

```
position<x>
|
-- position</temp_file>
   |
   -- position</buffer>
   -- action</temp_file/construct>
   -- position</file_name>
   -- position</file_handle>
   |  |
   |  -- position</file_system>
   |  -- action</file_handle/construct>
   -- action</temp_file/create>
      |
      -- position<run>
      -- position<completed>
```

According to [DLP 31](00031-destroying-particles.md), everything gets destroyed
simultaneously.

However, during destruction, we need to do the following:

1. The buffer needs the file_handle in order to flush its data to the disk.
2. We need to close the file_handle.
3. We need to delete the file on the disk using the file_name.

(Yes, it doesn't make sense to flush the file just to delete it, but pretend
that we need to do that for some reason in our program.)

Those three things have to happen in exactly that order, but we destroy trees of
particles like that simultaneously and instantaneously.

### Local Destructors

Sometimes in a program you need to specify some code that _must_ run at the end
of an action. Here's an example in Go:

```Go
type Door struct {
    isLocked bool
}

func (d *Door) goInBathroom() {
    d.isLocked = true
    defer func() { d.isLocked = false }()
    d.useTheBathroom()
}
```

Basically, we want to be sure that door unlocks even if we never come out of the
bathroom.

### Moving Particles

We can't just check what positions destructors are registered to, because
particles can move between positions. For example, imagine this program:

```
# Inside an Action Statements Block:
define the position<temp_file> {
    before destruction starts {
        # Delete the file.
    }
}
define the position<file>.
create a particle in position<temp_file>.
move the particle in position<temp_file> to position<file>.
```

When that Action Statements Block ends, only `file` has a particle in it, but
the destructor that was defined in `temp_file` needs to fire.

## Solution

### New Action Trigger Condition

We add a new trigger condition that actions can check:

`this particle is being destroyed`

We refer to this as a "destructor condition," and any action that checks this
condition as a "destructor."

Like constructors, destructors are ordinary actions with normal Action Statement
Blocks, and so they may _not_ refer to the particle that they are assigned to.

### When It Is Checked

Destructors start when the particle they are assigned to is about to be
destroyed. More technically, this means that the destructor condition is checked
immediately before destroying a particle that has a destructor on it.

This means, in the simplest case, that all destructors trigger simultaneously
during the destruction of a particle and its transitive children.

Destructors may also trigger other actions, which trigger normally.

Note that these semantics make constructors and destructors somewhat mirror each
other: constructors run _after_ a particle is _created_, and destructors run
_before_ a particle is _destroyed_. So there's always a particle taking an
action.

### Destructor Ordering

Destructors create a dependency order during destruction that imposes a partial
order upon particle destruction.

**Destructors always run before the particles they interact with are
destroyed.**

Note that use of interface positions on destructors should be rare, however. The
more common ordering mechanism for destructors will be through implied positions
(they will run before any implied position they interact with is destroyed,
which could include child positions of implied positions if the destructor moves
around or destroys parent particles). In other words, if a destructor implies
`position</buffer>` then `position</buffer>` cannot be destroyed until that
destructor completes or no longer needs to access `position</buffer>`. This is
how Define programs implement destruction-time required dependencies and solve
the problems of destruction ordering.

Interestingly, destructors do _not_ have to run before their parent particle is
destroyed. Conceptually, destructors run _simultaneously_ with the destruction
of their parent particle. As a result of this rule, this often means that
destructors on child positions can run simultaneously with destructors on parent
positions.

Even when a destructor depends on an implied position, destructors on the
children of that implied position may run simultaneously with the destructor on
the parent position, due to the rules above.

Exactly _how_ this ordering manifests in Define will be covered by a later
proposal, but the above are the logical rules for how it works for the sake of
verifying programs.

### Static Analysis Requirement

The compiler must be able to know statically, during compilation, exactly when
any destructor will trigger. (It is fine for that timing to be "simultaneously
with all this other stuff.") This must be possible without super-linear growth
of complexity or memory usage for large programs when compiling.

## A Real Program

In the example program above, we would need to create a new destructor for
`temp_file`:

```
define the potential action<mv:example.com:example:/temp_file/destroy> {
    it also assigns the position</file_name>.
    it also assigns the position</file_handle>.
    it also assigns the position</buffer>.

    it happens when {
        this particle is being destroyed.
    } and it does {
        # All totally imaginary syntax that will never exist.
        flush the value in position</buffer> to the file in position</file_handle>.
        close the file in position</file_handle>::position</file_system> using the value in position</file_handle>.
        delete the file at the value in position</file_name>.
    }
}

# And add it to temp_file.
define the potential position<mv:example.com:example:/temp_file> {
    it may only contain particles where {
        it has the action</temp_file/construct>.
        it has the action</temp_file/create>.
        it has the action</temp_file/destroy>.
    }
}
```

Because this destructor depends on `position</buffer>`,
`position</file_handle>`, and `position</file_name>`, it is guaranteed to be run
before those particles are destroyed.

Local particles would be destroyed exactly the same way---by defining a
potential action and assigning it to that particle. That does mean that anything
a local destructor touches has to be something defined by that particle. (In
other words, it can't refer to other local positions in the Action Statements
Block.) I currently think that's okay in terms of a software design requirement.

## Why This is the Right Solution

I had a whole other solution mapped out here that defined "destruction blocks"
on positions. You can actually see it in the history of this file, because I
checked it in for posterity. The problem is that particles can move! So you have
to be able to assign destructors to _particles_, not positions.

The destructor semantics for position-defined destructors were also very complex
(you can see them in the commit history of this doc.)

This solution is not only elegant (it changes destruction ordering in the
minimal fashion necessary), it is also tremendously more flexible than the
destructor system of most programming languages. You can specify multiple
destructors. You can re-use one destructor's code across multiple different
"types." You can have conditional destructors that only fire when the action is
in the state where it actually needs the destructor.

The one trade-off is that you have to add the action to any position you need
destroyed in that way. However, you can easily add it to a global position and
then every time you reference that global position, it will have that destructor
on it.

## Forward Compatibility

This is a very hard decision to walk back, because we are allowing a type of
action with very specific semantics. However, I am relatively convinced that
this solution is the only reasonable logical solution (that is, there actually
are no other options that make sense for Define, for destructor implementation).

If we change our design for destructors in a way that enforces some other
ordering in the future, we could refactor existing programs into that order. It
would change their functionality, but that would be intentional. We would still
have enough information in existing programs to know what the minimal safe order
is, due to interface/implied position dependencies.

## Refactoring Existing Systems

To my knowledge, this system is significantly more powerful than the destructor
syntax available in any other programming language. As such, we should be able
to implement the destructor syntax of every other language. The one thing we
wouldn't necessarily do is implement the destructor _semantics_ of those
languages, because we have very specific destruction semantics. As such,
refactoring existing programming languages into Define might require some
explicit destructor behavior. However, it's also possible that we have more
rigorous destructor semantics than most languages and thus our safety guarantees
are better at performing the _intent_ of destructors in other languages.
