# Define Validator

This directory contains all the phases of the Define validator.

## High-Level Components

The intentional design of the system is that we have the following components:

1. **Structural Validator**: This actually calls the parser, transformer, and
   config loader. Its primary duty is to build the "reference graph," which is a
   DAG of which global definitions reference each other. It loads and parses
   files in parallel and produces diagnostics primarily related to program
   structure: dependency configuration correctness, name formats, basic
   reference validity, and so on.
2. **Reference Graph Validator**: Takes the reference graph from the structural
   validator and produces the "action graph," which is a graph of which actions
   trigger other, when.

## Test Design

Tests live in different places depending on what they are designed to test. The
structural validator's tests test functionality that is primarily owned by the
structural validator. The reference graph tests are a bit more end-to-end, but
are designed to test those things for which the reference graph validator is
primarily responsible, or things where we can only understand the full outcome
after both structural validation and program validation have run.

All the tests run the full compiler pipeline, as compiler interactions can be
very complex. Tests should always strive to start from parsing actual Define
source, not constructing their inputs artificially.
