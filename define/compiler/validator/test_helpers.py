# pyright: reportUnusedCallResult=false
"""Shared validator test helpers."""

from pathlib import Path
from pprint import pformat

from define.compiler.graphs import action_call_graph
from define.compiler.validator import validation_result


def assert_action_calls(
    call_graph: action_call_graph.ActionCallGraph, *actions: str
) -> None:
    """Assert that the given action call chain exists in the call graph."""
    __tracebackhide__ = True
    assert len(actions) >= 2, "Need at least two actions to form a call chain"
    # We use edges() (not unique_edges()) so that the error message
    # displays edges in graph insertion order, making failures easier
    # to diagnose.
    all_edges = [(e.source, e.target) for e in call_graph.edges()]
    edge_set = set(all_edges)
    for i in range(len(actions) - 1):
        expected = (actions[i], actions[i + 1])
        assert expected in edge_set, (
            f"Expected edge {actions[i]} -> {actions[i + 1]} "
            f"not found in action_call_graph.\n"
            f"Available edges:\n{pformat(all_edges)}"
        )


def assert_no_errors(result: validation_result.ProgramValidationResult) -> None:
    """Assert that a validation result has no exceptions or diagnostics."""
    __tracebackhide__ = True
    exceptions = result.all_exceptions
    assert not exceptions, (
        f"Expected no exceptions, but got {len(exceptions)}:\n"
        + "\n".join(f"  {type(e).__name__}: {e}" for e in exceptions)
    )
    all_diagnostics = result.all_diagnostics
    assert not all_diagnostics, (
        f"Expected no diagnostics, but got {len(all_diagnostics)}:\n"
        + "\n".join(f"  {pformat(d)}" for d in all_diagnostics)
    )


def write_project_config(tmp_path: Path, universe_name: str) -> None:
    """Write a .define/project/config.defcl file under tmp_path."""
    config_dir = tmp_path / ".define" / "project"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.defcl").write_text(
        f'project: {{\n  universe_name: "{universe_name}"\n}}\n',
        encoding="utf-8",
    )


def write_sub_root(tmp_path: Path, sub_root_rel_path: str, universe_name: str) -> None:
    """Create a sub-root directory with a project config."""
    sub_root = tmp_path / sub_root_rel_path
    write_project_config(sub_root, universe_name)


def write_local_deps_config(tmp_path: Path, deps: dict[str, str]) -> None:
    """Write a .define/deps/local.defcl file under tmp_path."""
    deps_dir = tmp_path / ".define" / "deps"
    deps_dir.mkdir(parents=True, exist_ok=True)
    entries = ",\n    ".join(
        f'{{\n      universe_name: "{name}"\n      path: "{path}"\n    }}'
        for name, path in deps.items()
    )
    content = (
        f"deps: {{\n  local: [\n    {entries}\n  ]\n}}\n" if deps else "deps: {}\n"
    )
    (deps_dir / "local.defcl").write_text(content, encoding="utf-8")
