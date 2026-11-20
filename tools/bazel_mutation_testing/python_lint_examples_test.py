from __future__ import annotations

import functools
import json
import operator
import os
import pathlib
import subprocess
import sys
from typing import TYPE_CHECKING, NamedTuple, cast

import pytest

from tools import runfiles
from tools.bazel_mutation_testing import diagnostics, lint_flags

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

# Each example starts with what rejects it under the repository's lints and in
# mutation runs, such as "# Rejected: ruff:F841" and "# Rejected in mutation
# runs: nothing".
_REPOSITORY = "# Rejected: "
_MUTATION_RUN = "# Rejected in mutation runs: "
_EXAMPLES = sorted(
    runfiles.resolve(location)
    for location in os.environ["PYTHON_LINT_EXAMPLES"].split()
)
_EXAMPLE_PARAMETERS = [pytest.param(example, id=example.stem) for example in _EXAMPLES]
_TURNED_OFF = lint_flags.load().turned_off
# The repository turns these rules off for every file under tools, so no
# example can show what they reject.
_WITHOUT_EXAMPLES = frozenset({"ruff:T201"})
_PYPROJECT = runfiles.resolve_from_env("PYPROJECT")
# The directory that the repository's configurations name paths from.
_WORKSPACE = _PYPROJECT.parent

# What rejects each example, by the example's file name.
type _Rejections = dict[str, frozenset[str]]


class _Tool(NamedTuple):
    """How to read a lint tool's report of every example."""

    file_of: Callable[[dict[str, object]], object]
    """Return the path of the example that a reported JSON line is about."""
    read: Callable[[str], frozenset[str]]
    """Return what one example's reported lines reject it for."""


def _pyright_file(reported: dict[str, object]) -> object:
    return cast("dict[str, object]", reported["pyright"])["file"]


_RUFF = _Tool(
    operator.itemgetter("filename"),
    functools.partial(diagnostics.action_rejections, "Ruff"),
)
_AST_GREP = _Tool(
    operator.itemgetter("file"),
    functools.partial(diagnostics.action_rejections, "AstGrep"),
)
_PYRIGHT = _Tool(_pyright_file, diagnostics.test_rejections)


def _expected(line: str, prefix: str) -> frozenset[str]:
    assert line.startswith(prefix)
    names = line.removeprefix(prefix)
    return frozenset() if names == "nothing" else frozenset(names.split(", "))


def _header(example: pathlib.Path) -> list[str]:
    return example.read_text(encoding="utf-8").splitlines()[:2]


def _by_example(tool: _Tool, report: str) -> _Rejections:
    """Return what `tool`'s JSON lines `report` reject each example for."""
    lines: dict[str, list[str]] = {}
    for line in report.splitlines():
        if line.startswith("{"):
            reported = cast("dict[str, object]", json.loads(line))
            name = pathlib.Path(cast("str", tool.file_of(reported))).name
            lines.setdefault(name, []).append(line)
    return {name: tool.read("\n".join(found)) for name, found in lines.items()}


def _run(command: list[str | pathlib.Path]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command, cwd=_WORKSPACE, capture_output=True, text=True, check=False
    )


def _checked(
    tool: _Tool, completed: subprocess.CompletedProcess[str], report: str
) -> _Rejections:
    found = _by_example(tool, report)
    # A tool that fails while reporting nothing must not pass the examples that
    # expect nothing.
    assert (completed.returncode == 0) == (not found), completed.stderr
    return found


def _paths() -> list[str | pathlib.Path]:
    return [example.relative_to(_WORKSPACE) for example in _EXAMPLES]


def _ruff(turned_off: Iterable[str]) -> _Rejections:
    command: list[str | pathlib.Path] = [
        runfiles.resolve_from_env("RUFF"),
        "check",
        f"--config={_PYPROJECT}",
        "--quiet",
        "--output-format=json-lines",
        *_paths(),
    ]
    if turned_off:
        command.append(f"--ignore={','.join(sorted(turned_off))}")
    completed = _run(command)
    return _checked(_RUFF, completed, completed.stdout)


def _ast_grep(turned_off: Iterable[str]) -> _Rejections:
    completed = _run(
        [
            runfiles.resolve_from_env("AST_GREP"),
            "scan",
            f"--config={runfiles.resolve_from_env('SGCONFIG')}",
            "--json=stream",
            *[f"--off={rule}" for rule in sorted(turned_off)],
            *_paths(),
        ]
    )
    return _checked(_AST_GREP, completed, completed.stdout)


def _pyright_lines(output: str) -> str:
    # pyright_test prints each error and warning of basedpyright's JSON output
    # this way.
    found = cast("list[dict[str, object]]", json.loads(output)["generalDiagnostics"])
    return "".join(
        f"{json.dumps({'pyright': diagnostic})}\n"
        for diagnostic in found
        if diagnostic["severity"] in {"error", "warning"}
    )


def _pyright(turned_off: Iterable[str], directory: pathlib.Path) -> _Rejections:
    # As in pyright_test, a stand-in venv gives basedpyright this test's import
    # paths without starting an interpreter.
    site_packages = directory / "venv/lib/site-packages"
    site_packages.mkdir(parents=True)
    _ = (site_packages / "import_paths.pth").write_text(
        "".join(f"{path}\n" for path in sys.path[1:]),
        encoding="utf-8",
        newline="\n",
    )
    config = directory / "pyrightconfig.json"
    _ = config.write_text(
        json.dumps(
            {
                "extends": str(_PYPROJECT),
                "include": [str(example) for example in _EXAMPLES],
                "extraPaths": [str(_WORKSPACE)],
                "venvPath": str(directory),
                "venv": "venv",
                **dict.fromkeys(turned_off, "none"),
            }
        ),
        encoding="utf-8",
        newline="\n",
    )
    completed = _run(
        [
            runfiles.resolve_from_env("BASEDPYRIGHT"),
            "--project",
            config,
            "--outputjson",
            "--pythonversion",
            f"{sys.version_info.major}.{sys.version_info.minor}",
        ]
    )
    return _checked(_PYRIGHT, completed, _pyright_lines(completed.stdout))


def _all_rejections(directory: pathlib.Path, *, mutation_run: bool) -> _Rejections:
    found: dict[str, set[str]] = {example.name: set() for example in _EXAMPLES}
    for tool_found in (
        _ruff(_TURNED_OFF.ruff if mutation_run else ()),
        _ast_grep(_TURNED_OFF.ast_grep if mutation_run else ()),
        _pyright(_TURNED_OFF.pyright if mutation_run else (), directory),
    ):
        for name, rejections in tool_found.items():
            found[name].update(rejections)
    return {name: frozenset(rejections) for name, rejections in found.items()}


@pytest.fixture(scope="module")
def repository_rejections(tmp_path_factory: pytest.TempPathFactory) -> _Rejections:
    return _all_rejections(tmp_path_factory.mktemp("repository"), mutation_run=False)


@pytest.fixture(scope="module")
def mutation_run_rejections(tmp_path_factory: pytest.TempPathFactory) -> _Rejections:
    return _all_rejections(tmp_path_factory.mktemp("mutation_run"), mutation_run=True)


@pytest.mark.parametrize("example", _EXAMPLE_PARAMETERS)
def test_repository_lints(example: pathlib.Path, repository_rejections: _Rejections):
    assert repository_rejections[example.name] == _expected(
        _header(example)[0], _REPOSITORY
    )


@pytest.mark.parametrize("example", _EXAMPLE_PARAMETERS)
def test_mutation_run_lints(
    example: pathlib.Path, mutation_run_rejections: _Rejections
):
    assert mutation_run_rejections[example.name] == _expected(
        _header(example)[1], _MUTATION_RUN
    )


def test_examples_cover_the_turned_off_rules():
    turned_off: set[str] = set()
    for example in _EXAMPLES:
        header = _header(example)
        turned_off.update(
            _expected(header[0], _REPOSITORY) - _expected(header[1], _MUTATION_RUN)
        )
    assert (
        turned_off
        == (
            {f"ruff:{rule}" for rule in _TURNED_OFF.ruff}
            | {f"ast-grep:{rule}" for rule in _TURNED_OFF.ast_grep}
            | {f"pyright:{rule}" for rule in _TURNED_OFF.pyright}
        )
        - _WITHOUT_EXAMPLES
    )
