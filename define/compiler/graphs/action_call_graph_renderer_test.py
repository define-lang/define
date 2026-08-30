# pyright: reportUnusedCallResult=false
from __future__ import annotations

import os
import subprocess
from pathlib import Path, PurePosixPath

import pytest

from define.compiler.graphs import action_call_graph, action_call_graph_renderer
from define.compiler.validator import test_helpers
from define.compiler.validator.reference_graph import reference_graph_validator
from define.compiler.validator.structural import program_validator


def _validate_mermaid(text: str):
    validator = os.environ.get("MERMAID_VALIDATOR")
    if not validator:
        pytest.skip("Mermaid validation requires its Bazel data dependency")
    validator_path = _resolve_runfile_path(validator)
    result = subprocess.run(
        [str(validator_path)],
        input=text,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"Invalid Mermaid syntax:\n{result.stderr}"


def _resolve_runfile_path(path: str) -> Path:
    candidate = Path(path)
    # Direct pytest runs use a filesystem path instead of a Bazel runfiles key.
    if candidate.exists():  # pragma: no branch
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
    *,
    expect_errors: bool = False,
) -> action_call_graph.ActionCallGraph:
    pv = program_validator.ProgramStructuralValidator()
    test_helpers.write_project_config(tmp_path, universe_name)
    for name, source in files.items():
        file_path = tmp_path / name
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(source, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    entry_point = PurePosixPath(next(iter(files)))
    program_result = pv.validate_program(entry_point)
    reference_graph_result = reference_graph_validator.ReferenceGraphValidator(
        program_result.reference_graph,
        program_result.definition_results,
    ).validate()
    if not expect_errors:
        test_helpers.assert_no_errors(program_result)
    return reference_graph_result.action_call_graph


_ACTION_A = (
    "define the potential action<my.domain.com:my_lib:/act_a> {\n"
    "    it happens when {\n"
    "        this particle is created.\n"
    "    } and it does {\n"
    "        define the position<gateway> {\n"
    "            it may only contain particles where {\n"
    "                it has the action</act_b>.\n"
    "            }\n"
    "        }\n"
    "        create a particle in position<gateway>.\n"
    "        create a particle in position<gateway>::action</act_b>::position<pp>.\n"
    "    }\n"
    "}\n"
)

_ACTION_B_TRIGGERED = (
    "define the potential action<my.domain.com:my_lib:/act_b> {\n"
    "    define the position<pp>.\n"
    "    it happens when {\n"
    "        the position<pp> has a particle.\n"
    "    } and it does {\n"
    "        define the position<do_nothing>.\n"
    "        create a particle in position<do_nothing>.\n"
    "        destroy the particle in position<pp>.\n"
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
                "act_a.dfn": _ACTION_A,
                "act_b.dfn": _ACTION_B_TRIGGERED,
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
            "    it happens when {\n"
            "        this particle is created.\n"
            "    } and it does {\n"
            "        define the position<gateway> {\n"
            "            it may only contain particles where {\n"
            "                it has the action</act_b>.\n"
            "            }\n"
            "        }\n"
            "        create a particle in position<gateway>.\n"
            "        create a particle in position<gateway>::action</act_b>::position<pp>.\n"
            "        create a particle in position<gateway>::action</act_b>::position<pp>.\n"
            "    }\n"
            "}\n"
        )
        graph = _build_graph(
            {
                "act_a.dfn": source_a,
                "act_b.dfn": _ACTION_B_TRIGGERED,
            },
            tmp_path,
            monkeypatch,
            expect_errors=True,
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
            "        the position<pp> has a particle.\n"
            "    } and it does {\n"
            "        define the position<gateway> {\n"
            "            it may only contain particles where {\n"
            "                it has the action</act_c>.\n"
            "            }\n"
            "        }\n"
            "        create a particle in position<gateway>.\n"
            "        create a particle in position<gateway>::action</act_c>::position<pp>.\n"
            "        destroy the particle in position<pp>.\n"
            "    }\n"
            "}\n"
        )
        action_c = (
            "define the potential action<my.domain.com:my_lib:/act_c> {\n"
            "    define the position<pp>.\n"
            "    it happens when {\n"
            "        the position<pp> has a particle.\n"
            "    } and it does {\n"
            "        define the position<placeholder>.\n"
            "        create a particle in position<placeholder>.\n"
            "        destroy the particle in position<pp>.\n"
            "    }\n"
            "}\n"
        )
        graph = _build_graph(
            {
                "act_a.dfn": _ACTION_A,
                "act_b.dfn": action_b_chains,
                "act_c.dfn": action_c,
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
            "    it happens when {\n"
            "        this particle is created.\n"
            "    } and it does {\n"
            "        define the position<gateway> {\n"
            "            it may only contain particles where {\n"
            "                it has the action</bar>.\n"
            "            }\n"
            "        }\n"
            "        create a particle in position<gateway>.\n"
            "        create a particle in position<gateway>::action</bar>::position<pp>.\n"
            "    }\n"
            "}\n"
        )
        source_bar = (
            "define the potential action<test.org:other_lib:/bar> {\n"
            "    define the position<pp>.\n"
            "    it happens when {\n"
            "        the position<pp> has a particle.\n"
            "    } and it does {\n"
            "        define the position<placeholder>.\n"
            "        create a particle in position<placeholder>.\n"
            "        destroy the particle in position<pp>.\n"
            "    }\n"
            "}\n"
        )
        graph = _build_graph(
            {
                "foo.dfn": source_foo,
                "bar.dfn": source_bar,
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
