Need to be able to detect entirely dead files, optionally.

Clear out dead particles.

Dead guarantees---ones the caller never interacts with.

An implied position that is only referenced by a single action must be an
interface position.

Useless trigger positions: never interacted with and there are other interface
positions that _are_ interacted with. Especially important when there is only
one other interface position.

We could _maybe_ track action liveness through output positions modularly in a
way similar to Destruction Contracts. It might involve some complex bookkeeping.
