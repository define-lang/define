# Define Testdata Organization

Testdata in the subdirectories of this directory must be owned by exactly one
Python test and use this path:

```text
define/testdata/<phase>/<test module without _test>/<scenario name>/
```

For example, `test_short_form_global_reference` in `create_particle_test.py`
owns:

```text
define/testdata/reference_graph/create_particle/short_form_global_reference/
```

For a test method in a class, prefix the function-derived name with the class
name without `Test`, converted to snake case, and separate the two parts with
`__`. For example, `TestCreateParticle.test_invalid_local_name_char` owns:

```text
define/testdata/reference_graph/chained_name/create_particle__invalid_local_name_char/
```

- Use the dedicated `*_testdata*` fixture for the scenario type. Never read a
  convention-organized path directly from a test.
- Every test-module directory has its own `BUILD.bazel` and a filegroup named
  after that directory. Make its Python test target depend on the shorthand
  package label, such as `//define/testdata/reference_graph/create_particle`;
  never define all module targets in `define/testdata/BUILD.bazel` or make an
  individual Python test depend on the repository-wide `testdata_files` target.
- When renaming an owning test module or function, use `git mv` to rename its
  testdata directory in the same change.
- A non-filesystem scenario has a `source.dfn` at the scenario root. Supporting
  configuration may accompany it.
- A filesystem scenario contains the complete project tree, including its
  `.define` configuration. Tests change directly to its read-only runfiles
  directory before validating it.
- Put a test function's conceptual explanation at the start of its Define entry
  source as `#` comments instead of using a Python test docstring. Do not add
  those comments when comments, exact bytes, missing content, or exact source
  layout are part of the behavior under test.
- Run `//define/testdata:testdata_test` after adding, removing, or renaming
  convention-organized testdata.
