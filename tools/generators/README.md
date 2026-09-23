# Compiler scaling inputs

Use this index to choose a generator, then consult its `--help` for sizing
flags:

```sh
bazelisk run //tools/generators:generate_action_graph_source -- --help
```

Source generators take `--output FILE`. The reference-project generator takes
`--output NEW_DIRECTORY`; compile its `test.dfn` entry file.

| Generator                                                                         | Use for                                                                                                                                               |
| --------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| [generate_action_graph_source](generate_action_graph_source.py)                   | Deep or wide action call graphs, shared calls, bottlenecks, and destructor cascades.                                                                  |
| [generate_deep_pipeline_source](generate_deep_pipeline_source.py)                 | Requirement propagation through deep calls; `--violate-requirements` adds diagnostic histories.                                                       |
| [generate_destruction_contracts_source](generate_destruction_contracts_source.py) | Destruction-time state across repeated callers, with shared or disjoint child names.                                                                  |
| [generate_particle_operations_source](generate_particle_operations_source.py)     | Deep and wide particle state, move chains, independent moves, and repeated triggers.                                                                  |
| [generate_pending_guarantees_source](generate_pending_guarantees_source.py)       | Nonempty pending Action Guarantee maps during explicit or automatic destruction; independently scale pending and destroyed particles.                 |
| [generate_quality_implications_source](generate_quality_implications_source.py)   | Deep or shared Quality Implications and repeated assignments. Width and fan-out of two give exponentially many paths through linearly many qualities. |
| [generate_action_codegen_source](generate_action_codegen_source.py)               | Code generation for many actions, substantial action bodies, and wide destruction.                                                                    |
| [generate_large_define_source](generate_large_define_source.py)                   | Large source blocks and long chained names; `--malformed-eof` adds a late parse failure.                                                              |
| [generate_diagnostics_source](generate_diagnostics_source.py)                     | Many diagnostics, long diagnostic messages, and errors late in a file.                                                                                |
| [generate_reference_graph_project](generate_reference_graph_project.py)           | Many files, deep paths, dependency graphs, and configuration chains; select the graph with `--shape`.                                                 |

Reference-project shapes: `layered` (seeded random), `independent`, `chain`,
`fan-in`, `depth-updates`, `diamonds`, `bottlenecks`, `config-chain`, `cycles`,
and `missing`. The last two intentionally produce diagnostics. Random `layered`
projects can include unreachable files; deterministic shapes make every emitted
source file reachable.

Use one compiler worker with `depth-updates` to preserve the adversarial
reference insertion order. `--modules` includes the first position, which
references all others before their predecessor references force repeated depth
updates.

Indentation diagnostics from `generate_diagnostics_source --indent-width`
require parsing with a file path; validation without filesystem context omits
them.

Each generator has a matching `_test.py` checking small inputs and their shape.
Measure generation separately from compilation, and compare scaling against
actual source size and loaded definitions rather than flag values alone.
