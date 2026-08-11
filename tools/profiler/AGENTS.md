# Profiler Test Profiles

The JSONL files in `testdata/` are checked-in raw profiles used to test analyzer
interpretation without depending on live kernel scheduling in ordinary tests.

Regenerate every checked-in profile with:

```shell
bazelisk run --noshow_progress --ui_event_filters=-info //tools/profiler:regenerate_test_profiles
```

Run the command after changing the raw-profile schema, capture semantics,
critical-path analysis inputs, any corresponding `testdata/*_target.py` file,
the compiler fixture workload, or the Python toolchain. Review the JSONL diff
before accepting it, then run `//tools/profiler:profiler_test` and
`//tools/profiler:compiler_profile_test`.

Fixture targets must coordinate phases through file descriptors or FIFOs. Do not
add sleeps, elapsed-time deadlines, or fixed CPU-time workloads. The regenerator
samples a bounded number of persisted observations per phase and validates that
each captured profile contains the evidence its test requires.
