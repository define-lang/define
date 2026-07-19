# Program Validator Tests Instructions

When adding or updating tests in
`define/compiler/validator/structural/program_validator_tests/`, follow these
rules:

- Never filter diagnostics by type or by file. Always assert on the exact set of
  diagnostics returned.
- Never break one line of Define source code across two Python lines, even if it
  creates a very long Python string.
- Before adding, removing, renaming, or updating a data-backed test, read and
  follow `define/testdata/AGENTS.md`.
