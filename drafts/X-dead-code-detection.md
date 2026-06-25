We can detect local dead code very easily.

Dead interface positions come two ways: (1) never used inside the action (2)
never interacted with in the outside. Actually, needs to always be "never used
inside the action" to avoid people using actions as containers.

We can also check dead locals. "Never referenced" is the easiest.

Dead quality implications are very easy to check.

Constraints on a local that are not directly referenced in the action and are
not required for moves.

Dead constraints are harder but theoretically possible as we DFS walk postorder,
or maybe even during the forward pass.
