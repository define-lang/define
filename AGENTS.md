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

## Linting

- Linting must be done with both `uv run pyright` and `uv run ruff check`.
- Always run both linters after making a to Python files:
  - `uv run pyright` for type checking
  - `uv run ruff check` for code quality checks
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
- When using `unittest.mock`, always use `patch.object` with `autospec=True`
  instead of `patch`.
