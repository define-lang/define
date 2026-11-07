# Profiler Test Profiles

The `.bin` file in `testdata/` is a checked-in Tachyon profile used to test the
wall timeline without depending on live thread scheduling in ordinary tests.

Regenerate every checked-in profile with:

```shell
bazelisk run --noshow_progress --ui_event_filters=-info //tools/profiler:regenerate_test_profiles
```

Run the command after changing how Tachyon is invoked, what the timeline reads
from a profile, `testdata/critical_path_target.py`, or the Python toolchain.

Fixture targets must coordinate phases through file descriptors or FIFOs, not
elapsed time or fixed CPU-time workloads. Tachyon reports no sampling progress,
so the regenerator holds each phase open for a fixed time, then validates that
each captured profile contains the evidence its test requires and retries the
capture if it does not.
