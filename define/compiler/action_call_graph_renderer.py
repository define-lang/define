"""Renders an ActionCallGraph into a human-readable format."""

from __future__ import annotations

import re
import typing

if typing.TYPE_CHECKING:
    from define.compiler import action_call_graph


_INVALID_ID_CHARS = re.compile(r"[^A-Za-z0-9_]")


def _sanitize_id(name: str) -> str:
    """Replace Mermaid-invalid identifier characters with underscores."""
    return _INVALID_ID_CHARS.sub("_", name)


# TODO: Hook this renderer into a CLI.
class Mermaid:
    """Renders an ActionCallGraph as Mermaid diagrams."""

    _graph: action_call_graph.ActionCallGraph

    def __init__(self, graph: action_call_graph.ActionCallGraph):
        """Create a Mermaid renderer for the given call graph."""
        self._graph = graph

    def render_flowchart(self) -> str:
        """Produce a Mermaid ``flowchart LR`` flowchart from the call graph."""
        unique_edges = self._graph.unique_edges()

        if not unique_edges:
            return "flowchart LR\n"

        nodes: set[str] = set()
        for source, target in unique_edges:
            nodes.add(source)
            nodes.add(target)

        lines = ["flowchart LR"]
        for name in sorted(nodes):
            node_id = _sanitize_id(name)
            if name.startswith("position<"):
                lines.append(f'    {node_id}(["{name}"])')
            else:
                lines.append(f'    {node_id}["{name}"]')
        for source, target in sorted(unique_edges):
            lines.append(f"    {_sanitize_id(source)} --> {_sanitize_id(target)}")
        lines.append("")
        return "\n".join(lines)
