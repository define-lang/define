# The Define Programming Language

This directory contains the implementation, specification, documentation, and
tests of a programming language called "Define."

## Spec

- The specification for the language is in `spec/spec.md`. Only implement
  behavior if the spec says to do so.
- If I instruct you to implement behavior that isn't in the spec, do not
  research the codebase to find another spec. Instead, confirm with me that that
  is what I actually want.
- When updating `spec/spec.md`, follow the instructions written in the comment
  at the top of the file.

## Proposals

- The `proposals/` directory contains the reasoning for _why_ the language works
  the way it does. It does not contain normative instructions. Only the spec
  contains normative instructions. Only read proposals when necessary.
- If you read a proposal and it conflicts with the spec in a way you can't
  resolve, bring that to my attention.

## Compiler Codebase Structure

### High-Level Flow

```mermaid
flowchart LR
    Parsing --> Transformation
    Transformation --> StructuralValidation["Structural Validation"]
    StructuralValidation --> RefGraphValidation["Reference Graph Validation"]
    RefGraphValidation --> CLI
    CLI --> CodeGen["Code Generation"]
    CodeGen -.->|generated code imports| Runtime["runtime/literal.py"]
```

### Parsing

```mermaid
flowchart LR
    Grammar["grammar.lark"] --> Parser["parser.py"]
    ParseErrors["parser_exceptions.py"] --> Parser
    ErrorClassification["parser_error_classification.py"] --> Parser
    NameParser["name_parser.py"] --> Parser
    IndentValidator["indentation_validator.py"] --> Parser
```

### Transformation

```mermaid
flowchart LR
    AST["ast.py"] --> Transformer["transformer.py"]
```

### Structural Validation

```mermaid
flowchart LR
    FileValidator["validator/structural/file_validator.py"]
    NameValidators["validator/structural/name_validators.py"] --> FileValidator
    ScopeTracker["validator/scope_tracker.py"] --> FileValidator
    ReferenceGraph["graphs/reference_graph.py"] --> ProgramValidator
    FileValidator --> ProgramValidator["validator/structural/program_validator.py"]
    PathTracker["validator/structural/path_tracker.py"] --> ProgramValidator
    Config["config.py"] --> ProgramValidator
    ValidationResult["validator/validation_result.py"] --> ProgramValidator
    Stats["validator/stats.py"] --> ValidationResult
```

### Reference Graph Validation

```mermaid
flowchart LR
    ReferenceGraphValidator["validator/reference_graph/reference_graph_validator.py"]
    DefinitionPostorderValidator["validator/reference_graph/definition_postorder_validator.py"] --> ReferenceGraphValidator
    DPTracker["validator/reference_graph/particle_tracker.py"] --> DefinitionPostorderValidator
    ReferenceGraph["graphs/reference_graph.py"] --> ReferenceGraphValidator
    ActionCallGraph["graphs/action_call_graph.py"] --> ReferenceGraphValidator
    ValidationResult["validator/validation_result.py"] --> ReferenceGraphValidator
```

### Code Generation

```mermaid
flowchart LR
    PythonGenerator["codegen/literal/python/generator.py"] --> CodeGenerator["codegen/generator.py"]
    Naming["codegen/literal/python/naming.py"] --> PythonGenerator
    PositionDef["codegen/literal/python/position_definition.py"] --> PythonGenerator
    ActionDef["codegen/literal/python/action_definition.py"] --> PythonGenerator
    TemplateCtx["codegen/literal/python/template_context.py"] --> PythonGenerator
    TemplateEnv["codegen/literal/python/template_env.py"] --> PythonGenerator
    ActionStmts["codegen/literal/python/action_statements.py"] --> PositionDef
    ActionStmts --> ActionDef
    Template["codegen/literal/python/*.j2"] --> PythonGenerator
```

### CLI

```mermaid
flowchart LR
    ProgramValidator["validator/structural/program_validator.py"] --> Driver["driver.py"]
    ReferenceGraphValidator["validator/reference_graph/reference_graph_validator.py"] --> Driver
    CodeGenerator["codegen/generator.py"] --> Driver
    OverallStats["overall_stats.py"] --> Driver
    Diagnostics["diagnostics.py"] --> Driver
    Exceptions["exceptions.py"] --> Driver
    Driver --> Main["main.py"]
```

## Grammar

- The grammar for the language is in `compiler/grammar.lark`.
- When updating the grammar, use EBNF instead of regex.

## Parser

- The parser is in `compiler/parser.py`. Before changing the functionality of
  the parser, update the tests in `compiler/parser_tests` first, or write a new
  test in the same style if you are adding totally new functionality.
- The parser test does not depend on any files on the disk. It does not use
  `testdata/`. It does not use parameterized tests.

## Transformer

- The transformer turns the parse tree into an AST. The transformer is in
  `compiler/transformer.py`, the AST is in `compiler/ast.py`, and they both have
  tests.

## Validator

- The validator checks syntax that the parser can't check, and it also checks
  semantics.
- Validator coordinator code is in `compiler/validator/program_validator.py`.
- Per-file validation code is in `compiler/validator/file_validator.py`.
- Validator tests are in `compiler/validator/` and
  `compiler/validator/structural/program_validator_tests/`.

## Driver

- The Driver is the class that represents the compiler overall. It is in
  `compiler/driver.py`.
- When changing functionality in `compiler/driver.py` itself that creates new
  functionality, first update `compiler/driver_test.py`.
- When changing functionality `Driver.run`, first update
  `compiler/driver_run_test.py`.

## Fuzz Test

- The fuzz test (`compiler/driver_fuzz_test.py`) is tagged `manual` and does not
  run with `bazelisk test //...`. Run it explicitly with
  `bazelisk test //define/compiler:driver_fuzz_test` after changes to the
  parser, transformer, validator, or error classification code.
- Update the fuzz test's code genration when the syntax or semantics of the
  language change, so that the generated inputs remain representative of valid
  and near-valid Define source.
- When a fuzz test failure reveals a bug, add a targeted unit test for the
  affected component (parser, transformer, or validator) that reproduces the
  specific issue before fixing it.

## Code Generation

- Generator code is in `compiler/codegen/`, with the Python-specific generator
  in `compiler/codegen/literal/python/generator.py`.
- Integration test cases for the generator live in `compiler/codegen/testdata/`.
- After changing the code generator or any testdata, regenerate the expected
  outputs: `bazelisk run --noshow_progress //tools:regenerate_codegen_testdata`

## Implementation Sequence

- When I ask you to implement an entirely new language feature, first update
  only the grammar, the parser test, and the parser.
