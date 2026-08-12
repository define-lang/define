This is a profiler designed specifically to profile the compiler.

We created it ourselves for the reasons described in architecture.md. Probably
once Python 3.15 comes out, we can use Tachyon and throw this away.

This profiler is almost entirely vibe coded from the spec in architecture.md. I
have scanned over the code of it and eliminated particularly egregious errors
and design issues, but I can't attest to its correctness other than that it
seems to be working to produce profiling data, and I can fix it when it's
misbehaving.

Wall capture also attempts to record `sched_waking` and `sched_wakeup_new`
through Linux perf. Those records carry no attribution weight; they identify the
waking and woken threads so the analyzer can replace temporal handoff guesses
with direct scheduler evidence. The analyzer reports
`sampled-transition inference` when the host's tracefs permissions or
`perf_event_paranoid` setting do not permit scheduler tracepoints.
