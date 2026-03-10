# pyright: reportUnusedCallResult=false
import os
import subprocess
from pathlib import Path, PurePosixPath

import pytest

from define.compiler import action_call_graph, action_call_graph_renderer
from define.compiler.validator import program_validator


def _write_project_config(tmp_path: Path, universe_name: str):
    config_dir = tmp_path / ".define" / "project"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.defcl").write_text(
        f'project: {{\n  universe_name: "{universe_name}"\n}}\n',
        encoding="utf-8",
    )


def _validate_mermaid(text: str):
    validator = os.environ.get("MERMAID_VALIDATOR")
    if not validator:
        return
    validator_path = _resolve_runfile_path(validator)
    result = subprocess.run(
        [str(validator_path)],
        input=text,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Invalid Mermaid syntax:\n{result.stderr}"


def _resolve_runfile_path(path: str) -> Path:
    candidate = Path(path)
    if candidate.exists():
        return candidate

    if os.environ.get("RUNFILES_DIR") or os.environ.get("RUNFILES_MANIFEST_FILE"):
        from python.runfiles import Runfiles  # pyright: ignore[reportMissingTypeStubs]

        runfiles = Runfiles.Create()
        assert runfiles is not None
        resolved_path = runfiles.Rlocation(path)
        assert resolved_path is not None
        return Path(resolved_path)

    raise FileNotFoundError(f"Could not resolve runfile path: {path}")


def _build_graph(
    files: dict[str, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    universe_name: str = "my.domain.com:my_lib",
) -> action_call_graph.ActionCallGraph:
    pv = program_validator.ProgramValidator()
    _write_project_config(tmp_path, universe_name)
    for name, source in files.items():
        file_path = tmp_path / name
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(source, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    entry_point = PurePosixPath(next(iter(files)))
    results = pv.validate_program(entry_point)
    assert all(result.exception is None for result in results)
    assert all(not result.diagnostics for result in results)
    return pv.action_call_graph


_ACTION_A = (
    "define the potential action<my.domain.com:my_lib:/act_a> {\n"
    "    define the position<pp>.\n"
    "    it happens when {\n"
    "        the position<pp> has a dimension point.\n"
    "    } and it does {\n"
    "        create a dimension point in action</act_b>::position<pp>.\n"
    "    }\n"
    "}\n"
)

_ACTION_B_TRIGGERED = (
    "define the potential action<my.domain.com:my_lib:/act_b> {\n"
    "    define the position<pp>.\n"
    "    define the position<do_nothing>.\n"
    "    it happens when {\n"
    "        the position<pp> has a dimension point.\n"
    "    } and it does {\n"
    "        define the position<placeholder>.\n"
    "        create a dimension point in position<placeholder>.\n"
    "    }\n"
    "}\n"
)


_POS_COLOR_SOURCE = (
    "define the potential position<my.domain.com:my_lib:/color> {\n"
    "    after it is assigned {\n"
    "        create a dimension point in action</act_b>::position<pp>.\n"
    "    }\n"
    "}\n"
)


class TestRenderMermaid:
    def test_empty_graph(self):
        graph = action_call_graph.ActionCallGraph()
        result = action_call_graph_renderer.Mermaid(graph).render_flowchart()
        assert result == "flowchart LR\n"

    def test_single_edge(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        graph = _build_graph(
            {
                "act_a.def": _ACTION_A,
                "act_b.def": _ACTION_B_TRIGGERED,
            },
            tmp_path,
            monkeypatch,
        )

        result = action_call_graph_renderer.Mermaid(graph).render_flowchart()
        assert result == (
            "flowchart LR\n"
            '    action_my_domain_com_my_lib__act_a_["action<my.domain.com:my_lib:/act_a>"]\n'
            '    action_my_domain_com_my_lib__act_b_["action<my.domain.com:my_lib:/act_b>"]\n'
            "    action_my_domain_com_my_lib__act_a_ --> action_my_domain_com_my_lib__act_b_\n"
        )
        _validate_mermaid(result)

    def test_duplicate_edges_deduplicated(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        source_a = (
            "define the potential action<my.domain.com:my_lib:/act_a> {\n"
            "    define the position<pp>.\n"
            "    it happens when {\n"
            "        the position<pp> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in action</act_b>::position<pp>.\n"
            "        create a dimension point in action</act_b>::position<pp>.\n"
            "    }\n"
            "}\n"
        )
        graph = _build_graph(
            {
                "act_a.def": source_a,
                "act_b.def": _ACTION_B_TRIGGERED,
            },
            tmp_path,
            monkeypatch,
        )

        result = action_call_graph_renderer.Mermaid(graph).render_flowchart()
        assert result == (
            "flowchart LR\n"
            '    action_my_domain_com_my_lib__act_a_["action<my.domain.com:my_lib:/act_a>"]\n'
            '    action_my_domain_com_my_lib__act_b_["action<my.domain.com:my_lib:/act_b>"]\n'
            "    action_my_domain_com_my_lib__act_a_ --> action_my_domain_com_my_lib__act_b_\n"
        )
        _validate_mermaid(result)

    def test_multiple_distinct_edges(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        action_b_chains = (
            "define the potential action<my.domain.com:my_lib:/act_b> {\n"
            "    define the position<pp>.\n"
            "    it happens when {\n"
            "        the position<pp> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in action</act_c>::position<pp>.\n"
            "    }\n"
            "}\n"
        )
        action_c = (
            "define the potential action<my.domain.com:my_lib:/act_c> {\n"
            "    define the position<pp>.\n"
            "    it happens when {\n"
            "        the position<pp> has a dimension point.\n"
            "    } and it does {\n"
            "        define the position<placeholder>.\n"
            "        create a dimension point in position<placeholder>.\n"
            "    }\n"
            "}\n"
        )
        graph = _build_graph(
            {
                "act_a.def": _ACTION_A,
                "act_b.def": action_b_chains,
                "act_c.def": action_c,
            },
            tmp_path,
            monkeypatch,
        )

        result = action_call_graph_renderer.Mermaid(graph).render_flowchart()
        assert result == (
            "flowchart LR\n"
            '    action_my_domain_com_my_lib__act_a_["action<my.domain.com:my_lib:/act_a>"]\n'
            '    action_my_domain_com_my_lib__act_b_["action<my.domain.com:my_lib:/act_b>"]\n'
            '    action_my_domain_com_my_lib__act_c_["action<my.domain.com:my_lib:/act_c>"]\n'
            "    action_my_domain_com_my_lib__act_a_ --> action_my_domain_com_my_lib__act_b_\n"
            "    action_my_domain_com_my_lib__act_b_ --> action_my_domain_com_my_lib__act_c_\n"
        )
        _validate_mermaid(result)

    def test_node_ids_sanitized(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        source_foo = (
            "define the potential action<test.org:other_lib:/foo> {\n"
            "    define the position<pp>.\n"
            "    it happens when {\n"
            "        the position<pp> has a dimension point.\n"
            "    } and it does {\n"
            "        create a dimension point in action</bar>::position<pp>.\n"
            "    }\n"
            "}\n"
        )
        source_bar = (
            "define the potential action<test.org:other_lib:/bar> {\n"
            "    define the position<pp>.\n"
            "    it happens when {\n"
            "        the position<pp> has a dimension point.\n"
            "    } and it does {\n"
            "        define the position<placeholder>.\n"
            "        create a dimension point in position<placeholder>.\n"
            "    }\n"
            "}\n"
        )
        graph = _build_graph(
            {
                "foo.def": source_foo,
                "bar.def": source_bar,
            },
            tmp_path,
            monkeypatch,
            universe_name="test.org:other_lib",
        )

        result = action_call_graph_renderer.Mermaid(graph).render_flowchart()
        assert result == (
            "flowchart LR\n"
            '    action_test_org_other_lib__bar_["action<test.org:other_lib:/bar>"]\n'
            '    action_test_org_other_lib__foo_["action<test.org:other_lib:/foo>"]\n'
            "    action_test_org_other_lib__foo_ --> action_test_org_other_lib__bar_\n"
        )
        _validate_mermaid(result)

    def test_position_init_source_renders_different_shape(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        graph = _build_graph(
            {
                "color.def": _POS_COLOR_SOURCE,
                "act_b.def": _ACTION_B_TRIGGERED,
            },
            tmp_path,
            monkeypatch,
        )

        result = action_call_graph_renderer.Mermaid(graph).render_flowchart()
        assert result == (
            "flowchart LR\n"
            '    action_my_domain_com_my_lib__act_b_["action<my.domain.com:my_lib:/act_b>"]\n'
            '    position_my_domain_com_my_lib__color_(["position<my.domain.com:my_lib:/color>"])\n'
            "    position_my_domain_com_my_lib__color_ --> action_my_domain_com_my_lib__act_b_\n"
        )
        _validate_mermaid(result)
