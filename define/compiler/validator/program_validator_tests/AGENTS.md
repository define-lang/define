# Program Validator Tests Instructions

When adding or updating tests in
`define/compiler/validator/program_validator_tests/`, follow these rules:

- Never filter diagnostics by type. Always assert on the exact set of
  diagnostics returned.
