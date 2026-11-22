# Boolean Logic in the Compiler

How the compiler represents boolean logic, checks the rules of DLP 56 (Logical
Operations for Boolean Values), DLP 59 (No Redundant Boolean Values), DLP 60
(One Order for Boolean Logic), and DLP 61 (Registered Boolean Operations), fixes
programs until they follow those rules, and structures Value Operation and
Action contracts for parallel compilation and future whole-program optimization.

The proposals define what programs may write. This document specifies how the
compiler performs the work. [The Algorithm](#the-algorithm) describes the
compiler architecture and limits.
[Measurements and Reasons](#measurements-and-reasons) gives the empirical data
behind each choice. [Approaches That Didn't Work](#approaches-that-didnt-work)
records rejected alternatives.
[Appendix: Parallel Compilation, Contracts, and Whole-Program Action Optimization](#appendix-parallel-compilation-contracts-and-whole-program-action-optimization)
covers modular contract design across Value Operations and Actions.

The background research is in
[Representations of Boolean Logic](../define/proposals/background/boolean-logic-representations.md),
and the reference implementation, Lean 4 termination proof, and measurements are
in the research repository's
[boolean_equality_checking](https://github.com/define-lang/research/tree/main/boolean_equality_checking)
directory. Real-code measurements come from the boolean logic of eleven
open-source codebases in the same repository's
[boolean_logic_in_real_code](https://github.com/define-lang/research/tree/main/boolean_logic_in_real_code)
study (3,265 extracted units: 376 standalone functions at `scope=1` and 2,889
inlined units at `scope=2`).

## The Algorithm

### Limits and Forward Compatibility

The compiler enforces five deterministic, compiler-independent limits on boolean
logic. Together they bound contract size, per-worker memory in parallel builds,
exponential BDD growth, and polynomial match search — with no machine-dependent
timeouts and no heuristic step budget. Raising any of these limits in a future
version of Define only accepts more programs, preserving Forward Compatibility:

| Limit                                       | Scope                                                           | Value                    | What it bounds                                                                                                                                                                                             |
| ------------------------------------------- | --------------------------------------------------------------- | ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Boolean input Interface Views**           | Every Value Operation                                           | **≤ 20**                 | Bounds every pure boolean Value Operation's exported contract to **≤ 128 KB** (truth table) or **≤ 98,302** ROBDD nodes, and limits DLP 60 symmetry checking to at most 190 view pairs.                    |
| **Registered operation read views (arity)** | Registered boolean ops (`booleans.defcl`)                       | **≤ 3**                  | Bounds `Matcher` search to `O(S * (I + S)^2)` and at most 6 view permutations per op, and enables exact `fewest_ands` via the 14-class 3-variable NPN table.                                               |
| **Registered boolean operations**           | Each project's `booleans.defcl`                                 | **≤ 16** _(plus stdlib)_ | Bounds the number of registered operations `Matcher` checks against every Value Operation and Action in the project.                                                                                       |
| **Boolean statements**                      | Every Value Operation and Action                                | **≤ 256**                | Keeps `Matcher` fast even on adversarial non-matching chains; ensures every pure boolean Value Operation fits unconditionally inside the `(256 statements, 20 inputs)` truth-table floor.                  |
| **Boolean inputs**                          | Every Value Operation and Action                                | **≤ 512**                | Bounds the `Matcher` value pool (`N = I + S ≤ 768`) on mixed Value Operations and Actions with many non-boolean comparisons (`x == 1`, `x < y`, etc.), keeping worst-case `Matcher` runtime around ~0.1 s. |
| **Canonical shared ROBDD reachable nodes**  | Mixed Value Operations and Actions with `21–512` boolean inputs | **≤ 65,536 (`2^16`)**    | Prevents exponential `O(2^I)` blowups past 20 inputs; bounds worst-case memory to **~5–10 MB per parallel worker** and build time to **~5–20 ms**.                                                         |

Two consequences follow directly from these limits:

- **Every pure boolean Value Operation always compiles through the guaranteed
  truth-table floor.** Because a pure boolean Value Operation has at most 20
  boolean input Interface Views (its only boolean inputs) and at most 256
  boolean statements, it can never hit an ROBDD limit, regardless of how tangled
  its boolean function is.
- **Large expressions refactor cleanly.** A Value Operation or Action that
  exceeds 256 boolean statements can be split into calls to helper Value
  Operations (each taking at most 20 boolean input Interface Views, or taking
  the underlying non-boolean views such as numbers). Each execution collapses
  into a single statement in the caller while preserving exact redundancy
  checking through the callee's contract.

### What the Compiler Checks

Value Operations are compiled bottom-up in parallel along their static DAG, and
Actions are then compiled bottom-up in parallel along their call/trigger DAG.
For each Value Operation (and each Action's boolean statements block), checked
once:

1. **Structural limits:** at most 20 boolean input Interface Views on a Value
   Operation (and exactly one written view on a pure boolean Value Operation),
   at most 256 boolean statements, at most 512 boolean inputs, and (when using
   ROBDDs past 20 inputs) at most **65,536** reachable non-terminal nodes in the
   canonical shared ROBDD.
2. **Order:** boolean statements and arguments passed to interchangeable views
   follow DLP 60's order.
3. **Redundant values:** no boolean statement computes a constant (`true` or
   `false`), or computes the same value or opposite value as a boolean input or
   an earlier statement (except `not` of that value).
4. **Dead statements:** every boolean statement's value reaches a written view
   or a non-boolean statement.
5. **Read views:** every boolean input Interface View of a pure boolean Value
   Operation changes the written view for at least one combination of the read
   views.
6. **Literals:** no boolean statement receives a Define literal (`true` or
   `false`), tracing through View Setting Statement copies to the value's
   origin.
7. **Matches:** no value computes the same function as a registered boolean
   operation (or its opposite) applied to at most three earlier values. `and`
   and `not` count as registered operations. A registered operation's own
   definition follows only `and`, `not`, and earlier registered operations under
   DLP 61's order.
8. **Spellings:** a value computed by a single execution of a registered
   operation uses the spelling that comes first in DLP 61's order. A `not` is
   never respelled.
9. **Wrappers:** no Value Operation merely wraps a registered operation; only
   the standard library wraps `and` and `not`, and Value Operations do not
   execute those wrappers. Wrapper checks inspect statements syntactically.

Each Value Operation is checked once where it is defined, regardless of how many
callers execute it.

### Representation

The boolean statements of a Value Operation or Action lower into an and-inverter
graph (AIG): every internal node is an `and` of two literals, and a literal is a
node index plus a 1-bit negation flag. (Here "literal" means a signed
logic-synthesis edge, not a Define boolean literal.) `not` flips the negation
bit without allocating a node, so `not (not x)` collapses to `x` automatically.
Leaves are the boolean inputs (arbitrary-width 0-based assignments, supporting
`I > 64` cleanly) and constant `false`.

AIG nodes are hash-consed in a single unique table with sorted operands and
immediate local simplification:

- `x and x` → `x`
- `x and not x` → `false`
- `x and true` → `x`
- `x and false` → `false`

A View Setting Statement allocates no node: the copy refers to the same literal
as its source.

### Executions of Boolean Value Operations

An execution of a boolean Value Operation is a single node in the caller's
graph: a reference to the callee plus the caller's argument literals. DLPs 59–61
check only values produced by the caller's own statements, never the callee's
internal statements (which were already checked where the callee is defined).
The execution's result is still checked in the caller because the caller can
pass correlated values to distinct views of the callee.

When a pure boolean Value Operation compiles, its contract records its boolean
function over its `k ≤ 20` read views, along with its interchangeable-view
symmetry partition and a 128-bit canonical fingerprint:

- **Small AIG:** when the callee's AIG has at most `2^k` nodes (for `k ≤ 6`) or
  at most `16k` nodes (for `k > 6`), callers evaluate those AIG nodes directly.
- **Truth table:** for `k ≤ 20`, the exact `2^k`-bit truth table of the written
  view (at most 128 KB at `k = 20`, and 8 bytes at `k ≤ 6`).
  - In a truth-table caller with `k ≤ 6`, each word is evaluated with direct bit
    lookups.
  - In a truth-table caller with `k > 6`, argument bit-vectors are transposed in
    8×8 blocks via SWAR bit-matrix transposition to extract 64 table indices at
    once before looking up the recorded table.
- **Canonical ROBDD (optional compact form):** for `k > 6`, the callee's output
  ROBDD (guaranteed ≤ 98,302 nodes for any `k ≤ 20`) can be stored alongside or
  materialized lazily when an ROBDD caller executes the callee, so ROBDD callers
  compose the callee node by node instead of splitting a `2^k`-bit table.

DLP 60's interchangeable-view groups come directly from the callee's recorded
contract. With at most 20 boolean read views, checking all pairs takes at most
`20 * 19 / 2 = 190` word-parallel truth-table swap comparisons (microseconds).
If symmetry is ever computed directly on a recorded diagram, the compiler
pre-partitions views using `O(|Diagram|)` biased mod-`(2^61 - 1)` Chow/Walsh
level signatures, filters non-symmetric pairs using targeted satisfying and
falsifying path samples over each view's dependency cone, and verifies remaining
pairs with zero-allocation lockstep `are_symmetric` checks.

### Counting Boolean Inputs

One pass over the statements collects the distinct boolean inputs read by
boolean statements:

- In a **pure boolean Value Operation**, the boolean inputs are exactly its
  boolean input Interface Views (`I ≤ 20`).
- In a **mixed Value Operation** or **Action**, the boolean inputs are its
  boolean input Interface Views (or contracted input boolean positions) plus any
  local view written by a non-boolean statement (such as a numeric comparison or
  a mixed Value Operation execution) that a boolean statement reads (`I ≤ 512`).

Local views written by boolean statements are derived values, not boolean
inputs. The input count depends only on syntax, so every compiler computes the
exact same count.

### Choosing a Method

Every value is decided exactly using one of two backends, chosen
deterministically from the boolean input count `I` and the arities of executed
Value Operations:

| Boolean inputs (`I`)                                             | Method                                                                         |
| ---------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `I ≤ 16`                                                         | Truth tables                                                                   |
| `17 ≤ I ≤ 20`, executing a Value Operation with `> 6` read views | Truth tables                                                                   |
| `17 ≤ I ≤ 20` otherwise                                          | ROBDDs (with automatic truth-table fallback if the ROBDD exceeds 65,536 nodes) |
| `21 ≤ I ≤ 512`                                                   | ROBDDs (subject to the 65,536 canonical reachable-node limit)                  |

Both backends produce identical errors on every Value Operation and Action.
Because `I ≤ 20` always falls back to truth tables if an ROBDD hits the node
cap, every pure boolean Value Operation (`I ≤ 20`, `S ≤ 256`) is guaranteed to
compile.

### Truth Tables

The compiler evaluates every node's truth table over all `I` boolean inputs
(`2^(max(I, 6) - 6)` 64-bit words per node — at most 128 KB per node and 32 MB
total for 256 statements at `I = 20`).

Each node's truth table is normalized (so a function and its complement share
one representative) and grouped using a hash bucket with **exact word-by-word
verification** (never hash-only equality):

- A statement is redundant if an earlier statement, a boolean input, or a
  constant falls in its exact equivalence class (opposite if negated).
- Read-view relevance on pure boolean Value Operations is checked directly by
  comparing cofactors across each view's bit stride in the output table.
- Dead statements are found purely from the statement dependency graph.

The compiler also exposes diagnostic helpers (`care_set_mask` over up to 4
inputs, and pairwise `implies` / `mutually_exclusive` queries) on both the
truth-table and ROBDD backends for clear error messages.

### ROBDDs

With ROBDDs, every boolean value maps to a canonical edge in one shared reduced
ordered binary decision diagram with **complement edges** (so a value and its
`not` share the same node, differing only in bit 0).

The variable ordering is fixed and compiler-independent: inputs are ordered by
**first-reached depth-first traversal** starting from each root value (values
not read by any other boolean statement, in statement order), visiting each
statement's arguments in written order, followed by any unreached inputs in
index order.

Core operations use native canonicalized apply routines with power-of-two
open-addressed caches that rehash dynamically as the node table grows:

- `and` / `or` via De Morgan complement edges (`lor(f, g) = land(f^1, g^1)^1`).
- Native `lxor` with 4× complement-edge canonicalization.
- Native `ite` with standard-triple canonicalization.
- Zero-allocation `O(I)` lockstep `distinguishing_path(a, b)` for finding an
  exact counterexample assignment where two edges differ.
- `apply_table` via native Shannon recursion with direct fast paths for
  `and`/`or`/`xor`/`ite`, and `compose` for recorded diagrams.

Node construction enforces a **2× internal construction cap** (`131,072`
allocated nodes for a `65,536` canonical limit) inside `Bdd::make()`, so even an
exponential intermediate expression aborts cleanly within ~5–10 MB of RAM. After
building all statement roots, the compiler counts the exact number of distinct
**reachable non-terminal nodes** (`reachable_node_count`) from all statement
edges:

- If `I ≤ 20` and the count exceeds `65,536` (or hits the construction cap), the
  compiler falls back to the truth-table backend.
- If `I > 20` and the count exceeds `65,536` (or hits the construction cap), the
  compiler rejects the operation with DLP 59's complexity error, pointing to the
  statement being built when the limit was crossed.

Equivalence checking on the shared ROBDD is `O(1)`:

- Two values are equal iff their edges are identical, and opposite iff their
  edges differ only in bit 0.
- A value is constant iff its edge is `kTrue` or `kFalse`.
- A read view matters iff its level appears in the output edge's reachable
  subgraph.
- Candidate matches are verified directly in the same manager, checking both
  functional equality and essentiality of all arguments (an `O(1)` check for
  arity 2, and `(k - 1)`-arity cofactor checks for arity 3).

### Registered Operations Order (DLP 61)

Registered operations are ordered deterministically by their function so that
boolean expressions read naturally to humans and never depend on the order
entries are listed in `booleans.defcl`:

1. `standard:/boolean/and`, then `standard:/boolean/not`.
2. Fewest `and`s in any AIG computing the operation's function (looked up in the
   precomputed exact-synthesis table of the 14 NPN classes of ≤ 3-variable
   functions).
3. Fewest read views.
4. Project-registered operations before standard-library-registered ones
   (standard-library operations follow only earlier standard-library operations;
   project operations follow `and`, `not`, all standard-library registered
   operations, and earlier project-registered operations).
5. More symmetric first (fewer interchangeable-view groups).
6. Truth table in counting order (first read view changing least often, rows
   from `(0, ..., 0)` to `(1, ..., 1)`, `false < true`).

For the standard boolean operations, this produces the exact order:

`and` → `not` → `or` → `implies` → `xor` → `eq` → `mux` → `maj`

Thus `or(a, b)` is defined from `and`/`not`, `implies(a, b)` is `or(not a, b)`,
`xor(a, b)` is `or(a and not b, b and not a)`, `eq(a, b)` is `not xor(a, b)`,
`mux(s, a, b)` is `or(s and a, b and not s)`, and `maj(a, b, c)` is
`mux(c, or(a, b), a and b)`.

### Finding Matches and Spellings

DLP 61's match search checks whether any value equals a registered operation (or
its opposite) applied to at most three earlier values. The same unified search
engine (`Matcher`) handles both matches and spellings in a single pass over
three modes (`kAll` for fixing, `kBestPerValue`, and `kBestOverall` with
descending-MFFC early exit for checking):

1. **Exact canonical class IDs:** each earlier value carries its exact
   equivalence class ID (from truth-table buckets or ROBDD edges), so duplicate
   or negated copies in the pool are deduplicated with zero hash-collision risk.
2. **Varied-density sampling + BDD collision-splitting:**
   - For `I ≤ 8`, all `2^I` assignments are sampled exhaustively (zero false
     positives).
   - For `I > 8`, the compiler starts with 256 multi-density samples (sparse,
     balanced, and dense polarities so deep `and`/`or` chains don't collapse to
     all-0 or all-1).
   - Under the ROBDD backend, any two distinct values that still collide on the
     initial samples are separated in deterministic batches using `O(I)`
     lockstep `distinguishing_path`, ensuring every distinct value has a unique
     sample signature before search begins.
3. **MFFC pruning & `not` skipping:** replacing a match must remove at least two
   statements, so `not` statements and values whose maximum fanout-free cone
   (MFFC) has size `< 2` are skipped. In `kBestOverall` checking mode, targets
   are searched in descending MFFC order and the search exits as soon as no
   remaining target can beat the best match found so far.
4. **Specialized & bitset-pruned argument search:**
   - Dynamic pool bitsets (`WordPool`) track which earlier values are `0` or `1`
     on each sample, with no fixed pool-size cap.
   - `xor` and `eq` use direct `O(1)` flat hash-table lookup on sample words
     (`target_word ^ arg0_word`).
   - `mux` splits data-first into two symmetric cases to prune immediately
     before selecting the control bit.
   - General arity-2 and arity-3 variants iterate views in optimal constraint
     order (`Variant::view_order`), intersecting newly forced sample bitsets
     with inherited candidate lists (`cand_buf_`) and deferring full candidate
     materialization until after `m0_`/`m1_` and hash checks pass.
5. **Exact verification & sample refinement:** surviving candidates are verified
   exactly on truth tables or the shared ROBDD. Any spurious candidate adds its
   exact counterexample assignment to the sample set so it never recurs.
6. **Spellings:** for any value already computed by a single execution of a
   registered operation (other than `not`), the search checks only registered
   operations whose best possible spelling could beat the current one (fewer
   negated arguments, or equal negated arguments and a smaller DLP 61 key),
   stopping on the first winning spelling when only reporting errors.

### Checking Again on Later Compiles

A Value Operation's check depends only on its own statements, its project's (and
standard library's) registered operations, and the contracts of the pure boolean
Value Operations it executes — never on how callees are written internally.

Each pure boolean Value Operation's contract stores its recorded function (small
AIG, truth table, or compact ROBDD), its symmetry partition, and a 128-bit
canonical hash. Rewriting a callee without changing its boolean function or
symmetry partition leaves its contract hash unchanged, so no caller needs to be
rechecked. Changing `booleans.defcl` rechecks only the project's own Value
Operations and Actions, and only for matches and spellings of the added or
removed registered operations.

### Fixing a Program

A refactoring tool automatically fixes DLP 59's redundant/opposite values, dead
statements, and unused read views, DLP 60's order, and DLP 61's matches,
spellings, and wrappers:

- **Unused read views (`drop_views`):** unused views are dropped one at a time,
  replacing each dropped view with the first kept read view that makes no value
  constant. Per-view substitution handles interacting unused views such as
  `xor(u1, u2)` where substituting all unused views with the same kept view
  would create a constant. On `I > 20`, constant checks dispatch through the
  ROBDD backend instead of allocating truth tables.
- **Batching non-overlapping fixes:** after one check, the tool groups matches
  in `O(N)` time, applies all redundant-value fixes and all largest-first
  non-overlapping matches with their first spellings, and rechecks.
- **Avoiding execution cycles (DLP 9):** if replacing a match inside a
  registered operation's dependency cone would introduce an execution cycle, the
  tool first inlines the cycle-forming executions into the registered
  operation's definition, fixing registered operations and their dependencies
  before the rest of the program.
- **Removing wrappers and identity ops:** operations that merely return a view
  or wrap a single statement are removed and substituted into their callers.

The fix loop is proven to terminate in Lean 4
(`boolean_equality_checking/proof/fixing_termination.lean`, theorem
`dag_prog_terminates`), which discharges state-space finiteness directly from
Define's static finite DAG computation graphs over a lexicographic measure:
total read views across all operations, then per-operation priority order
(unregistered ops first, then registered ops from largest key to smallest) over
`(statements, non-not statements, multiset of execution precedence keys, multiset of DLP 60 expression ranks)`.

Errors left for the programmer to fix: boolean literals passed to boolean
statements, constant values or constant written views, limit violations,
existing execution cycles, unused read views where every kept view creates a
constant, registered operations defined as wrappers, and cycle-forming
executions through non-boolean Value Operations.

## Measurements and Reasons

All measurements below come from the updated C++23 reference implementation
(`boolean_equality_checking/src/beq`) with the budget-free canonical ROBDD
architecture.

### Representation and Executions as References

- Structural hashing on the AIG takes ~2 µs for 256 statements and eliminates
  ~28% of redundant values before exact checking runs.
- Representing Value Operation executions as references to callee contracts
  keeps per-operation checking cost independent of call-graph depth; inlining
  graphs directly grows 3–4× per level and passes 20 million nodes at depth 14.
- Checking callees alone does not guarantee caller safety: callers pass
  correlated values to callee views, producing redundant or constant results in
  26–44% of random executions.

### Truth Tables vs. ROBDDs

- Truth tables depend only on `I` and `S` (≤ 2 ms at 16 inputs, ~52 ms at 20
  inputs for 256 statements; ≤ 32 MB peak memory).
- Past 16 inputs, ROBDDs are dramatically faster except when executing wide
  (`> 6`-view) callees at `17–20` inputs, where the 8×8 bit-matrix-transpose
  truth-table lookup avoids node-by-node diagram composition.
- Variable ordering is critical: first-reached DFS input order is 24–130× faster
  than source order or random order on dense and XOR-heavy circuits.

### Real-World Codebase Coverage (3,265 Units Across 11 Codebases)

Measured across all 3,265 real-world boolean units extracted from Linux, GCC,
LLVM/Clang, Go, Rust, TypeScript, Mypy, TiDB, SQLite, PostgreSQL, and CPython
(`results/budget_real_steps.jsonl`):

| Subset / Limit                                                               | Passing                                                                                     | Max ROBDD nodes                                                       | Typical / max latency                   |
| ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- | --------------------------------------- |
| **Standalone functions (`scope=1`, 376 units)**                              | **376 / 376 (100%)** under _all_ conservative caps (`S ≤ 256`, `I ≤ 512`, `ROBDD ≤ 65,536`) | **3,500** (`max S = 184`, `max I + S = 358`)                          | < 1 ms                                  |
| **All units including `scope=2` inlining (3,265 units) at `ROBDD ≤ 65,536`** | **3,256 / 3,265 (99.72%)**                                                                  | 36,919 (`go: loadStorePairClass`, `I=2933, S=2274`, 4.5 ms)           | median 0.35 ms                          |
| **All units at `ROBDD ≤ 4,000,000`**                                         | **3,264 / 3,265 (99.97%)**                                                                  | 3,893,860 (`mypy: narrow_declared_type`, `scope=2`, `I=1290`, 749 ms) | median 0.35 ms, p99 21.9 ms, max 1.19 s |

Only 9 units out of 3,265 exceed `65,536` ROBDD nodes — all 9 are large
`scope=2` inlined functions (the 1 unit over 4M is `mypy`'s `scope=2`
`visit_comparison_expr` at 44.4M nodes, which as a standalone `scope=1` function
has only 54 ROBDD nodes).

### Why Registered Operations Are Capped at Arity ≤ 3 and Statements at ≤ 256

Stress-testing `Matcher` on adversarial linear-BDD chains of `S` calls to an
unregistered 3-input operation `u3(a, b, c) = (a and b) xor c` (where nothing
matches, so `Matcher` must prove no match exists for every statement across all
`N = I + S` earlier values):

| Statements (`S`) | Inputs (`I`) | Arity ≤ 3 (`or, implies, xor, eq, mux, maj`) | With arity-4 XOR-like op (`par4`) |
| ---------------- | ------------ | -------------------------------------------- | --------------------------------- |
| **256**          | **513**      | **0.11 s**                                   | **Timeout (> 15 s)**              |
| 512              | 1,025        | 0.64 s                                       | —                                 |
| 1,024            | 2,049        | 4.72 s                                       | —                                 |
| 2,048            | 4,097        | Timeout (> 15 s)                             | —                                 |

Arity-4 XOR-like operations have no forcing prefix until the 4th argument,
giving worst-case `O(S * N^3)` search even on a tiny linear BDD. Capping
registered operations at **arity ≤ 3** eliminates the `O(S * N^3)` cliff
completely (while keeping every standard boolean combinator including `mux` and
`maj`), and capping **`S ≤ 256` and `I ≤ 512`** bounds worst-case `O(S * N^2)`
match search to **~0.11 s** even on adversarial non-matching inputs.

### Whole-Program Benchmarks

Checking generated programs with ~20% mixed Value Operations from scratch
(single-threaded reference binary):

| Program                                        | Total wall time | Peak RSS   | Key breakdown                                                         |
| ---------------------------------------------- | --------------- | ---------- | --------------------------------------------------------------------- |
| `ops_15k` (14,897 ops, ≤ 10 inputs)            | **1.34 s**      | **84 MB**  | ~90 µs/op                                                             |
| `ops_2k_wide` (1,995 ops, mostly 16–20 inputs) | **12.26 s**     | **188 MB** | 4.90 s wide table lookups (8×8 transpose), 1.02 s matches + spellings |

Across all 277 synthetic stress workloads (`dense`, `xor_heavy`, `parity`,
`chain`, `mult`, `real_shape`), 277 / 277 finish cleanly with zero timeouts
(e.g., `dense_8_256` in 0.077 s / 17.2 MB; `dense_48_256` in 0.078 s;
`xor_heavy_22_256` in 0.047 s).

## Approaches That Didn't Work

### Limits and Budgets

- **A compiler step budget (`StepBudget`).** Counting internal compiler work
  steps (BDD ops, nodes, search steps, sample evals) is unpredictable for
  programmers, tightly coupled to one implementation's internal optimizations,
  and hard to standardize across compilers. The five structural limits plus the
  canonical shared ROBDD reachable-node cap are 100% compiler-independent, easy
  to communicate, and bound both time and memory more cleanly.
- **Arity-4 registered operations.** Even with `S = 256`, an arity-4 parity or
  XOR-topped registered operation causes an `O(S * N^3)` search cliff (> 15 s)
  on non-matching chains, and requires a 222-class exact-synthesis table whose
  hardest classes took 13 minutes to compute. Capping registered ops at arity
  `≤ 3` covers all standard boolean combinators with only 14 NPN classes and
  eliminates the `O(S^4)` cliff.
- **High statement caps (e.g., 8,192 statements) without a step budget.** Even
  when the ROBDD stays small and linear, arity-3 `Matcher` scales as
  `O(S * (I + S)^2)` on adversarial non-matching chains (~4.7 s at `S = 1,024`,
  > 15 s at `S = 2,048`, ~40 minutes at `S = 8,192`). Keeping `S ≤ 256` and
  > `I ≤ 512` keeps worst-case runtime around 0.1 s while covering 100% of
  > standalone real-world functions.
- **A time limit or SAT solver conflict limit.** Both make compilation results
  depend on hardware speed, load, or solver version.
- **Partial checking or cutting large graphs into new inputs.** Silently missing
  redundancies breaks Forward Compatibility because a smarter future compiler
  would reject previously compiling programs.
- **A live-value width limit.** Measured widths on real and generated 256-stmt
  code were 17–74 even when ROBDDs had only a few thousand nodes, so any width
  limit tight enough to bound `2^width` would reject normal code.

### Methods

- **SAT sweeping.** Over 25× slower than truth tables at 16–20 inputs without
  cached patterns, and each candidate match required a separate solver call,
  timing out past 128 statements.
- **ROBDDs for every operation past 16 inputs.** At 17–20 inputs executing wide
  (`> 6`-view) callees, node-by-node BDD composition was > 2× slower to check
  and > 5× slower to fix than 8×8-transposed truth-table lookups.
- **Chunked truth tables and shared-input splitting.** Both recompute work per
  candidate match and lose to ROBDDs past 16 inputs.
- **Other BDD variable orders.** Source order, reverse order, and random order
  were 24–130× slower than first-reached DFS order on dense and XOR-heavy code.

### Matches, Spellings, and Fixing

- **Cuts of at most four values.** Found only 58% of planted redundant values
  (506 / 872), leaving many duplicate ways to write the same logic legal.
- **Listing order in `booleans.defcl`.** Made program legality depend on config
  order (720 orders of the 6 standard ops produced 14 distinct `and`-count
  assignments). Function-based keys make `booleans.defcl` order-independent.
- **Simplifying constant values or replacing unused views with `false`.**
  Propagating constants through callee executions blew up 20–40 statements into
  thousands; constants remain programmer errors, and unused views substitute a
  kept read view instead.

## Open Questions

- **Unused read view when every kept view creates a constant:** e.g.,
  `g(x, y, z) = xor(xor(x, z), xor(y, z)) and x`. The refactoring tool leaves
  this to the programmer; whether it should try substituting another internal
  value is open.
- **Constants created while breaking execution cycles during fixing:** inlining
  a cycle-forming execution can pair a value with its `not`; the tool stops and
  reports the constant to the programmer.
- **One canonical program per function:** fixing always terminates, but two
  equivalent Value Operations can still differ in which intermediate values they
  introduce.
- **Redundancy across non-boolean statements:** e.g., `(x < 3) and (x < 5)`
  treats both comparisons as independent boolean inputs. Proving non-boolean
  implications requires arithmetic/SMT reasoning outside pure boolean equality.
- **Diagnostic presentation:** both truth-table and ROBDD backends provide
  care-set masks and pairwise `implies`/`mutually_exclusive` queries, plus exact
  `distinguishing_path` counterexamples; finalizing how error messages surface
  these to programmers is tracked in
  [boolean-error-messages.md](boolean-error-messages.md).
- **Non-boolean value equality:** extending "one way to write it" to numeric or
  multi-bit values will require algebraic or SMT techniques rather than truth
  tables and ROBDDs.

---

## Appendix: Parallel Compilation, Contracts, and Whole-Program Action Optimization

Define compiles **all independent Value Operations in parallel** (bottom-up
along the static Value Operation DAG) and then **all independent Actions in
parallel** (bottom-up along the static Action call/trigger DAG). This appendix
specifies the boolean contract information exchanged across those compilation
boundaries, how parallel memory stays bounded, and how Action contracts can
support future whole-program boolean optimization without adding new
programmer-facing limits.

### Parallel Compilation Memory Budget

Because workers compile Value Operations and Actions concurrently, peak memory
scales with the number of active worker threads `T`:

- **Truth-table checks (`I ≤ 20, S ≤ 256`):** at most **32 MB** per worker (only
  reached at `I = 20, S = 256`; at `I ≤ 16`, ≤ 2 MB).
- **ROBDD checks (`21 ≤ I ≤ 512`, `≤ 65,536` canonical nodes, `131,072` hard
  construction cap):** **~5–10 MB** per worker (even 32 simultaneous worst-case
  ROBDD builds use only ~160–320 MB total).
- **Exported Value Operation contracts:** **≤ 128 KB** each (typically bytes to
  a few KB), making them cheap to serialize, cache on disk, and share across
  worker threads.

### Value Operation Contracts

When a Value Operation finishes compiling, its contract exposes everything a
caller (another Value Operation or an Action) needs so callers never re-parse or
re-check the callee's body:

1. **Pure boolean Value Operations (`k ≤ 20` boolean input Interface Views, 1
   boolean output view):**
   - **Canonical boolean function:** stored in whichever representation is most
     compact for callers:
     - Small AIG (`≤ 2^k` nodes for `k ≤ 6`, or `≤ 16k` nodes for `k > 6`),
     - Exact `2^k`-bit truth table (**≤ 128 KB** at `k = 20`, **8 bytes** at
       `k ≤ 6`), and/or
     - Output ROBDD over the `k` read views (mathematically guaranteed **≤
       98,302** non-terminal nodes for any 20-variable function with complement
       edges, and typically tens to hundreds of nodes).
   - **Interchangeable read-view groups (symmetry partition):** `k` small
     integers used by callers to check DLP 60 argument ordering in `O(k)`.
   - **Canonical 128-bit function fingerprint:** for `O(1)` equivalence,
     wrapper, and incremental-recompilation checks.
2. **Registered boolean Value Operations (`k ≤ 3`, listed in
   `booleans.defcl`):**
   - Everything above, plus:
   - **DLP 61 sort key:**
     `(fewest_ands, k, is_stdlib, num_groups, counting_order_tt)` (the truth
     table fits in a single byte `uint8_t` for `k ≤ 3`).
   - **Canonical `Variant` list:** deduplicated argument permutations modulo
     symmetry (at most `3! = 6` variants).
3. **Mixed Value Operations (boolean and non-boolean views):**
   - Any boolean output view that depends exclusively on boolean input Interface
     Views exports the same summary as a pure boolean Value Operation.
   - Any boolean output view that depends on non-boolean views is exposed to
     callers as an opaque boolean output (unless extended in the future with
     cross-output relational invariants as below).

Because every Value Operation is capped at **≤ 20 boolean input Interface
Views**, no separate exported-contract ROBDD node limit is needed: the 20-view
cap mathematically bounds every contract to ≤ 128 KB (truth table) and ≤ 98,302
nodes (ROBDD).

### Action Contracts for Future Whole-Program Boolean Optimization

An Action is not a pure boolean function — it operates on particles in
positions, triggers other Actions, and produces Action Guarantees (including
Action Particle Value Guarantees and Destruction Contracts). To enable future
**whole-program boolean optimizations** across Action boundaries — such as
eliminating dead triggers/branches, folding duplicate boolean Value Operation
executions across caller/callee boundaries, propagating known flags, or
specializing callees — an Action Contract can summarize boolean behavior over
its **contracted boolean interface positions** (`V` positions) in three
increasing tiers:

1. **Tier 1 — Per-position value, sensitivity, and frame facts (`O(V)` size):**
   - **Constants:** output boolean position `p_out` is guaranteed `true` or
     `false`.
   - **Copies and negations:** `p_out == p_in` or `p_out == not p_in`.
   - **Frame conditions:** `p` is unchanged by the Action (so callers preserve
     their existing boolean knowledge about `p` across a callee trigger).
   - **Input sensitivity:** which contracted boolean inputs are actually read
     (and under what guard), enabling callers to skip computing dead inputs or
     specialize the callee.
2. **Tier 2 — Pairwise relational invariants / 2-SAT implication graph (`O(V^2)`
   bits):**
   - Captures the vast majority of real-world cross-Action boolean invariants,
     including those produced by non-boolean work (parsing, I/O, comparisons):
     - **Mutual exclusion:** `!(has_error and is_valid)`
     - **Implication:** `is_empty => is_valid`, `strict_mode => !allow_fallback`
     - **Equivalence / complement:** `succeeded == !failed`
   - Integrates naturally with Define's **Action Particle Value Guarantees**
     (e.g., _"whenever `has_error == false`, `result` is occupied and its value
     is set"_).
   - Strictly polynomial and compact: for `V = 64` contracted boolean positions,
     the full implication matrix is 512 bytes, and transitive closure across
     composed Actions takes `O(V^3 / 64)` bit operations (microseconds) with
     zero exponential blowup.
3. **Tier 3 — Optional bounded multi-way relational summaries
   (optimization-only):**
   - For multi-way relationships not expressible as pairwise clauses (e.g.,
     `done == (a or b)` or `a and b => c`), an Action Contract may optionally
     carry a small relational ROBDD over its contracted boolean positions,
     internally capped (e.g., ≤ 4,096 nodes / 48 KB).

### Legality vs. Optimization Contract Boundary

A key design principle keeps Action contracts from ever imposing unpredictable
limits on Define programmers:

- **Whole-program optimization contracts never affect language legality.**
  Because optimization only needs to preserve soundness (never decide whether a
  program compiles), the compiler can compute Tier 1 + Tier 2 + Tier 3 summaries
  internally and **soundly widen** any Tier 3 relational BDD that exceeds its
  internal budget (e.g., during existential quantification when composing two
  Actions) back to Tier 1 + Tier 2 — with zero impact on which programs compile.
- **If cross-Action boolean invariants are ever promoted into language
  legality** (for example, rejecting dead branches in a caller based on a callee
  Action's boolean postconditions), legality should rely **only on Tier 1 + Tier
  2 (constants, frame conditions, and the exact 2-SAT implication closure)**.
  Because 2-SAT implication closure over contracted boolean literals is unique,
  canonical, and strictly polynomial, it guarantees cross-compiler determinism
  with no exponential blowup and no heuristic node cap — requiring at most a
  generous bound on contracted boolean interface positions per Action (such as
  `≤ 256`, which caps the implication matrix at 16 KB).
