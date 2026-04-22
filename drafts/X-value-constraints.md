### 5: Logical Properties of Operations

In a language like Define that strives for verification, we have to know: when
you execute an operation, what guarantees does it provide? What requirements
does it have? Can the compiler safely re-order it or turn it into a vector
instruction in the CPU? How does it deal with different types of inputs?

We have to know this at the level of the _logical_ operation, not the physical
operation, because we have to be able to prove properties about the logical
operation.
