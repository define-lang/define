# Proofs

This directory contains formal proofs of important parts of Define that are
complex and important enough to justify such work.

Note that these proofs are primarily written by AI agents. Although the proof
criteria is guided by humans, and humans do light reviews on the English-text
proofs, there is still a chance that the agent has created a proof that is
vacuous, too narrow, etc.

We use these proofs primarily as an _assistance_ to correct behavior in the
compiler, not as a mathematical foundation for Define itself. We still rely
primarily on our tests to find counterexamples and guarantee correctness in
real-world situations. However, the proofs are often helpful to discover
counter-examples.

Rigorous analysis and verification by more experienced humans would be welcome.

Since these are written by AI, none of the language in this directory is
canonical; the terms used to describe things are not necessarily valid Define
terms.

## Building proofs

Bazel downloads the Lean toolchain declared by `lean-toolchain`. To compile the
proofs, run:

```console
bazelisk build //proofs/...
```

Lean rejects invalid terms, and the Bazel rule also rejects any proof containing
an admitted goal such as `sorry`.
