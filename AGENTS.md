# Rules for Define Project

We are working together to make a new type of programming language that has
never existed before.

See [spec/spec.md] for the language specification.

## Python Execution

- Always use `uv` to run Python applications and scripts.
- Use `uv run` to execute Python code.
- Use `uv sync` to install dependencies.

## Formatting

- Formatting is done with `uv run ruff format`
- Format all code after making a change.
- Format all .md files with `prettier --write`
- Format all .proto files with `npx @bufbuild/buf format -w`
- Format all Bazel files (BUILD.bazel, .bzl, MODULE.bazel) with
  `npx @bazel/buildifier`

## Linting

- Linting runs when you run bazelisk build or test. Always lint files after
  editing them.
- Run `npx @bufbuild/buf lint defcl/schema` after making changes to .proto files
  in `defcl/schema`.
- Fix all linting errors that are reported.

## Imports

- Prefer importing modules instead of classes:. Example:
  `from compiler import ast` and then reference `ast.ASTNode` in the code.
- Never import or use `typing.TYPE_CHECKING`.
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

- Prefer positive booleans. For example: `enable_feature=False` rather than
  `disable_feature=True`.

## Tests

- Avoid adding debug messages to assert calls.
- Do not write docstrings in tests.
- Do not add `-> None` return type annotations to test methods.
- When using `unittest.mock`, always use `patch.object` with `autospec=True`
  instead of `patch`.

## Bazel

The project uses Bazel 9 (via bazelisk) with Bzlmod. WORKSPACE is not used.

### Building and Testing

- Build all targets: `bazelisk build //...`
- Test all targets: `bazelisk test //...`
- Keep build targets atomic — each target should contain only the minimum
  necessary sources and dependencies.
- **When adding a new test target** (e.g. `py_test`, `go_test`, `native_test`),
  always set `size = "small"`.

### Python Dependencies

- All Python dependencies are managed via `aspect_rules_py`'s uv extension with
  a single `pypi` hub backed by the root `uv.lock`.
- Dependencies are declared in per-package `pyproject.toml` files
  (`compiler/pyproject.toml`, `defcl/pyproject.toml`, `tools/pyproject.toml`).
- To regenerate `uv.lock` after changing any `pyproject.toml`: `uv lock`
- Reference dependencies in BUILD files as `@pypi//package_name`.

### Pyright Type-Checking

- Each source directory (`compiler`, `defcl/python`, `tools`) has a
  `pyright_test` target that type-checks all Python sources in that directory.
- **When adding a new `py_library`, `py_binary`, or `py_test` target**, you must
  also add it to the `deps` of the `pyright_test` in the same BUILD file (or the
  parent package's `pyright_test` for sub-packages under `defcl/python`).

### Format Checking

- Every BUILD file that contains Python targets must also have a `format_test`
  target that checks formatting of all Python sources in that package.
- **When creating a new BUILD file with Python targets**, add:
  ```starlark
  load("@aspect_rules_lint//format:defs.bzl", "format_test")
  format_test(
      name = "format_test",
      srcs = glob(["*.py"]),
      python = "@aspect_rules_lint//format:ruff",
  )
  ```

### Keeping Dependencies Up to Date

- Periodically check that all versions listed in `MODULE.bazel` are on the
  latest stable version.
- Periodically run `uv run pre-commit autoupdate`.
- Periodically force-upgrade all Python dependencies with `uv sync --upgrade`

### uv Workspace

- The root `pyproject.toml` declares a uv workspace with members `compiler`,
  `defcl`, and `tools`.
- `uv sync` still works for local development outside Bazel.
