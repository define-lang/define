# How to Write a Language Proposal

All language proposals must contain the following.

## Top-Level Info

The name of the author(s), the status of the document, the date it was
originally proposed (when it was first merged into this repository and the first
draft was completed), and the date it was finalized (when it was closed for
further modification).

The Status may be any of the following:

- Draft: This proposal is still subject to rapid modification by its authors and
  is not generally open for comment.
- Open for Comments: This proposal is accepting comments and feedback.
- In Review: This proposal is being reviewed by the person or group with the
  authority to change the language spec.
- In Implementation: Currently being implemented; may change somewhat if we
  discover issues during implementation.
- Finalized: Has been released for general use by programmers and will not be
  changed. Future adjustments require a new proposal.

## The Problems You Are Trying to Solve

Tell us what the problems are that you are trying to solve. We accept only
problems that have been actually experienced by somebody, not theoretical
problems that might happen. You must include an example program that shows that
problem.

## The Proposed Solution

Explain the solution. Specify the syntax.

All the problems described should have the same solution. If different problems
require different solutions, they should be in separate language proposals.

If the solution involves a trade-off (not all the problems can be perfectly
solved), acknowledge the trade-off here.

## A Real Program

An actual program written using the proposal. It does not have to execute. Our
first and foremost goal is to create a great programming language, so show that
your proposal creates a great programming language by showing an actual program
written with it. Even better if you can show what that program looked like
before your proposal and what it will look like after.

## Why This is the Right Solution

Tell us why this is the right solution to the problem you've proposed. Remember
the key points in our [concepts](../spec/concepts.md) and
[principles](../spec/principles.md), as that will heavily determine if we agree
with your reasoning or not.

In this section you may also want to list out all the alternative solutions that
were considered and discarded, including alternative syntax, to explain why you
didn't choose a different option.

## A Description of Forward Compatibility

How will we be able to change our mind about this language feature in the
future, easily? Ideally, include an example showing how we would
deterministically refactor a program written with your proposal into an
alternative syntax in the future. Attempt to logically demonstrate that there
are no counterexamples---that after we implement your proposal, it would be
impossible for a program to exist that we cannot refactor deterministically into
a different syntax.

The best ways to demonstrate forward compatibility are:

1. **Zero Ambiguity**: It should always be deterministically possible to
   disambiguate the exact intention of a piece of syntax compared to all other
   syntax that exists in Define. For example, it should never be ambiguous in
   code what a name means.
2. **Infinite Possibility**: Show how the design allows for an infinite (or
   effectively infinite) number of future possibilities if we want to change our
   mind about how things work. For example,
   [DLP 10](00010-configuration-directory.md) reserves all top-level directory
   names for use in Define itself so that we can change our mind about what goes
   into that directory, and there can't be any possible name conflicts there.

## Refactoring Existing Systems

Include an example showing how we will deterministically refactor all existing
define programs to use your feature, if it requires changing some existing
syntax.
