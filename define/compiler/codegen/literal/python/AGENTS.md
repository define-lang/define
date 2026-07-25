# Literal Python Code Generation

## Python and Template Responsibilities

- Jinja templates own emitted Python syntax. Python modules provide structured
  semantic data, allocated identifiers, and module/path names.
- Pass syntax components through template contexts, not Python source fragments;
  templates should spell attribute access, qualified references, calls,
  statements, annotations, imports, and other expressions.
- Python reserved-word and built-in-name sets remain in `naming.py`.
- Give subtemplates and macros small, explicit APIs, and keep their control
  statements indented to reflect the generated Python structure.
