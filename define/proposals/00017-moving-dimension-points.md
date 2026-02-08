# Define Language Proposal 17: Moving Dimension Points

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** January 14, 2026
- **Date Finalized:**

## Problem

Action has to be able to occur in programs. One of the pre-requisites for any
action is for motion to be able to occur. In the way we conceive of programs,
motion means "a dimension point moves to another position."

One could imagine a universe instead where you never move dimension points and
only create new copies of them in new positions. This universe would quickly
become pretty static, though, as you'd never be able to relocate anything you
made, ever.

Thus, we need a syntax for moving dimension points.

## Solution

Similar to our creation syntax, the syntax for moving dimension points will be:

```
move the dimension point in position<foo> to position<bar>.
```

The downside of this syntax is that these lines get very long when we have long
position names. That's an acceptable trade-off as we don't care about verbosity
in Define.

Note that it is an error to attempt to move a dimension point into the position
it is currently in (that doesn't make any sense).

It is an error to move a dimension point into a position already occupied by a
dimension point.

## A Real Program

See above. There isn't enough syntax yet defined to make an actual real program
here.

## Why This is the Right Solution

As with other syntax in Define, we use multiple words. This protects our forward
compatibility and also reads intuitively for both humans and AI agents.

I believe this syntax doesn't need anything else other than what we have now (a
from position and a to position). We may need some syntax for moving multiple
dimension points all at once, but we don't need it yet.

We could have removed "the dimension point in" but then the sentence wouldn't
really be _true_. You're not moving the position. I think that actually would be
confusing for programmers as they read it.

## Forward Compatibility

There is no ambiguity in the language between this statement and any other
statement, and its meaning is completely unambiguous.

## Refactoring Existing Systems

There are no existing systems to refactor. This syntax also doesn't have any
clear equivalent in most programming languages (except perhaps Rust, where you
can transfer ownership of a variable to a new function), so I can't even provide
a good "we could refactor existing languages" example.
