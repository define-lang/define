# Define Language Proposal 18: Modular Constraints

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** January 14, 2026
- **Date Finalized:**

## Problem

In general, Define intends to enforce constraints statically, as much as is
realistically possible.

Conceptually, a constraint is a sort of limited machine that operates in the
universe of reflection. A view point says "I would like to create, change, or
destroy a dimension point in some fashion," and the machine stops that from
happening. The questions that arise are things like:

1. How much freedom do I need to allow to such machines in order to enable them
   to enforce every constraint that anybody could realistically need?
2. How do we keep those constraints _in_ the universe of reflection (i.e., make
   them enforced by the compiler) as much as possible and not let them "leak"
   into being machines that exist in the "real" universe of the program (i.e.,
   don't have to have them as runtime checks)?
3. How do I express that in syntax?
4. How do I make it so that human programmers can reason about how those
   constraints will behave? How can they predict exactly what is going to happen
   with those constraints when they write them?
5. How do I make enforcing those constraints actually feasible for the computer?

Most of these problems are solved by ensuring that constraints can be enforced
_modularly_. That is, when solving constraints, we need to be doing it only on
the part of the program we are currently looking at, not the whole program all
at once. If you have to turn a whole program into one gigantic
constraint-solving equation, solving that equation with a computer quickly
becomes intractable. Forcing yourself into a modular model also simplifies how
you think about constraints, providing a much clearer path to syntax, a simpler
mechanism for programmers to reason about how constraints behave, etc.

In order to enforce this modularity, there has to be some way to "cut off"
constraints or localize them so that the solver only has to look at part of the
program. You also want to be able to compile any part of the program and know
that it is internally correct and consistent by itself, without having to
compile the whole rest of the program _outside_ of that piece to guarantee that.

The one piece this doesn't solve is the first problem---how you give people
sufficient freedom. What it _does_ do, however, is create a framework within
which we have to solve that problem. Without some limitation on how constraints
are defined, there's no way to reason about how we would provide that freedom
reasonably.

## Solution

This problem is complex enough that it will require multiple proposals, but all
of them work together to create a cohesive solution. As such, I am writing this
proposal to contain the overall design of the solution, and later proposals will
fill in the details for each part.

I have been doing some experiments, and I believe that every constraint we need
can be enforced by having the following system:

1. Positions statically declare what qualities are required for dimension points
   in that position. Attempting to create a dimension point without those
   qualities in that position, or move a dimension point into that position that
   does not have those qualities, will produce an error at compile time.
   Dimension points may have _more_ qualities than the ones listed, but they
   guarantee that they will _always_ have the ones listed.
2. Qualities define constraints on the dimension points to which they are
   assigned. This enforces a significant degree of modularity, as it prevents
   constraints from being able to grow in complexity beyond what the quality
   definition knows about. When multiple qualities are on a dimension point,
   their conditions are joined together with a logical AND. These are enforced
   statically by the compiler. If constraints inherently create a logical
   conflict when merged onto the same dimension point, ideally the compiler will
   catch that.
3. Triggers declare preconditions that must be true before they start. This is
   what allows for a lot of local evaluation of constraint satisfaction. You
   know what is true inside the boundary of the trigger, so you don't have to
   verify the entire world outside of the trigger in order to know the code
   inside the trigger is correct. These are enforced statically by the compiler
   when it sees a trigger being activated.
4. Within triggers, there are checks that enforce requirements and explain what
   will happen at runtime if those requirements fail. When the requirement
   fails, the code that runs must either (a) cause the trigger to stop (b)
   result in a state that guarantees the original requirements. When the
   compiler knows that those requirements are guaranteed to hold, it can
   optimize away the check. Otherwise, the check remains in the code at runtime
   and the "or" condition executes when it fails.
5. Constraints that involve statements about multiple dimension points may be
   defined as part of forms, but only about dimension points that are in the
   form. This is also going to matter for forms where the internal points are
   anonymous, like a bag, but where you want to say "every ball in this bag is
   green." Some nuance is necessary here to make it clear to the programmer when
   constraints should be defined on forms vs when they should just be part of a
   quality that itself defines multiple positions.

It is possible that 3 and 4 can be merged and there just needs to be a syntax
that indicates "this check may survive until runtime, in some cases, because it
has an alternate condition." Then the compiler would just need to be able to
detect dead "or" blocks (conditions that are never violated and thus never make
it into the runtime of the program).

## A Real Program

We haven't defined syntax for any of this. However, imagine these pieces of a
program in imaginary syntax:

```
define the quality<example.com:bank:/account/nonzero> {
    it has a numeric value.
    it has the constraint {
        the value is greater than 0.
    }
}

define the quality<example.com:bank:/account> {
    define the position<balance> {
        it may only contain dimension points where {
            it has the quality<example.com:bank:/nonzero>.
        }
    }
    define the form<transactions> {
        it is a bag.
        it may only contain dimension points where {
            it has the quality<standard:/integer>
        }
    }

    define the trigger<withdraw> {
        define the position<amount> {
            it may only contain dimension points where {
                it has the quality<example.com:bank:/nonzero>.
            }
        }
        require that {
            position<amount> <= position<balance>
        }
    }

    define the trigger<adjust> {
        define the position<add> {
            it may only contain dimension points where {
                it has the quality<example.com:bank:/nonzero>.
            }
        }
        define the position<remove> {
            it may only contain dimension points where {
                it has the quality<example.com:bank:/nonzero>.
            }
        }
        define the position<error> {
            it may only contain dimension points where {
                it has the quality<standard:/error>.
            }
        }
        require that {
            position<balance> + (position<add> - position<remove>) > 0
        } or {
            # Put an error in position<error> and then:
            stop this trigger.
        }
    }
}
```

## Why This is the Right Solution

I spent an extensive amount of time investigating constraint systems and trying
different potential syntaxes.

At first I opted for a very flexible constraint syntax where you could define a
single constraint that could refer to multiple positions with numerous types of
conditions in it. However, this quickly led to near-infinite complexity in
solving the equations, as well as great complexity in implementation, reasoning
through how the system would behave, figuring out _when_ constraints need to be
enforced, etc. For example, imagine a constraint that looks like this:

```
define the constraint<complex> {
    (
        position<x> has the quality<foo>
        AND
        position<y> has the quality<foo>
    )
    OR (
        position<x> has the quality<bar>
        AND
        the value in position<x> is greater than 3
    ) OR (
        position<y> has the quality<foo>
        AND
        the value in position<y> is "lorem ipsum"
    )
}
```

That creates so many problems. How does that help the compiler reliably know
what's in position<x> or position<y> when it has to refer to them? When do we
define that constraint, do we define it before quality assignment or after it?
How do we know when we need to check the constraint (as written, we would need a
lot of trigger points in the program just to check if the constraint is still
true, and it would become complex to track it).

The key insight that simplified things was the idea that qualities and
constraints could be merged, and that thus the constraints could only refer to
the dimension point the quality was assigned on and other positions the quality
defined. That then led to only a few real problems:

1. If constraints were only part of qualities, how did you constrain which
   dimension points were allowed in a position in a way that was simple and
   guaranteed so the compiler can always figure it out? (The problem is that
   qualities, when assigned, are assigned to _dimension points_, not positions.)
2. Triggers could be triggered from multiple locations (multiple different code
   pathways could call the same function) and so it was not modularly solvable
   whether they were correct.
3. There can be external input to a program (user input, database reads, network
   input, etc.) where the program itself doesn't know the shape of the data it's
   getting, and where that data _could_ be wrong.

This was easily solved with the "requirement" system (parts 3 and 4 above).

## Forward Compatibility

Forward compatibility of the system depends largely on how we constrain what can
be written as a constraint. The simpler and more straightforward the constraints
are, the more freedom we have to refactor them into other syntaxes.

In particular, it is important that checking a constraint never has any side
effects. We want to be able to re-order constraints in the compiler for optimal
checking, or possibly even re-order them in actual code if we have to in the
future. If there's a side effect of checking some constraint, then we can't
re-order it, because the developer would expect side effects to happen in order.

One general limitation of constraint systems is that in order to refactor them,
you have to be able to solve both the new syntax and the old syntax. If we
wanted to move constraints outside of qualities, we would have to be able to
prove that was safe and had equivalent functionality, which might be tricky
depending on how we did it.

## Refactoring Existing Systems

There are no existing systems. Various bad constraint syntaxes would be hard to
refactor into anything else, reliably, which is why we need to get this right.
The goal here is to make _this_ thing be possible to refactor into the future.
