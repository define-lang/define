We can detect local dead code very easily.

Dead interface positions come two ways: (1) never used inside the action (2)
never interacted with in the outside.

Dead quality implications are very easy to check.

Dead constraints are harder but theoretically possible as we DFS walk postorder,
or maybe even during the forward pass.
