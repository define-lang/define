# Parser Tests Instructions

When adding or updating tests in `define/compiler/parser_tests/`, follow these
rules:

- Tests that check invalid syntax must assert a specific subclass of
  `DefineSyntaxError`, not `DefineSyntaxError` itself.
- Tests that check invalid syntax must assert relevant fields on the raised
  exception to verify correct location and token details
  (line/column/token/char, as applicable).
- Prefer the format `mv:define-lang.org:parser` as the FQUN for global
  definitions in tests, rather than a bare universe name like `standard`.
