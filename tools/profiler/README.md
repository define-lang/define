Profiling tools for the Define compiler, used through `tools/run_profile.py` and
`tools/analyze_profile.py`. They exist for an agent profiling the compiler: they
keep the analysis an agent would otherwise script each time.

Wall profiles are captured by Tachyon, CPython's sampling profiler, which stops
every thread for each sample and records each thread's Python stack and status.
The analyzer turns those samples into a timeline of each thread: runs of work
and waiting labeled by their innermost compiler frames, from which the critical
path of a compile can be read. A thread is working while it holds its Python
thread state and waiting while it has released it, such as in a lock, a queue,
or I/O, so native code that releases its thread state counts as waiting. Most
failed samples happen while the interpreter shuts down.

CPU profiles are captured by Linux perf with CPython's perf trampolines, which
show native frames as well as Python ones. Capture writes perf's collapsed
stacks, one line per distinct stack and thread with its sample count, while
CPython's perf symbol map still exists to name the Python frames.

For either kind, the analyzer prints function tables and call trees over a
selection of threads and, for wall profiles, a time window, optionally starting
each stack at one function, so that a phase found in the timeline can be
explained by the functions it spends its time in.

The analysis code is almost entirely vibe coded. I have scanned over it and
eliminated particularly egregious errors and design issues, but I can't attest
to its correctness other than that it seems to produce useful reports, and I can
fix it when it's misbehaving.
