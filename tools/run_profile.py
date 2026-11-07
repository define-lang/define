"""Public command-line entry point for compiler profiling orchestration."""

from __future__ import annotations

from tools import profile_orchestration

profile_orchestration.chdir_to_build_workspace()
profile_orchestration.main()
