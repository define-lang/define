But here's one that also catches associativity and commutativity: every node is
an `and` of a _set_ of literals, where a literal is a node plus whether it's
inverted (`a` or `not a`). The compiler keeps one table of every node it has
built, and building a node that already exists returns the existing one
(hash-consing). Every node is built with these rules, in this order:

1. **Flatten:** an input that is itself an `and`, used without inversion,
   contributes its literals instead of itself.
2. **Sort and remove duplicates:** the literals are sorted by node, so `a and a`
   becomes `a`.
3. **Contradictions:** a set that holds both `x` and `not x` is false.
4. **Constants:** true drops out, and false makes the whole node false.
5. **Single literals:** an `and` of just `x` is `x`.

`not (not x)` is `x` without a rule, because `not` is a mark, not a node. Then
two compositions that differ only by associativity, commutativity, duplicates,
contradictions, or constants produce the same literal, and comparing them takes
constant time. De Morgan's law needs no rule either, because with only `and` and
`not`, "or" can only be written one way: `not (not a and not b)`.

The one choice is what rule 1 does with a node that's used more than once.
Flattening it everywhere makes the form canonical for everything above, but it
copies the shared node into every place that uses it, which is quadratic in the
worst case. Flattening only nodes that are used once keeps the size linear, but
then two compositions only match when they share the same nodes. Within one
value operation, which is small, flattening everything is cheap.
