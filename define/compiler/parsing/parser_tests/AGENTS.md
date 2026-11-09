# Parser Tests Instructions

When adding or updating tests in `define/compiler/parsing/parser_tests/`, follow
these rules:

- Use the `parse` fixture (type `Parse` from `conftest`). It asserts
  `diagnostics == []` and that there is no syntax error, and returns the
  `ast.Program`. For tests that expect a syntax error, use the
  `parse_syntax_error` fixture (type `ParseSyntaxError`), which returns the
  syntax error. Only use the `parse_with_diagnostics` fixture when you need the
  parser's whole result (e.g. to check non-empty diagnostics).
- Prefer the format `mv:define-lang.org:parser` as the FQUN for global
  definitions in tests, rather than a bare universe name like `standard`.
