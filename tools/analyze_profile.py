"""Public command-line entry point for profiler analysis."""

from tools.profiler import analyzer

# PRF-020: Machine and human interfaces. PRF-043: Analyzer at every checkpoint.
analyzer.main()
