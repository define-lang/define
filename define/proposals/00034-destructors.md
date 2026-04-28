# Define Language Proposal 34: Destructors

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** January 29, 2026
- **Date Finalized:**

## Problems

Due to the way that dimension point destruction is defined in
[DLP 31](00031-destroying-dimension-points.md), there is no way to guarantee
that any sort of "cleanup" code will run when you destroy a dimension point.
This happens because actions that a dimension point has are removed before the
dimension point is destroyed, so there can't be any actions that reference the
position by the time it is removed.

However, it's often necessary to guarantee that some action happens when a
dimension point is destroyed. For example, if you have a library that generates
temporary files, you need to be confident the file will be deleted when the
program ends. If you open a socket, you need to close it. And so forth.

Most programming languages handle this with "destructors," which are functions
that run right before an object is destroyed. They involve doing all the cleanup
for a whole class.

### The Destruction Cascade Causes a Problem

We have a particularly special problem. Imagine this program:

```
define the potential position<mv:example.com:example:/file_name> {
    it may only contain dimension points where {
        it has a value that is a string.
    }
}

define the potential position<mv:example.com:example:/file_handle> {
    it also assigns the position</file_system>.

    it may only contain dimension points where {
        it has a value that is an integer.
    }
    after it is assigned {
        create a dimension point in position</file_system>.
        # Some code that interacts with position</file_system>.
    }
}

define the potential position<mv:example.com:example:/buffer> {
    # Imagine we have some syntax to define a byte buffer that we
    # need to write to the disk before the program terminates.

    after it is assigned {
        create a dimension point in this position.
    }
}

define the potential position<mv:example.com:example:/temp_file/create> {
    it also assigns the position</file_name>.
    it also assigns the position</file_handle>.

    define the position<run>.
    define the position<completed>.

    it happens when {
        the position<run> has a dimension point.
    } and it does {
        create a dimension point in position</file_name>.
        set the value in position</file_name> to "/tmp/foo". # Imaginary syntax
        create a dimension point in position</file_handle>.
        set the value in position</file_handle> to 1.
        create a dimension point in position<completed>.
    }
}

define the potential position<mv:example.com:example:/temp_file> {
    it may only contain dimension points where {
        it has the position</buffer>.
        it has the action</temp_file/create>.
    }
    after it is assigned {
        create a dimension point in this position.
    }
}

define the position<x> {
    it may only contain dimension points where {
        it has the position<mv:example.com:example:/temp_file>.
    }
}
create a dimension point in position<x>.
create a dimension point in position<x>::action</temp_file/create>::position<run>.
wait until {
    the position<x>::action</temp_file/create>::position<completed> has a dimension point.
}
destroy the dimension point in position<x>.
```

This results in a dependency tree that looks like this, respecting the order in
which everything was assigned:

```
position<x>
|
-- position</temp_file>
   |
   -- position</buffer>
   -- position</file_name>
   -- position</file_system>
   -- position</file_handle>
   -- action</temp_file/create>
      |
      -- position<run>
      -- position<completed>
```

According to [DLP 31](00031-destroying-dimension-points.md), that destruction
statement cascades like this:

1. Destroy the dimension point in
   `action</temp_file/create>::position<completed>`.
2. Destroy the dimension point in `action</temp_file/create>::position<run>`.
3. Unassign `action</temp_file/create>` from
   `position<x>::position</temp_file>`.
4. Destroy the dimension point in `position</file_handle>`.
5. Unassign `position</file_handle>` from `position<x>::position</temp_file>`.
6. Destroy the dimension point in `position</file_system>`.
7. Unassign `position</file_system>` from `position<x>::position</temp_file>`.
8. Destroy the dimension point in `position</file_name>`.
9. Unassign `position</file_name>` from `position<x>::position</temp_file>`.
10. Destroy the dimension point in `position</buffer>`.
11. Unassign `position</buffer>` from `position<x>::position</temp_file>`.
12. Destroy the dimension point in `position<x>::position</temp_file>`.
13. Unassign `position</temp_file>` from `position<x>`.
14. Destroy the dimension point in `position<x>`.

However, during destruction, we need to do the following:

1. The buffer needs the file_handle in order to flush its data to the disk.
2. We need to close the file_handle.
3. We need to delete the file on the disk using the file_name.

(Yes, it doesn't make sense to flush the file just to delete it, but pretend
that we need to do that for some reason in our program.)

Those three things have to happen in exactly that order, but the cascade doesn't
indicate that they depend on each other at all. The only thing that knows all
three of those positions exist is `position</temp_file>`. However, by the time
we get to destroying the dimension point in `position</temp_file>`, it no longer
has any qualities and so it can't _know_ about those other positions in order to
use them for cleanup.

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

### Moving Dimension Points

We can't just check what positions destructors are registered to, because
dimension points can move between positions. For example, imagine this program:

```
# Inside an Action Statements Block:
define the position<temp_file> {
    before destruction starts {
        # Delete the file.
    }
}
define the position<file>.
create a dimension point in position<temp_file>.
move the dimension point in position<temp_file> to position<file>.
```

When that Action Statements Block ends, only `file` has a dimension point in it,
but the destructor that was defined in `temp_file` needs to fire.

## Solution

### New Action Trigger Condition

We add a new trigger condition that actions can check:

`this dimension point is being destroyed`

We refer to this as a "destructor condition," and any action that checks this
condition as a "destructor."

Actions containing this condition may check any other condition they wish, as
well, which allows for the implementation of conditional destructors.

Note that unlike Position Assignment Blocks, destructors have normal Action
Statement Blocks that may _not_ refer to `this dimension point`.

### When It Is Checked

During the destruction cascade defined in
[DLP 31](00031-destroying-dimension-points.md), destruction conditions are
checked before the dimension points of an action would be destroyed. If the
action would trigger, it runs _synchronously_ during the cascade, completing
before the cascade continues.

This is an exception to the rule that actions may not trigger during the
cascade.

For clarity, this means destructors will trigger in the reverse order they were
assigned to a dimension point (the cascade inherently behaves that way).

Any actions triggered _by_ a destructor are still run asynchronously. This means
they must detect the paradox of attempting to work on positions that may be in
the middle of being deleted. (Attempting to destroy a dimension point and do any
other action to it simultaneously is a paradox.) In reality, this means that
essentially all actions triggered during a destructor will require appropriate
`wait until` blocks, because actions can only reference positions the action
knows about (which are inherently positions assigned to this dimension point).

Note that these semantics make position initialization and dimension point
destruction very different: init runs when a _position_ is _assigned_, and
destructors run when a _dimension point_ is _destroyed_.

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
        this dimension point is being destroyed.
        OR
        the position<run> has a dimension point.
    } and it does {
        # All totally imaginary syntax that will never exist.
        flush the value in position</buffer> to the file in position</file_handle>.
        close the file in position</file_system> using the value in position</file_handle>.
        delete the file at the value in position</file_name>.
    }
}

# And add it to temp_file.
define the potential position<mv:example.com:example:/temp_file> {
    it may only contain dimension points where {
        it has the position</buffer>.
        it has the action</temp_file/create>.
        it has the action</temp_file/destroy>.
    }
    after it is assigned {
        create a dimension point in this position.
    }
}
```

That would then trigger as Step 2 of the cascade described in the Problems
section, because `/temp_file/destroy` is the last action assigned to the
dimension point.

Local dimension points would be destroyed exactly the same way---by defining a
potential action and assigning it to that dimension point. That does mean that
anything a local destructor touches has to be something defined by that
dimension point. (In other words, it can't refer to other local positions in the
Action Statements Block.) I currently think that's okay in terms of a software
design requirement.

## Why This is the Right Solution

I had a whole other solution mapped out here that defined "destruction blocks"
on positions. You can actually see it in the history of this file, because I
checked it in for posterity. The problem is that dimension points can move! So
you have to be able to assign destructors to _dimension points_, not positions.

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
