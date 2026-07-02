# Define Language Proposal 26: Action Triggering Order

- **Author:** Max Kanat-Alexander
- **Status:** Cancelled
- **Date Proposed:** January 22, 2026
- **Date Finalized:** July 2, 2026

## Problems

This Define Language Proposal used to describe a system of concurrency that was
never implemented. This proposal was written out of order---it solved a problem
we did not yet need to solve at that point in the design of the language: how to
trigger actions that trigger on a shared implied position. Instead, I started
off the actual implementation in a simpler state (not allowing actions to
trigger on implied positions) and realized there as a simpler concurrency model
that could still be derived from that.

There may still be a future proposal that needs this solution. Its history is
recorded in the version control history of this file.

## Solution

This proposal is now superseded by
[DLP 44 (Deterministic Automatic Concurrency)](00044-deterministic-automatic-concurrency.md).

At this point in the design of the language (January 22, 2026) it would have
been more accurate to say that all actions and operations within actions trigger
synchronously, in order, and that concurrency will be solved later.

## A Real Program

No real programs were ever written with this syntax or these semantics.

## Why This is the Right Solution

I decided that it wasn't, actually.

## Forward Compatibility

Irrelevant since it never got implemented.

## Refactoring Existing Systems

There were no existing programs written using this syntax or these semantics.
