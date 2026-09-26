# ast-grep Checks

- Match syntax-tree structure with `pattern`, `kind`, relational rules such as
  `has` and `inside`, and node fields. Use `regex` only for text that has no
  further structure, such as a set of identifier names or a string's contents,
  and combine it with `kind` so it applies to the intended node.
- A pattern determines the node it matches. Adding `kind` next to `pattern` does
  not change how the pattern parses; when a pattern snippet is ambiguous, use a
  pattern object with `context` and `selector`.
- A named metavariable must bind to the same node everywhere it appears in a
  rule. Use `$_` when sub-rules should match independently.
