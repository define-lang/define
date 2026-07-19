# Parser Tests Instructions

When adding or updating tests in `define/compiler/parser_tests/`, follow these
rules:

- Use the `parse` fixture (type `Parse` from `conftest`) instead of calling
  `parser.Parser` directly. It asserts `diagnostics == []`, raises any parse
  exception, and returns the tree. Use `pytest.raises` for tests that expect a
  parse error. Only use the `p` fixture when you need access to the raw
  `ParseResult` (e.g. to check non-empty diagnostics).
- Tests that check invalid syntax must assert a specific subclass of
  `DefineSyntaxError`, not `DefineSyntaxError` itself.
- Tests that check invalid syntax must assert relevant fields on the raised
  exception to verify correct location and token details
  (line/column/token/char, as applicable).
- Prefer the format `mv:define-lang.org:parser` as the FQUN for global
  definitions in tests, rather than a bare universe name like `standard`.
- Before adding, removing, renaming, or updating a data-backed test, read and
  follow `define/testdata/AGENTS.md`.
