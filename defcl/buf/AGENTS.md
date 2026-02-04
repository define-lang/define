# Rules for DCL Buf Plugin

This directory contains a custom buf lint plugin written in Go.

## Go Execution

- Build the plugin with `go build -o buf-plugin-defcl .`
- Run tests with `go test -v ./...`

## Formatting

- Format Go code with `go fmt ./...`
- Format .md files with `prettier --write`

## Adding New Rules

1. Define a `check.RuleSpec` variable with the rule ID prefixed with `DEFCL_`.
2. Add the rule to the `spec.Rules` slice.
3. Implement the handler function.
4. Write tests before implementing the rule (TDD).
5. Add test proto files under `testdata/valid/` and `testdata/invalid/<rule>/`.

## Tests

- Use `checktest.CheckTest` for testing rules.
- Each rule should have at least one valid and one invalid test case.
- Test proto files should use `edition = "2023";`.

## Comments

- Only add comments that explain why code was written. Never add comments saying
  what code does.

## Dependencies

- Use `go get` to add new dependencies.
- The primary dependency is `buf.build/go/bufplugin` for the plugin framework.
