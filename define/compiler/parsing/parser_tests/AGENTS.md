# Parser Tests Instructions

When adding or updating tests in `define/compiler/parsing/parser_tests/`, follow
these rules:

- Use the `parse` fixture (type `Parse` from `conftest`). It asserts
  `diagnostics == []`, raises any parse exception, and returns the
  `ast.Program`. Use `pytest.raises` for tests that expect a parse error. Only
  use the `parse_with_diagnostics` fixture when you need the parser's whole
  result (e.g. to check non-empty diagnostics).
- Prefer the format `mv:define-lang.org:parser` as the FQUN for global
  definitions in tests, rather than a bare universe name like `standard`.
