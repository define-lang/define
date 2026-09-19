## Bend research

match is its core branching construct. The attraction is that it handles
selection while also giving the checker useful structural information:

- It identifies the alternatives and exposes their data. Matching a list
  distinguishes an empty list from a head and tail. The compiler can check that
  every possible case is covered.

- Each alternative supplies facts. In the empty-list case, the compiler knows
  the list is empty. In the other case, it knows the list consists of that head
  and tail. Bend uses those facts to specialize the proposition being proved.

- It exposes progress for recursion. The tail is structurally smaller than the
  original list, giving the termination checker an immediately recognizable
  reason that recursion progresses.

There is one semantic distinction from a plain value-select function: a match
chooses which branch’s computation to execute. Passing f() and g() to an
ordinary eager select computes both before selection. Equivalent conditional
execution needs alternatives whose computation is deferred.
