from __future__ import annotations

from typing import TYPE_CHECKING

from tools.bazel_mutation_testing import mutant, results, survivors

if TYPE_CHECKING:
    import pathlib

_RUN = results.Run(
    commit="0123abcd",
    area=["//crates/...", "//define/..."],
    test_timeout=60,
    lint_flags=[],
)
_LIB_PATCH = """\
--- a/crates/example/lib.rs
+++ b/crates/example/lib.rs
@@ -5 +5 @@
-    a > b
+    a >= b
"""
_DOC_PATCH = """\
--- a/crates/example/lib.rs
+++ b/crates/example/lib.rs
@@ -1,3 +1,3 @@
 /// ```
 /// assert!(is_small(1));
-/// ```
+/// ```text
"""
_PY_PATCH = """\
--- a/define/example.py
+++ b/define/example.py
@@ -2 +2 @@
-    return 1
+    return 2
"""
_MUTANTS = [
    mutant.Mutant(
        name="define/example.py:2:12: replace 1 with 2",
        path="define/example.py",
        patch=_PY_PATCH,
        lines=(2, 2),
    ),
    mutant.Mutant(
        name="define/example.py:2:12: replace 1 with 0",
        path="define/example.py",
        patch=_PY_PATCH,
        lines=(2, 2),
    ),
    mutant.Mutant(
        name="crates/example/lib.rs:5:7: replace > with >=",
        path="crates/example/lib.rs",
        patch=_LIB_PATCH,
        lines=(5, 5),
    ),
    mutant.Mutant(
        name="crates/example/lib.rs:5:7: replace > with ==",
        path="crates/example/lib.rs",
        patch=_LIB_PATCH,
        lines=(5, 5),
    ),
    mutant.Mutant(
        name="crates/example/lib.rs:3:5: replace doc fence",
        path="crates/example/lib.rs",
        patch=_DOC_PATCH,
        lines=(3, 3),
    ),
]
_OUTCOMES = {
    "define/example.py:2:12: replace 1 with 0": results.Result(
        name="define/example.py:2:12: replace 1 with 0",
        outcome=results.Outcome.OUT_OF_MEMORY,
        culprit="//define:example_test",
        seconds=12.5,
    ),
    "define/example.py:2:12: replace 1 with 2": results.Result(
        name="define/example.py:2:12: replace 1 with 2",
        outcome=results.Outcome.TIMED_OUT,
        culprit="//define:example_test",
        seconds=60.5,
    ),
    "crates/example/lib.rs:5:7: replace > with >=": results.Result(
        name="crates/example/lib.rs:5:7: replace > with >=",
        outcome=results.Outcome.SURVIVED,
        culprit=None,
        seconds=3.0,
        covering_tests=0,
    ),
    "crates/example/lib.rs:5:7: replace > with ==": results.Result(
        name="crates/example/lib.rs:5:7: replace > with ==",
        outcome=results.Outcome.KILLED,
        culprit="//crates/example:example_test",
        seconds=1.0,
    ),
    "crates/example/lib.rs:3:5: replace doc fence": results.Result(
        name="crates/example/lib.rs:3:5: replace doc fence",
        outcome=results.Outcome.SURVIVED,
        culprit=None,
        seconds=2.0,
    ),
}
_EXPECTED = f"""\
# Mutation Testing Survivors

- Commit: `0123abcd`
- Area: `//crates/... //define/...`
- Mutants: 5: 1 killed, 2 survived, 1 timed out, 1 ran out of memory

## crates/example/lib.rs

### crates/example/lib.rs:5:7: replace > with >=

No test runs this code.

```diff
{_LIB_PATCH}```

### crates/example/lib.rs:3:5: replace doc fence

````diff
{_DOC_PATCH}````

## define/example.py

### define/example.py:2:12: replace 1 with 2

Timed out: //define:example_test

```diff
{_PY_PATCH}```

### define/example.py:2:12: replace 1 with 0

Ran out of memory: //define:example_test

```diff
{_PY_PATCH}```
"""


def test_render_lists_survivors_and_limit_kills_by_file():
    assert survivors.render(_RUN, _MUTANTS, _OUTCOMES) == _EXPECTED


def test_write_creates_the_report(tmp_path: pathlib.Path):
    path = tmp_path / "reports/survivors.md"
    survivors.write(path, _RUN, _MUTANTS, _OUTCOMES)
    assert path.read_text(encoding="utf-8") == _EXPECTED
