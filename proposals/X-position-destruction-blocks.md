# Define Language Proposal X: Position Destruction Blocks

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** January 26, 2026
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
    this dimension point must have the position</file_system>.

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
    this dimension point must have the position</file_name>.
    this dimension point must have the position</file_handle>.

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

## Solution

### New Syntax

We add a new syntax that exists for all position definitions (both potential and
real positions):

```
before destruction starts {
    # Position Destruction Block
}
```

The Position Destruction Block may contain almost any syntax available in a
Position Assignment Block, with one exception: it may not contain
`destroy the dimension point in this position`, as that would cause an obvious
infinite loop. The parser will actually allow that in syntax, but the validator
will deny it as creating an infinite loop.

It is strongly recommended that Position Destruction Blocks not make _any_
change to shared positions on this dimension point (other positions that are
assigned to the same dimension point as this position), as that makes it much
harder to reason about how destruction behaves (although the compiler will
handle that correctly, when possible). However, we allow it because it may be
necessary to do it in rare cases.

### Semantics

Position destruction blocks trigger any time a dimension point in this position
is _about_ to be destroyed. In other words, the very first action that a
destruction statement takes is to run the Position Destruction Block, before it
does any other work.

Note that this makes position initialization and destruction very different:
init runs when a _position_ is _assigned_, and destruction runs when a
_dimension point_ is _destroyed_.

### Cascade

Position Destruction Blocks run at the start of any position destruction
statement. If we imagine the cascade as a series of position destruction
statements, then that fully encapsulates the behavior of position destruction in
the cascade.

However, to make it clear, here is what the cascade looks like. This is the same
order as defined in [DLP 31](00031-destroying-dimension-points.md), but
expressed recursively, for the sake of simplicity.

1. First, the Destruction Block on the named position executes.
2. Then we suspend the constraints defined by the named position's definition,
   in terms of what qualities must be assigned to this dimension point.
3. We then go through the assigned qualities on the named position in reverse
   order to how they were assigned and take the following actions:
   1. Start a cascade on that quality:
      - **Positions**: If we encounter a position that contains a dimension
        point, we start a cascade on that dimension point.
      - **Actions**: If we encounter an action, we start a new cascade on each
        position that action defines in its Action Definition Block, in reverse
        order of how the positions were defined in code.
   2. After we return from the cascade on the position or action, unassign that
      quality (that position or that action) from this position.
4. Now we destroy the dimension point in this position.

"Starting" a cascade means starting from step 1 above on a dimension point.

That implements the same destruction order as the cascade in
[DLP 31](00031-destroying-dimension-points.md), with the addition of Position
Destruction Blocks that happen as we work our way "forward" through the cascade,
and clarifying that constraint removal happens _after_ we run the Destruction
Block.

In our above example in the Problems section, this means that we would run
destruction blocks on positions in this order:

1. `position<x>`
2. `position<x>::position</temp_file>`
3. `position<x>::position</temp_file>::action</temp_file/create>::position<completed>`
4. `position<x>::position</temp_file>::action</temp_file/create>::position<run>`
5. `position<x>::position</temp_file>::position</file_handle>`
6. `position<x>::position</temp_file>::position</file_system>`
7. `position<x>::position</temp_file>::position</file_name>`
8. `position<x>::position</temp_file>::position</buffer>`

This may be confusing for us, the language implementers, but it is actually
relatively intuitive for developers: while a Destruction Block runs, it still
has access to everything the position defines, so it can clean it up.

Position Destruction Blocks are executed synchronously when they occur in the
cascade. The compiler _may_ choose to run them concurrently if it can prove it
is safe to do so (that doing so could not cause a paradox).

### Cascades Are Per Destruction

To be clear, the "destruction cascade" is something that happens only with a
single destruction statement. So when we have multiple destruction statements,
there are multiple cascades. At the end of an Action Statements Block, we don't
first run all destructors and then destroy all dimension points. We just insert
destruction statements and let them work like they normally work.

### Triggering Other Actions During Destruction

Actions triggered during a Position Destruction Block are full async, just like
all other actions. However, they are considered to happen simultaneously with
the entire cascade. In other words, you probably want to have a `wait until`
statement if you trigger any action on _this_ dimension point during a Position
Destruction Block, because the action is just about to be removed by the
cascade. Thus, the compiler will throw an error about a paradox (simultaneously
triggering an action and unassigning it).

## A Real Program

### Solving the Example Problem

In the example program above, here is how we might add a Destruction Block to
`/temp_file` to clean up the file automatically when the dimension point is
destroyed:

```
define the potential position<mv:example.com:example:/temp_file> {
    it may only contain dimension points where {
        it has the position</buffer>.
        it has the action</temp_file/create>.
    }
    after it is assigned {
        create a dimension point in this position.
    }
    before destruction starts {
        # All totally imaginary syntax that will never exist.
        flush the value in position</buffer> to the file in position</file_handle>.
        close the file in position</file_system> using the value in position</file_handle>.
        delete the file at the value in position</file_name>.
    }
}
```

### Local Position Destruction

Here's an example of destroying a local position that has a destruction block:

```
define the potential action<mv:example.com:example:/enter_bathroom> {
    define the position<locked>.
    define the position<enter>.

    it happens when {
        the position<enter> has a dimension point.
    } and it does {
        # I JUST REALIZED THERE IS A PROBLEM: DESTRUCTORS NEED TO TRACK TO DIMENSION POINTS, NOT POSITIONS.
    }
}
```
