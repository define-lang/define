# Define Language Proposal 34: Destructors

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** January 29, 2026
- **Date Finalized:**

## Problems

Due to the way that particle destruction is defined in
[DLP 31](00031-destroying-particles.md), there is no way to guarantee that any
sort of "cleanup" code will run when you destroy a particle. This happens
because actions that a particle has are removed before the particle is
destroyed, so there can't be any actions that reference the position by the time
it is removed.

However, it's often necessary to guarantee that some action happens when a
particle is destroyed. For example, if you have a library that generates
temporary files, you need to be confident the file will be deleted when the
program ends. If you open a socket, you need to close it. And so forth.

Most programming languages handle this with "destructors," which are functions
that run right before an object is destroyed. They involve doing all the cleanup
for a whole class.

### The Destruction Cascade Causes a Problem

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

define the potential position<mv:example.com:example:/temp_file/create> {
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
        it has the position<mv:example.com:example:/temp_file>.
    }
}
create a particle in position<x>.
create a particle in position<x>::position</temp_file>.
create a particle in position<x>::action</temp_file/create>::position<run>.
destroy the particle in position<x>.
```

This results in a dependency tree that looks like this, respecting the order in
which everything was assigned:

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

According to [DLP 31](00031-destroying-particles.md), that destruction statement
cascades like this:

1. Destroy the particle in `action</temp_file/create>::position<completed>`.
2. Destroy the particle in `action</temp_file/create>::position<run>`.
3. Unassign `action</temp_file/create>` from
   `position<x>::position</temp_file>`.
4. Unassign `action</file_handle/construct>` from `position</file_handle>`.
5. Destroy the particle in `position</file_handle>::position</file_system>`.
6. Unassign `position</file_system>` from `position</file_handle>`.
7. Destroy the particle in `position</file_handle>`.
8. Unassign `position</file_handle>` from `position<x>::position</temp_file>`.
9. Destroy the particle in `position</file_name>`.
10. Unassign `position</file_name>` from `position<x>::position</temp_file>`.
11. Unassign `action</temp_file/construct>` from
    `position<x>::position</temp_file>`.
12. Destroy the particle in `position</buffer>`.
13. Unassign `position</buffer>` from `position<x>::position</temp_file>`.
14. Destroy the particle in `position<x>::position</temp_file>`.
15. Unassign `position</temp_file>` from `position<x>`.
16. Destroy the particle in `position<x>`.

However, during destruction, we need to do the following:

1. The buffer needs the file_handle in order to flush its data to the disk.
2. We need to close the file_handle.
3. We need to delete the file on the disk using the file_name.

(Yes, it doesn't make sense to flush the file just to delete it, but pretend
that we need to do that for some reason in our program.)

Those three things have to happen in exactly that order, but the cascade doesn't
indicate that they depend on each other at all. The only thing that knows all
three of those positions exist is `position</temp_file>`. However, by the time
we get to destroying the particle in `position</temp_file>`, it no longer has
any qualities and so it can't _know_ about those other positions in order to use
them for cleanup.

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

Actions containing this condition may check any other condition they wish, as
well, which allows for the implementation of conditional destructors.

Like constructors, destructors are ordinary actions with normal Action Statement
Blocks, and so they may _not_ refer to the particle itself.

### When It Is Checked

During the destruction cascade defined in
[DLP 31](00031-destroying-particles.md), destruction conditions are checked
before the particles of an action would be destroyed. If the action would
trigger, it is logically triggered at that point during the cascade, and should
be _verified_ as though that is when it triggered. (However, its actual moment
of triggering at runtime is determined in the normal way that Define determines
when actions trigger, described in a later proposal.)

This is an exception to the rule that actions may not trigger during the
cascade.

For clarity, this means destructors will trigger in the reverse order they were
assigned to a particle (the cascade inherently behaves that way).

Note that these semantics make constructors and destructors somewhat mirror each
other: constructors run _after_ a particle is _created_, and destructors run
_before_ a particle is _destroyed_. So there's always a particle taking an
action.

### Static Analysis Requirement

The compiler must be able to know statically, during compilation, exactly when
any destructor will trigger. This must be possible without super-linear growth
of complexity or memory usage for large programs when compiling.

## A Real Program

In the example program above, we would need to create a new destructor for
`temp_file`:

```
define the potential action<mv:example.com:example:/temp_file/destroy> {
    it also assigns the position</file_name>.
    it also assigns the position</file_handle>.
    it also assigns the position</buffer>.

    define the position<run>.

    it happens when {
        this particle is being destroyed.
        OR
        the position<run> has a particle.
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

That destructor fires at the very beginning of the cascade---before Step 1 of
the sequence shown in the Problems section---because `/temp_file/destroy` is the
last action assigned to the particle and is therefore the first quality
unassigned during destruction.

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

This solution is not only elegant (it doesn't really have to change the cascade
at all), it is also tremendously more flexible than the destructor system of
most programming languages. You can specify multiple destructors. You can re-use
one destructor's code across multiple different "types." You can have
conditional destructors that only fire when the action is in the state where it
actually needs the destructor.

The one trade-off is that you have to add the action to any position you need
destroyed in that way, which forces certain software design patterns on
well-designed Define programs (that is, it means you want to have potential
positions that define objects that need destructors, instead of just providing a
collection of actions and positions that the developer can _choose_ to assign to
a position). Once we implement access controls (in future proposals), the way
you implement these design patterns will be more apparent.

## Forward Compatibility

This is a very hard decision to walk back, because we are allowing complex
trigger conditions in actions. However, I am relatively convinced that this
solution is the only reasonable logical solution (that is, there actually are no
other options that make sense for Define, for destructor implementation).

Now, theoretically, provided we enforce that destructor triggering is always
statically analyzable, we can still convert Define programs into using some
other system, but it could get pretty messy, because we would have to make sure
the destructors trigger under the exact same conditions.

## Refactoring Existing Systems

To my knowledge, this system is significantly more powerful than the destructor
syntax available in any other programming language. As such, we should be able
to implement the destructor syntax of every other language. The one thing we
wouldn't necessarily do is implement the destructor _semantics_ of those
languages, because we have very specific destruction orders. As such,
refactoring existing programming languages into Define might require some
explicit destructor behavior.
