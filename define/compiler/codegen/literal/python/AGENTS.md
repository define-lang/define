# Literal Python Code Generation

Before changing literal Python execution codegen, read
[its design](execution_codegen_design.md) and canonical
[generated-code examples](action_execution_examples.md).

## Python and Template Responsibilities

- Jinja templates own emitted Python syntax. Python modules provide structured
  semantic data, allocated identifiers, and module/path names.
- Pass syntax components through template contexts, not Python source fragments;
  templates should spell attribute access, qualified references, calls,
  statements, annotations, imports, and other expressions.
- Give subtemplates and macros small, explicit APIs, and keep their control
  statements indented to reflect the generated Python structure.
