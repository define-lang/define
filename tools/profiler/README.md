This is a profiler designed specifically to profile the compiler.

We created it ourselves for the reasons described in architecture.md. Probably
once Python 3.15 comes out, we can use Tachyon and throw this away.

This profiler is almost entirely vibe coded from the spec in architecture.md. I
have scanned over the code of it and eliminated particularly egregious errors
and design issues, but I can't attest to its correctness other than that it
seems to be working to produce profiling data, and I can fix it when it's
misbehaving.
