# Operation Graph Design

This directory contains design documents and reference artifacts for the
operation graph.

[Particle Operation Dependencies](dependency_rules.md) explains the requirements
behind the rules, position setters and readers, and the distinction between
Vacate and Vanish.

## Reference Implementation of the Graph Algorithm

[algorithm.py](algorithm.py) calculates Create, Move, Vacate, and Vanish
dependencies, including early Vacate/Vanish combination and combination after
Comparison. [graph.py](graph.py) provides dependency storage and reachability
queries. These files are not used by the compiler. The language specification
remains authoritative.

### Inputs and use

For standalone use, add this directory's parent to `PYTHONPATH` and import
`design.algorithm`. The full compiler import path is unavailable because
`operation_graph.py` is a module, not a package. The reference files use only
the standard library and each other.

The input is valid, resolved Define code in Particle Operation Recency order.
Each `Operation` describes one Create, Move, or Vacate. Operation occurrences
are numbered from zero; a particle's identity is its Create occurrence. Position
identities distinguish the original particle's assigned positions from those of
a replacement particle.

| Field                | Meaning                                                                                                              |
| -------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `occupied`           | Intermediate positions in the actual Position References.                                                            |
| `fill`               | The Create's or Move's target position.                                                                              |
| `empty`              | The Move's source or the position emptied by Vacate.                                                                 |
| `quality_particles`  | Distinct particles whose assigned qualities the references use; their identities also identify the required Creates. |
| `defines`            | Positions defined by the newly created particle.                                                                     |
| `ordinary_occupants` | Particles required as intermediate occupants without using occupancy preserved for destructors.                      |
| `moved`              | The directly moved particle, excluding transitive movement.                                                          |
| `vacated`            | The original particle selected by this Vacate.                                                                       |

Repeated accesses to a position are combined in the input. Fields that do not
apply have their empty or `None` defaults. Transitive child Vacates do not
acquire Position References through their displayed names.

`classify(operations)` examines the complete input and returns the particle
identities that still need lifetime analysis. Pass that set to `Calculator`.
Source analysis may supply an equivalent conservative set instead: omitted
particles must satisfy the specification's early-combination condition across
all operations, including future triggered actions. An empty set is not a
request to discover that condition incrementally.

Call `add(operation)` for each occurrence. Before processing selected Vacates,
use `retain({ordinary: retained, ...})` to preserve position information needed
by destructors. All destructors using the same original position share the same
retained identity and its subsequent changes. These identifiers distinguish
dependency information, not different physical positions. `simultaneous(...)`
accepts the selected Vacates without adding ordering between them. `forget(...)`
releases position records once source analysis proves there are no future uses.

After all occurrences have been processed, call `finish()` once. It completes
the Vanish calculation and returns a particle-to-operation mapping. A combined
Vanish maps to its Vacate occurrence; an uncombined Vanish maps to a new
occurrence. Particles not selected for Vacation have no entry. Do not add more
operations after finalization.

The result is `calculator.graph`. `dependencies(occurrence)` reads direct
dependencies; `reaches(following, previous)` tests strict dependency
reachability throughout the completed graph. Separate Vanishes have no
dependents, so their edges are stored without reverse-index entries.
Construction uses `reaches_indexed` only for Create, Move, and Vacate
candidates.

This reference implementation does not parse source, resolve actions, or choose
an ordering between conflicting destructor operations. Those are inputs to the
whole-program calculation, not substitutes for the compiler's modular design.

The [research archive] preserves the full historical research behind the
reference implementation.

[research archive]:
  https://github.com/define-lang/research/operation_graph_optimization
