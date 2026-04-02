# Rules for Define Project

We are working together to make a new type of programming language that has
never existed before.

See [define/spec/spec.md] for the language specification.

## Local Development Setup

- Before running Python locally (via `uv run`), generate the local dev
  environment: `uv run tools/setup_local_dev.py`
- This copies Bazel-generated files (lark standalone parsers and protobuf
  modules) into the source tree so that Python imports resolve outside of Bazel.
- Re-run this script after changing `.proto` files or `.lark` grammar files.

## Formatting

- After making a change to any file, reformat by running
  `bazelisk run --noshow_progress //tools:format`

## Python Execution

- If you have to run a local Python script, do it via `uv run`.

## Linting

- Linting runs when you run bazelisk build or test. Always lint files after
  editing them.
- Run `npx @bufbuild/buf lint` after making changes to .proto files in
  `defcl/schema` or `define/config`.
- Fix all linting errors that are reported.
- **Never disable pyright rules globally** in `pyproject.toml`. All basedpyright
  rules must remain enabled. When a pyright check fails:
  - Fix the type error in source code (add type annotations, use `cast()`,
    etc.).
  - Always verify fixes against the **Bazel** `pyright_test` targets, not just
    local `basedpyright` — the Bazel sandbox resolves dependencies differently.

## Imports

- Prefer importing modules instead of classes:. Example:
  `from define.compiler import ast` and then reference `ast.ASTNode` in the
  code.
- Only use `typing.TYPE_CHECKING` to fix ruff TC001, TC002, or TC003.
- Never do dynamic imports. (Never write an import statement inside of a
  function.)
- Never do conditional imports.

## Exceptions

- Do not swallow exceptions. Prefer to let exceptions bubble up to the user.
- Only catch the specific exceptions that the code throws. Never
  `catch Exception`.

## Comments

- Only add comments that explain why code was written. Never add comments saying
  what code does.

## Docstrings

- Avoid putting "Returns" clauses in docstrings on simple accessors where the
  return value is obvious from the function signature.

## Code Style

- Avoid non-descriptive variable names like `ref`.
- Prefer positive booleans. For example: `enable_feature=False` rather than
  `disable_feature=True`.
- Do not add `-> None` return annotations unless a type checker explicitly
  requires one.

## Git

- When renaming or moving files, always use `git mv` so that git records the
  change as a rename.
- Don't use git -C on the current directory.
- Never use `git commit --no-verify`; fix commit hook issues instead.

## Tests

- Avoid adding debug messages to assert calls.
- Do not write docstrings in tests.
- When using `unittest.mock`, always use `patch.object` with `autospec=True`
  instead of `patch`.
- **Never filter results or diagnostics in test assertions.** Always assert on
  the complete set of diagnostics returned. Do not use list comprehensions to
  filter by type or by file and then assert on the filtered list — assert
  directly on the full list.
- **Never break one line of Define source code across two Python lines**, even
  if it creates a very long Python string.

## Bazel

The project uses Bazel 9 (via bazelisk) with Bzlmod. WORKSPACE is not used.

### BUILD File Management

BUILD files are maintained entirely by hand — do not use gazelle or any other
BUILD file generator.

- **One rule per source file.** Each `.py`, `.go`, or `.proto` file gets exactly
  one build rule (`py_library`, `py_test`, `py_binary`, `go_library`, etc.).
- **Naming convention:** The target name matches the source file's basename
  without extension:
  - `parser.py` → `name = "parser"`
  - `parser_test.py` → `name = "parser_test"`
  - `__init__.py` → name the target after the package directory (e.g.,
    `define/compiler/__init__.py` → `name = "compiler"`)
  - `go_library` for a single `.go` file is named `<dir>_lib` when a `go_binary`
    in the same package embeds it, or just `<dir>` otherwise. `go_test` is named
    `<dir>_test`. `go_binary` is named after the directory.
  - `proto_library` rules are named `{proto_name}_proto`.
  - `py_proto_library` rules are named `{proto_library_name}_py` (do not add
    `_pb2`).
- **Keep targets atomic:** each target lists only its own source file in `srcs`
  and only its direct dependencies in `deps`.
- **Visibility:** Use the narrowest visibility that works. Omit `visibility` for
  package-private targets; use `//pkg:__subpackages__` when needed by sibling
  packages; use `//visibility:public` only for true public APIs.
- **Target order:** Keep normal rule targets (e.g. `py_library`, `py_test`,
  `py_binary`, `go_library`, etc.) in alphabetical order by target name. This
  includes test targets that test specific files (like `parser_test` for
  `parser.py`) — these should be alphabetized together with their corresponding
  source targets so you can see them side-by-side. Language-specific proto
  targets (e.g. `py_proto_library`) go immediately after their `proto_library`,
  not in a separate section. Only special meta-test targets like `format_test`
  and `pyright_test` should be grouped in separate sections and need not be
  alphabetized with the normal rules.

### Building and Testing

- Build all targets: `bazelisk build --noshow_progress //...`
- Test all targets: `bazelisk test --noshow_progress //...`
- Run coverage:
  `bazelisk coverage --noshow_progress //... --combined_report=lcov --instrumentation_filter='^//(define|defcl|tools)[/:]'`
- Always run the full test suite (`bazelisk test --noshow_progress //...`) when
  done working, to make sure nothing is broken.
- Run coverage after writing a lot of tests.
- **When adding a new test target** (e.g. `py_test`, `go_test`, `native_test`),
  always set `size = "small"`.
- After changing the code generator or any codegen testdata, regenerate expected
  outputs: `bazelisk run --noshow_progress //tools:regenerate_codegen_testdata`

### Python Dependencies

- All Python dependencies are managed via `aspect_rules_py`'s uv extension with
  a single `pypi` hub backed by the root `uv.lock`.
- Dependencies are in `pyproject.toml`. The `tools/` directory has its own
  `pyproject.toml` file.
- To regenerate or update the uv lock file:
  `bazelisk run --noshow_progress //:update_lock`
- Reference Python dependencies in BUILD files as `@pypi//package_name`.

### Basedpyright Type-Checking

- Each source directory (`compiler`, `defcl/python`, `tools`) has a
  `pyright_test` target that type-checks all Python sources in that directory.
- **When adding a new `py_library`, `py_binary`, or `py_test` target**, you must
  also add it to the `deps` of the `pyright_test` in the same BUILD file (or the
  parent package's `pyright_test` for sub-packages under `defcl/python`).

### Python Format Checking

- Every BUILD file that contains Python targets must also have a `format_test`
  target that checks formatting of all Python sources in that package.
- **When creating a new BUILD file with Python targets**, add:
  ```starlark
  load("//tools/bzl:format.bzl", "format_test")
  format_test(
      name = "format_test",
      srcs = glob(["*.py"]),
      python = "@multitool//tools/ruff",
  )
  ```

### Keeping Dependencies Up to Date

- Run `uv run tools/update_toolchains.py` to update Go SDK version, buf
  toolchain (version + SHA256), node version, and multitool (ruff, uv).
