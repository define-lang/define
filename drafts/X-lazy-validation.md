Syntax is validated eagerly, but semantics are validated lazily.

It solves dead code and libraries breaking you even when you don't use some part
of them.

Non-validated code must never be in the compiled output and cannot affect the
behavior of the program.

Also we try to provide users with as many validation errors as possible. Problem
is annoying iteration.
