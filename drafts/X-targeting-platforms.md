There has to be some way to say "on this OS, we use this operation, but on this
other OS (or hardware) we use this different operation."

My suspicion is that what we actually want here is a config value per choice we
have to make, and then each target platform chooses how to set those config
values.

## Choosing Encodings for a Whole Program

From DLP 47:

Also, there might be situations in which a programmer genuinely _does_ want to
change the encoding used across an entire program, or in a particular
compilation. For example, they might be sometimes compiling for a Google TPU and
want to change _all_ floats in the program to use the TPU's `bfloat` encoding,
but other times are compiling for a CPU and want to use IEEE 754 for that CPU,
regardless of what "preference" a library has for how to represent an encoding.

We may also allow a compiler flag to swap out an encoding for the whole program.

## Encoding Conflicts

From DLP 47:

A future proposal will create the ability to configure _compilation targets_,
which will allow for configuring how Define performs code generation for
particular target architectures, OSes, etc. Any conflict resolution system will
happen in _that_ configuration. That is, any conflicts that occur between
encodings are decided by the target configuration. However, the target
configuration in general should only attempt to resolve conflicts, not allow for
explicit specification of encodings, because explicit specifications override
the compiler's ability to optimize.

The goal here will be to allow libraries to compile according to their own
configurations to the degree possible, but the actual current project being
compiled will determine the overall behavior when there are conflicts.

Note that this plan means that Define's compiled representation when compiling a
library intended for consumption may need to be an IR that has not yet resolved
its encodings, rather than machine code or fully-resolved operations.

If the compiler does not have such a target config and there are conflicting
encodings that would be valid for a concrete value, the compiler will throw an
error at compile time.

Since we currently ban redefining encodings and values in libraries, this would
currently be a rare occurrence (a library author would have to, themselves,
create this conflict) but it could still happen, and the system is worth
recording for posterity if and when we do allow extensions.

Note that a library newly introducing such a conflict would be a
forward-compatibility issue and they would have to provide refactoring tools or
default choices for their consumers when making this change.
