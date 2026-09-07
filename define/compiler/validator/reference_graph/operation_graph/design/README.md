# Operation Graph Design

This directory contains design documents and reference artifacts for the
operation graph.

[Particle Operation Dependencies](dependency_rules.md) explains the requirements
behind the rules, position setters and readers, and the distinction between
Vacate and Vanish.

## Reference Implementation of the Graph Algorithm

[algorithm.py](algorithm.py) is a reference implementation of Collection and
Comparison; [graph.py](graph.py) provides dependency storage and reachability
queries. These files are not used by the compiler. The language specification
remains authoritative.

The [research archive] preserves the full historical research behind the
reference implementation.

[research archive]:
  https://github.com/define-lang/research/operation_graph_optimization
