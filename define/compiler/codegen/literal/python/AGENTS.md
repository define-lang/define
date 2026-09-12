# Literal Python Code Generation

## Python and Template Responsibilities

- Jinja templates own emitted Python syntax. Python modules provide structured
  semantic data, allocated identifiers, and module/path names.
- Pass syntax components through template contexts, not Python source fragments;
  templates should spell attribute access, qualified references, calls,
  statements, annotations, imports, and other expressions.
- Give subtemplates and macros small, explicit APIs.
- Indent Jinja statements according to their Jinja nesting, independently of the
  indentation of the Python they emit.
