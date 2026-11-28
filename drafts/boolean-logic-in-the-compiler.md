# Boolean Logic in the Compiler

How the compiler represents boolean logic, checks the rules of DLP 56 (Logical
Operations for Boolean Values), DLP 59 (No Redundant Boolean Logic), DLP 60
(Interchangeable Views), DLP 61 (Associative Operations), DLP 62 (Boolean
Statement Order), DLP 63 (Factored Boolean Logic), DLP 64 (Standard Boolean
Operations), DLP 65 (Limits on Boolean Logic), and DLP 66 (Boolean Contracts for
Abstract Operations), automatically refactors programs until they follow those
rules (DLP 67, Auto-Fixing Boolean Logic), and structures Value Operation and
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

The compiler enforces four deterministic, compiler-independent limits on boolean
logic. Together they bound contract size, per-worker memory in parallel builds,
exponential BDD growth, and polynomial match search — with no machine-dependent
timeouts and no heuristic step budget. Raising any of these limits in a future
version of Define only accepts more programs, preserving Forward Compatibility:

| Limit                                      | Scope                                                           | Value                 | What it bounds                                                                                                                                                                                             |
| ------------------------------------------ | --------------------------------------------------------------- | --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Boolean input views**                    | Every Value Operation                                           | **≤ 20**              | Bounds every Boolean Value Operation's exported contract to **≤ 128 KB** (truth table) or **≤ 98,302** ROBDD nodes.                                                                                        |
| **Boolean Statements**                     | Every Value Operation and Action                                | **≤ 256**             | Keeps checking and matching fast even on adversarial non-matching chains; ensures every Boolean Value Operation fits unconditionally inside the `(256 statements, 20 inputs)` truth-table floor.           |
| **Boolean inputs**                         | Every Value Operation and Action                                | **≤ 512**             | Bounds the `Matcher` value pool (`N = I + S ≤ 768`) on mixed Value Operations and Actions with many non-boolean comparisons (`x == 1`, `x < y`, etc.), keeping worst-case `Matcher` runtime around ~30 ms. |
| **Canonical shared ROBDD reachable nodes** | Mixed Value Operations and Actions with `21–512` boolean inputs | **≤ 65,536 (`2^16`)** | Prevents exponential `O(2^I)` blowups past 20 inputs; bounds worst-case memory to **~5–10 MB per parallel worker** and build time to **~5–20 ms**.                                                         |

Two consequences follow directly from these limits:

- **Every Boolean Value Operation always compiles through the guaranteed
  truth-table floor.** Because a Boolean Value Operation has at most 20 boolean
  input views (its only boolean inputs) and at most 256 Boolean Statements, it
  can never hit an ROBDD limit, regardless of how tangled its boolean function
  is.
- **Large expressions refactor cleanly.** A Value Operation or Action that
  exceeds 256 Boolean Statements can be split into calls to helper Value
  Operations (each taking at most 20 boolean input views, or taking the
  underlying non-boolean views such as numbers). Each execution collapses into a
  single statement in the caller while preserving exact redundancy checking
  through the callee's contract.

### What the Compiler Checks

Value Operations are compiled bottom-up in parallel along their static DAG, and
Actions are then compiled bottom-up in parallel along their call/trigger DAG.
For each Value Operation (and each Action's Boolean Statements block), checked
once in strict priority order (**DLP 59 → DLPs 60–63 → DLP 64**):

1. **Structural limits:** at most 20 boolean input views on a Value Operation
   (exactly one output view on a Boolean Value Operation; on a non-Boolean Value
   Operation, no boolean output view's Boolean Sources may include a boolean
   input view, and no two boolean output views may share a Boolean Source), at
   most 256 Boolean Statements, at most 512 boolean inputs, and (when using
   ROBDDs past 20 inputs) at most **65,536** reachable non-terminal nodes in the
   canonical shared ROBDD.
2. **Literals, dead statements, and input views (DLP 56/59):**
   - No execution of an Abstract Operation (in a Value Operation or Action)
     looks at a boolean literal or a view/particle known to contain one (tracing
     through View Setting Statements in Value Operations, and local sets or
     transitive callee DLP 53 guarantees in Actions).
   - Every Boolean Statement's value is read, directly or indirectly, by an
     output view or a non-boolean statement (no dead statements).
   - Every boolean input of a Value Operation (each boolean input view, and each
     boolean view written by a non-boolean statement) must appear in the Boolean
     Sources of at least one boolean output view or at least one boolean
     argument passed to a non-boolean statement; and for every such boolean
     output view or boolean argument, changing any view in its Boolean Sources
     must be able to change its value.
3. **Redundant values (DLP 59):** no Boolean Statement computes a constant
   (`true` or `false`), or computes the same value or opposite value as a
   boolean input or an earlier statement (except `not` of that value).
4. **Argument order (DLP 60), associative grouping (DLP 61), statement order
   (DLP 62), and factoring (DLP 63):**
   - Arguments passed to declared interchangeable view groups (DLP 60) follow
     DLP 60's rank order, and Boolean Statements follow DLP 62's depth-first
     statement order.
   - **Associative grouping (DLP 61):** every maximal single-use chain of an
     associative operation is folded left-to-right (in DLP 60 rank order when
     interchangeable, or preserving left-to-right leaf order otherwise), with no
     balanced sub-pairs.
   - **Factoring common terms (DLP 63):** for the four distributive pairs of
     standard boolean operations (`(and, or)`, `(or, and)`, `(and, xor)`,
     `(or, equal)`), no value `x` repeats across two or more single-use
     `inner`-chain terms of the same single-use `outer`-chain.
5. **Standard boolean operations (DLP 64):** checked only when the operation has
   no DLP 59 redundant values and no DLP 63 unfactored common terms:
   - **Matches:** no value computes the same function as one of the five
     standard boolean operations (`and`, `not`, `or`, `xor`, `equal`) — or its
     opposite — applied to earlier values, when replacing it removes at least
     two statements (three for an opposite). Each standard library operation's
     own definition follows only earlier standard operations in the fixed order
     `and`, `not`, `or`, `xor`, `equal`.
   - **Spellings:** a value computed by a single execution of a standard boolean
     operation uses the spelling that comes first (fewest negated arguments,
     then fixed order `and`, `not`, `or`, `xor`, `equal`, then argument ranks).
     A `not` is never respelled.
   - **Wrappers:** no Value Operation merely wraps a standard boolean operation;
     only the standard library wraps `and` and `not` for Actions, and Value
     Operations do not execute those wrappers. Wrapper checks inspect statements
     syntactically.

Each Value Operation is checked once where it is defined, regardless of how many
callers execute it.

### Representation

The Boolean Statements of a Value Operation or Action lower into an and-inverter
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

An execution of a Boolean Value Operation is a single node in the caller's
graph: a reference to the callee plus the caller's argument literals. DLPs 59–64
check only values produced by the caller's own statements, never the callee's
internal statements (which were already checked where the callee is defined).
The execution's result is still checked in the caller because the caller can
pass correlated values to distinct views of the callee.

When a Boolean Value Operation compiles, its contract records its boolean
function over its `k ≤ 20` input views and a 128-bit canonical fingerprint:

- **Small AIG:** when the callee's AIG has at most `2^k` nodes (for `k ≤ 6`) or
  at most `16k` nodes (for `k > 6`), callers evaluate those AIG nodes directly.
- **Truth table:** for `k ≤ 20`, the exact `2^k`-bit truth table of the output
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

### Counting Boolean Inputs

One pass over the statements collects the distinct boolean inputs read by
Boolean Statements:

- In a **Boolean Value Operation**, the boolean inputs are exactly its boolean
  input views (`I ≤ 20`).
- In a **mixed Value Operation** or **Action**, the boolean inputs are its
  boolean input views (or contracted input boolean positions) plus any local
  view written by a non-boolean statement (such as a numeric comparison or a
  mixed Value Operation execution) that a Boolean Statement reads (`I ≤ 512`).

Local views written by Boolean Statements are derived values, not boolean
inputs. The input count depends only on syntax, so every compiler computes the
exact same count.

### Choosing a Method

Every value is decided exactly using one of two backends, chosen
deterministically from the boolean input count `I` and the arities of executed
Value Operations:

| Boolean inputs (`I`)                                              | Method                                                                         |
| ----------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `I ≤ 16`                                                          | Truth tables                                                                   |
| `17 ≤ I ≤ 20`, executing a Value Operation with `> 6` input views | Truth tables                                                                   |
| `17 ≤ I ≤ 20` otherwise                                           | ROBDDs (with automatic truth-table fallback if the ROBDD exceeds 65,536 nodes) |
| `21 ≤ I ≤ 512`                                                    | ROBDDs (subject to the 65,536 canonical reachable-node limit)                  |

Both backends produce identical errors on every Value Operation and Action.
Because `I ≤ 20` always falls back to truth tables if an ROBDD hits the node
cap, every Boolean Value Operation (`I ≤ 20`, `S ≤ 256`) is guaranteed to
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
- Useless boolean inputs are checked directly by comparing cofactors across each
  source's bit stride in the truth table of each boolean output view and each
  boolean argument passed to a non-boolean statement.
- Dead statements are found purely from the statement dependency graph.

The compiler also exposes diagnostic helpers (`care_set_mask` over up to 4
inputs, and pairwise `implies` / `mutually_exclusive` queries) on both the
truth-table and ROBDD backends for clear error messages.

### ROBDDs

With ROBDDs, every boolean view maps to a canonical edge in one shared reduced
ordered binary decision diagram with **complement edges** (so a value and its
`not` share the same node, differing only in bit 0).

The variable ordering is fixed and compiler-independent: inputs are ordered by
**first-reached depth-first traversal** starting from each terminal value (a
value not read by any other Boolean Statement, in statement order), visiting
each statement's arguments in written order, followed by any unreached inputs in
index order.

Core operations use native canonicalized apply routines with power-of-two
open-addressed caches that rehash dynamically as the node table grows:

- `and` / `or` via De Morgan complement edges (`lor(f, g) = land(f^1, g^1)^1`).
- Native `lxor` with 4× complement-edge canonicalization.
- Native `ite` with standard-triple canonicalization.
- Zero-allocation `O(I)` lockstep `distinguishing_path(a, b)` for finding an
  exact counterexample assignment where two edges differ.
- `apply_table` via native Shannon recursion with direct fast paths for
  `and`/`or`/`xor`/`equal`, and `compose` for recorded diagrams.

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
- A view in the Boolean Sources of a boolean output view (or of a boolean
  argument passed to a non-boolean statement) matters iff its level appears in
  that view's reachable ROBDD subgraph.
- Candidate matches for the five standard operations are verified directly in
  the same manager, checking both functional equality and essentiality of all
  arguments in `O(1)` via direct edge comparisons.

### Verifying Interchangeable Views (DLP 60)

Logical Operations are trusted as defined. On any Value Operation that declares
View Interchangeability Statements, the compiler verifies each statement
(`view<b>` interchangeable with `view<a>`) with two deterministic checks:

1. **Direct structural check (`O(S)` bottom-up hash-consing, all Value
   Operations):**
   - Run one bottom-up pass over `it does` in statement order (already
     topological under Single Assignment), assigning every view a canonical
     integer ID: interface input views (holding their initial value) and
     literals get unique IDs, View Setting Statements copy their source's ID,
     and each executed operation `op` sorts argument IDs within each of `op`'s
     declared interchangeable view groups (`O(k log k)`) and interns
     `(op_name, sorted_arg_ids, output_view_index)` in a hash table.
   - With DLP 61 associative operations, single-use associative chains of the
     same operation are flattened before interning (sorting leaves when
     interchangeable, preserving order when non-interchangeable).
   - For each View Interchangeability Statement, run one second linear pass over
     `it does` with `view<a>` and `view<b>`'s initial IDs swapped, reusing the
     same intern table. The check succeeds iff every output view receives the
     exact same ID as in the original pass.
   - Verifying the `m - 1` declared statements of a size-`m` interchangeable
     group generates all `m!` permutations in `O(m * S)` total time with zero
     backtracking and zero callee expansion.
2. **Exact boolean fallback (Boolean Value Operations):**
   - If the structural check does not prove interchangeability (such as
     `majority(a, b, c)` or `all_equal(a, b, c)`, whose canonical forms are
     structurally asymmetric due to DLP 59 and DLP 63), check the swap directly
     on the truth table or ROBDD already built for DLP 59.

### Associative Grouping and Factoring (DLPs 61 and 63)

DLP 61 grouping applies to associative operations (declared on Logical
Operations via `it is associative with view<...>.` and inferred automatically on
Value Operations — exact via DLP 59's boolean function for Boolean Value
Operations, and structurally on pure chains of associative operations for
non-Boolean Value Operations, ignoring any candidate group that partially
overlaps a DLP 60 interchangeable view group). DLP 63 factoring applies to the
four distributive pairs among standard boolean operations (`(and, or)`,
`(or, and)`, `(and, xor)`, and `(or, equal)`). Under DLPs 59 and 64, these four
pairs are mathematically the only distributive pairs among commutative,
associative binary boolean operations.

Using reference counts (`readers[v]`) of every value across all statements and
output views:

1. **Maximal single-use chains:** a statement `s` of a commutative, associative
   binary op `K` is a **chain head** if either `readers[s] ≠ 1` or its sole
   reader is not an execution of the same operation `K`. Walking downward from a
   chain head collects every child statement of the same op `K` with
   `readers[child] == 1` as an internal node of the chain, and all other
   operands as chain leaves.
2. **Grouping check (`order_grouping`):** every maximal chain of length `m ≥ 3`
   must be folded strictly left-to-right in DLP 60 rank order:
   - No internal statement may have _both_ arguments be internal chain nodes
     (forbidding balanced pairs like `(a and b) and (c and d)`).
   - At each step from the deepest internal node up to the chain head, the
     single newly introduced leaf must have rank strictly greater than (or equal
     to) the previous leaf, matching the canonical fold `op(v_1, v_2)`,
     `op(v_3, t_1)`, ..., `op(v_m, t_{m-2})` where
     `rank(v_1) ≤ rank(v_2) ≤ ... ≤ rank(v_m)` (combined with DLP 60's argument
     order, each leaf `v_k` appears on the lower-ranked side of
     `op(v_k, t_{k-2})`).
3. **Factoring check (`order_factor`):** for every chain head `r` of an `outer`
   op with `≥ 2` leaves, collect all single-use `inner`-chain leaves (where
   `inner` distributes over `outer`). If any value `x` appears in `c ≥ 2`
   distinct `inner`-chain terms of `r`, report an unfactored common term —
   choosing the factor `x` that removes the most terms (`c`), breaking ties by
   lowest DLP 60 rank. Factoring is checked and fixed **before** DLP 64 match
   search so expressions like `(a and b) or (a and c)` factor cleanly to
   `a and (b or c)`.

### Standard Boolean Operations (DLP 64)

Define enforces a single fixed global set of five standard boolean operations
across all projects:

`and` → `not` → `or` → `xor` → `equal`

Their definitions follow this fixed order:

- `standard:/boolean/and` and `standard:/boolean/not` (primitives).
- `standard:/boolean/or(a, b) = not (not a and not b)`.
- `standard:/boolean/xor(a, b) = or(a and not b, b and not a)`.
- `standard:/boolean/equal(a, b) = not xor(a, b)`.

All five operations have arity ≤ 2 and are completely symmetric across their
input views. There is no project-level registration file, no NPN exact-synthesis
table, and no per-project boolean dialect.

### Finding Matches and Spellings

When an operation has no DLP 59 redundant values and no DLP 63 unfactored common
terms, a single unified search engine (`Matcher`) checks whether any statement
computes one of the standard operations (or its opposite) applied to earlier
values, and whether any single execution of a standard operation has an earlier
spelling:

1. **Strictly `O(S * (I + S))` search with zero backtracking:** because every
   standard operation has arity ≤ 2 and is symmetric, `Matcher` never searches
   3- or 4-argument combinations:
   - `xor` and `equal` run a flat `O(1)` hash-table lookup on sample words
     (`target_word ^ arg0_word`) across the earlier-value pool.
   - `and` and `or` intersect the single remaining argument's candidate pool via
     dynamic bitsets (`WordPool`).
   - `not` is skipped because no redundant/opposite values remain.
2. **Exact canonical class IDs:** each earlier value carries its exact
   equivalence class ID (from truth-table buckets or ROBDD edges), so duplicate
   or negated copies in the pool are deduplicated with zero hash-collision risk.
3. **Varied-density sampling + BDD collision-splitting:**
   - For `I ≤ 8`, all `2^I` assignments are sampled exhaustively (zero false
     positives).
   - For `I > 8`, the compiler starts with 256 multi-density samples (sparse,
     balanced, and dense polarities so deep `and`/`or` chains don't collapse to
     all-0 or all-1).
   - Under the ROBDD backend, any two distinct values that still collide on the
     initial samples are separated in deterministic batches using `O(I)`
     lockstep `distinguishing_path`, ensuring every distinct value has a unique
     sample signature before search begins.
4. **MFFC pruning and best-match modes:** replacing a match must remove at least
   two statements (three for an opposite result), so `not` statements and values
   whose maximum fanout-free cone (MFFC) has size `< 2` are skipped. In compiler
   checking mode (`kBestOverall`), targets are searched in descending MFFC order
   and the search exits as soon as no remaining target can beat the best match
   found so far.
5. **Exact verification and sample refinement:** surviving candidates are
   verified exactly on truth tables or the shared ROBDD. Any spurious candidate
   adds its exact counterexample assignment to the sample set so it never
   recurs.
6. **Spellings:** for any value already computed by a single execution of a
   standard operation (other than `not`), the search checks only standard
   operations whose best possible spelling could beat the current one (fewer
   negated arguments, or equal negated arguments and an earlier standard
   operation in `and`, `not`, `or`, `xor`, `equal`), stopping on the first
   winning spelling when only reporting errors.

### Checking Again on Later Compiles

A Value Operation's check depends only on its own statements and the contracts
of the Boolean Value Operations it executes — never on how callees are written
internally.

Each Boolean Value Operation's contract stores its recorded function (small AIG,
truth table, or compact ROBDD) and a 128-bit canonical hash. Rewriting a callee
without changing its boolean function leaves its contract hash unchanged, so no
caller needs to be rechecked. Because the standard boolean operation set is
fixed globally across all projects, there is no config-driven invalidation pass.

### Fixing a Program (DLP 67)

The automated refactoring tool brings Value Operations into compliance with DLPs
59–66 in four bottom-up phases along the static execution DAG (DLP 9):

1. **Phase 1 — Structural interface rewrites (DLP 59):**
   - Split multi-output Boolean Value Operations into one single-output Boolean
     Value Operation per output view and update callers.
   - Extract disallowed boolean output logic (`mixed_bool_view` and
     `mixed_shared_input`) from non-Boolean Value Operations into Boolean Value
     Operations executed by callers, returning each distinct non-boolean Boolean
     Source directly at most once.
2. **Phase 2 — Literal propagation, constant folding, callee specialization, and
   useless-input elimination (DLP 59):**
   - Replace constant Boolean Statements with `true`/`false`, fold `and`/`not`
     on boolean literals, and specialize any Value Operation callee (`call` or
     `run`) that receives boolean literals into a deduplicated helper
     (`<callee>__L<pos><T|F>...`).
   - Propagate constant-output Boolean Value Operations (`true`/`false`) into
     callers.
   - Drop unused boolean input views on Boolean Value Operations (`drop_views`)
     by kept-view substitution when constant-free, falling back to `false`
     substitution + literal propagation when every kept view creates a constant
     (such as `xor(xor(x, z), xor(y, z)) and x`).
   - In non-Boolean Value Operations, eliminate per-expression useless boolean
     inputs (such as `xor_and`) by cloning the target expression's boolean
     sub-DAG with that input substituted by `false`, and remove globally unused
     boolean inputs (dropping unused input views, deleting dead pure
     comparisons, or specializing callees to drop unused output views).
3. **Phase 3 — Single-operation normalization loop (DLPs 59–64):**
   - **Canonicalize:** remove dead statements, resolve copies, sort arguments of
     declared interchangeable view groups (DLP 60) by rank, and topologically
     sort Boolean Statements into DLP 62 depth-first order.
   - **Redundant and opposite values (DLP 59):** replace redundant values with
     the earlier value (or `not` of it for opposites).
   - **Factoring common terms (DLP 63):** `apply_factor` factors the winning
     value `x` out of `k ≥ 2` single-use `inner`-chain terms of an `outer`-chain
     before match search.
   - **Batching non-overlapping matches and spellings (DLP 64):** apply all
     largest-first non-overlapping standard-operation matches with their first
     spellings, or fix the first better spelling when no match is present.
   - **Associative regrouping (DLP 61):** `regroup_associative` folds the first
     non-canonical single-use associative chain into its canonical left-to-right
     fold.
4. **Phase 4 — Settle wrappers and identity ops (DLPs 59/64):** operations that
   merely return an input view, a constant, or a single standard operation are
   removed and substituted into their callers; unreferenced synthesized
   specialization helpers are pruned.

All four phases are formally proven to terminate in Lean 4
(`boolean_equality_checking/proof/fixing_termination.lean`, theorems
`structural_terminates`, `specialization_terminates`, `fold_loop_terminates`,
`useless_elim_terminates`, `dag_prog_terminates`, and `full_autofix_terminates`,
audited with zero `sorry` and zero custom axioms).

The exact stopping boundary: boolean refactoring stops only when a boolean
literal (written directly or produced by folding a constant expression) is
passed to an opaque non-Boolean Logical Operation (or when a non-Boolean Logical
Operation writes a required unused boolean output view), or when an operation
hits DLP 65 limits, an existing DLP 9 execution cycle, or a 0-output Boolean
Value Operation.

## Measurements and Reasons

All measurements below come from the C++23 reference implementation
(`boolean_equality_checking/src/beq`) with the budget-free canonical ROBDD
architecture, DLP 61 grouping, DLP 63 factoring, and DLP 64's fixed standard set
`{and, not, or, xor, equal}`.

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

### Why DLP 64 Uses Only the Fixed Standard Set (`and`, `not`, `or`, `xor`, `equal`)

Stress-testing `Matcher` on adversarial linear-BDD chains of `S` calls to an
unregistered 3-input operation `u3(a, b, c) = (a and b) xor c` (`I = 2S + 1`,
where nothing matches, so `Matcher` must prove no match exists for every
statement across all `N = I + S` earlier values):

| Statements (`S`) | Inputs (`I`) | Fixed standard set (`and, not, or, xor, equal`) | Arity ≤ 3 (`+ implies, mux, maj`) | With arity-4 XOR-like op (`par4`) |
| ---------------- | ------------ | ----------------------------------------------- | --------------------------------- | --------------------------------- |
| **256**          | **513**      | **0.030 s** (`matches` 11.0 ms, 16 MB RSS)      | 0.11 s                            | **Timeout (> 15 s)**              |
| 512              | 1,025        | **0.078 s** (`matches` 34.6 ms, 16 MB RSS)      | 0.64 s                            | —                                 |
| 1,024            | 2,049        | **0.28 s** (`matches` 135 ms, 17 MB RSS)        | 4.72 s                            | —                                 |
| 2,048            | 4,097        | **1.11 s** (`matches` 560 ms, 28 MB RSS)        | Timeout (> 15 s)                  | —                                 |
| 4,096            | 8,193        | **4.56 s** (`matches` 2.38 s, 56 MB RSS)        | —                                 | —                                 |

Arity-4 XOR-like operations have no forcing prefix until the 4th argument,
giving worst-case `O(S * N^3)` search even on a tiny linear BDD. Arity-3
operations (`mux`, `maj`) scale as `O(S * N^2)`. Restricting DLP 64 to the five
arity-≤-2 symmetric standard operations eliminates backtracking completely,
giving strictly `O(S * (I + S))` search — **30 ms total** (`11 ms` in `matches`)
at the `S = 256, I = 512` limits, while also avoiding per-project boolean
dialects and avoiding `mux` vs. distributive-factoring conflicts.

### Whole-Program and Stress Benchmarks

Checking freshly generated and fixed whole programs with ~20% mixed Value
Operations, DLP 61 grouping, DLP 63 factoring, and DLP 64's fixed standard set
`{and, not, or, xor, equal}` (single-threaded reference binary,
`--bdd_nodes 65536`):

| Program                                            | Total wall time | Peak RSS   | Key breakdown                                                                      |
| -------------------------------------------------- | --------------- | ---------- | ---------------------------------------------------------------------------------- |
| `ops_15k_std` (14,926 ops, ≤ 10 inputs)            | **1.08 s**      | **94 MB**  | ~72 µs/op (`tables` 50 ms, `order` 110 ms, `matches + spellings` 240 ms)           |
| `ops_2k_wide_std` (1,998 ops, mostly 16–20 inputs) | **12.01 s**     | **194 MB** | `tables` 9.54 s (`lookups` 4.98 s via 8×8 transpose), `matches + spellings` 330 ms |

Across all 276 synthetic stress workloads (`work/methods/*.prog`: `dense`,
`xor_heavy`, `parity`, `read_once`, `long` up to 1,024 statements, `real`, and
multipliers up to 28×28) under the **65,536** canonical ROBDD node limit, **276
/ 276** finish cleanly in 22.64 s total with zero timeouts and peak RSS **33.7
MB** (slowest file: `long_22_1024.prog`, 3 ops × 1,024 statements, **1.20 s**).

## Approaches That Didn't Work

### Limits and Budgets

- **A compiler step budget (`StepBudget`).** Counting internal compiler work
  steps (BDD ops, nodes, search steps, sample evals) is unpredictable for
  programmers, tightly coupled to one implementation's internal optimizations,
  and hard to standardize across compilers. The four structural limits plus the
  canonical shared ROBDD reachable-node cap are 100% compiler-independent, easy
  to communicate, and bound both time and memory more cleanly.
- **Project-level registered boolean operations (`booleans.defcl`) and arity ≥ 3
  matching.** Allowing projects to register arbitrary boolean operations of
  arity 3 or 4 introduced three problems at once: (1) an `O(S * N^3)` timeout
  cliff for arity-4 XOR-like ops and `O(S * N^2)` scaling for arity-3 ops
  (`mux`, `maj`); (2) per-project boolean dialects where the same expression
  compiles in one project and fails in another, plus config-wide invalidation
  and cycle-breaking complexity; and (3) conflicts between `mux` matching
  (`mux(b, a, a and c)`) and DLP 63 distributive factoring (`a and (b or c)`).
  Fixing DLP 64 to `{and, not, or, xor, equal}` removes all three problems and
  reduces matching to strictly `O(S * (I + S))`.
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
- **Running associative regrouping before DLP 59 redundancy fixes.** Reordering
  leaves of an unfixed chain like `equal(x, equal(y, not x))` into
  `equal(y, equal(x, not x))` introduces a spurious constant sub-expression
  before redundancy elimination runs. Running `regroup_associative` after DLP
  59, factoring, and DLP 64 avoids spurious constants while preserving
  topological order.
- **Simplifying constant values or replacing unused views with `false`.**
  Propagating constants through callee executions blew up 20–40 statements into
  thousands; constants remain programmer errors, and unused views substitute a
  kept input view instead.

## Open Questions

- **Unused input view when every kept view creates a constant:** e.g.,
  `g(x, y, z) = xor(xor(x, z), xor(y, z)) and x`. The refactoring tool leaves
  this to the programmer; whether it should try substituting another internal
  value is open.
- **One canonical program per function:** fixing always terminates and
  canonicalizes associative chains and distributive common factors, but two
  equivalent Value Operations can still differ in which intermediate shared
  values or helper Value Operations they introduce.
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

### Value Operation Contracts (DLP 66)

When a Value Operation finishes compiling, its Boolean Contract (specified in
DLP 66) exposes everything a caller (another Value Operation or an Action) needs
so callers never re-parse or re-check the callee's body:

1. **Boolean Value Operations (`k ≤ 20` boolean input views, 1 boolean output
   view):**
   - **Canonical boolean function:** stored in whichever representation is most
     compact for callers:
     - Small AIG (`≤ 2^k` nodes for `k ≤ 6`, or `≤ 16k` nodes for `k > 6`),
     - Exact `2^k`-bit truth table (**≤ 128 KB** at `k = 20`, **8 bytes** at
       `k ≤ 6`), and/or
     - Output ROBDD over the `k` input views (mathematically guaranteed **≤
       98,302** non-terminal nodes for any 20-variable function with complement
       edges, and typically tens to hundreds of nodes).
   - **Inferred associative view group (if any, DLP 61):** cached so callers
     check DLP 61 grouping without re-deriving associativity.
   - **Canonical 128-bit function fingerprint:** for `O(1)` equivalence,
     wrapper, and incremental-recompilation checks.
2. **Non-Boolean (mixed) Value Operations:**
   - Do not export Boolean Contracts. By DLP 59, in a non-Boolean Value
     Operation, no boolean output view's Boolean Sources can include a boolean
     input view, and no two boolean output views can share a Boolean Source.
     Every boolean output view it produces is therefore independent as pure
     boolean logic and is exposed to callers as an opaque boolean input (unless
     extended in the future with non-boolean relational contracts).

Because every Value Operation is capped at **≤ 20 boolean input views**, no
separate exported-contract ROBDD node limit is needed: the 20-view cap
mathematically bounds every contract to ≤ 128 KB (truth table) and ≤ 98,302
nodes (ROBDD).

### Action Contracts for Future Whole-Program Boolean Optimization

An Action is not a pure boolean function — it operates on particles in
positions, triggers other Actions, and produces Action Guarantees (including
Action Particle Value Guarantees and Destruction Contracts). To enable future
**whole-program boolean optimizations** across Action boundaries — such as
eliminating dead triggers/branches, folding duplicate Boolean Value Operation
executions across caller/callee boundaries, propagating known flags, or
specializing callees — an Action Contract can summarize boolean behavior over
its **contracted boolean interface positions** (`V` positions) in three
increasing tiers:

1. **Tier 1 — Per-position value, sensitivity, and unchanged-position facts
   (`O(V)` size):**
   - **Constants:** output boolean position `p_out` is guaranteed `true` or
     `false`.
   - **Copies and negations:** `p_out == p_in` or `p_out == not p_in`.
   - **Unchanged positions:** `p` is unchanged by the Action (so callers
     preserve their existing boolean knowledge about `p` across a callee
     trigger).
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
  2 (constants, unchanged-position facts, and the exact 2-SAT implication
  closure)**. Because 2-SAT implication closure over contracted boolean literals
  is unique, canonical, and strictly polynomial, it guarantees cross-compiler
  determinism with no exponential blowup and no heuristic node cap — requiring
  at most a generous bound on contracted boolean interface positions per Action
  (such as `≤ 256`, which caps the implication matrix at 16 KB).
