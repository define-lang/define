# Rules for DCL Buf Plugin

This directory contains a custom buf lint plugin written in Go.

## Adding New Rules

1. Define a `check.RuleSpec` variable with the rule ID prefixed with `DEFCL_`.
2. Add the rule to the `spec.Rules` slice.
3. Implement the handler function.
4. Write tests before implementing the rule (TDD).
5. Add test proto files under `testdata/valid/` and `testdata/invalid/<rule>/`.

## Tests

- Use `checktest.CheckTest` for testing rules.
- Each rule should have at least one valid and one invalid test case.

## Dependencies

- Use `go get` to add new dependencies.
- The primary dependency is `buf.build/go/bufplugin` for the plugin framework.
