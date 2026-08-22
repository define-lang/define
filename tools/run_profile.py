"""Public command-line entry point for compiler profiling orchestration."""

from __future__ import annotations

from tools import profile_orchestration

# PRF-012: Orchestration boundary. PRF-020: Machine and human interfaces.
profile_orchestration.chdir_to_build_workspace()
profile_orchestration.main()
