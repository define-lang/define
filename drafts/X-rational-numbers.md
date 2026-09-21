### Integers vs Rationals

Define chooses _not_ to have a separate integer type, and to instead use
constraints (as described in a later proposal) to declare that a rational number
must be an integer.

### Integers vs Rationals

One interesting question is: does this mean that you need separate integer types
from rational types? For addition and subtraction, they behave identically, if
you consider an integer to be a rational number with a denominator of 1.
Division, on the other hand, has important differences in hardware, since
integer division rounds toward zero on every platform that I'm aware of.

I think the division problem is _probably_ solved by having a rational operation
that allows for round-to-zero division. Generally, this round-to-zero behavior
of other programming languages is a frequent source of bugs for unsuspecting
programmers, because they didn't specify explicitly that the program should do
that, they just wrote `3 / 2` and got `1`.

The tricky piece here is that exact rational math leads to fixed-point
calculations that are slow on most hardware, and it would be easy for
programmers to get themselves into a bad place by choosing to use rationals all
the time, unknowingly. However, we also could choose to automatically use
floating point operations wherever we could prove that the hardware produced
exact results, which should be possible with constraints and type inference.

The compiler must establish that both the stored values and the operations
performed on them preserve the required behavior. Exactly representable operands
alone aren’t sufficient: 1 and 3 are exact in binary floating point, but their
quotient isn’t.

For example, bounded integers or bounded multiples of 1/8 can fit exactly in
binary floating point. Operations whose exact results also fit can use
floating-point instructions without introducing approximation.
