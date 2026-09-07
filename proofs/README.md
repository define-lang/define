# Proofs

This directory contains formal proofs of important parts of Define that are
complex and important enough to justify such work.

Note that these proofs are primarily written by AI agents. Although the proof
criteria is guided by humans, and humans do light reviews on the English-text
proofs, there is still a chance that the agent has created a proof that is
vacuous, too narrow, etc.

We use these proofs primarily as an _assistance_ to correct behavior in the
compiler, not as a mathematical foundation for Define itself. We still rely on
our tests to find counterexamples and check compiler behavior in real-world
situations. The proofs are also helpful to discover counter-examples.

Rigorous analysis and verification by more experienced humans would be welcome.

The language specification is authoritative for Define terminology. Mathematical
objects use standard mathematical terms where applicable.

## Building proofs

Bazel downloads the Lean toolchain declared by `lean-toolchain` and the Lake
dependencies pinned in `lake-manifest.json`. `lakefile.lean` declares mathlib;
Bazel's Lake integration obtains the compiled modules needed by the proofs. To
compile the proofs, run:

```console
bazelisk build //proofs/...
```

Lean rejects invalid terms, every emitted warning is treated as an error, and
the Bazel rule also rejects any proof containing an admitted goal such as
`sorry`.
