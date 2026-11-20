from __future__ import annotations

from typing import TYPE_CHECKING

from tools.bazel_mutation_testing.python import generator

if TYPE_CHECKING:
    import pathlib

_PATH = "pkg/lib.py"
_SOURCE = '''\
"""Example."""

LIMIT = 10


def is_larger(left: int, right: int) -> bool:
    return left > right


class Box:
    """A box."""

    def first(self) -> int:
        return 1

    def second(self) -> str:
        return "a"
'''


def _workspace(tmp_path: pathlib.Path, source: str = _SOURCE) -> pathlib.Path:
    workspace = tmp_path / "workspace"
    path = workspace / _PATH
    path.parent.mkdir(parents=True)
    _ = path.write_text(source, encoding="utf-8", newline="\n")
    return workspace


def _list_mutants(workspace: pathlib.Path):
    return generator.list_mutants(
        [_PATH], workspace=workspace, tracked_paths=frozenset({_PATH})
    )


def test_mutants_of_functions_and_methods(tmp_path: pathlib.Path):
    mutants = _list_mutants(_workspace(tmp_path))
    assert [listed.name for listed in mutants] == [
        "pkg/lib.py:7:16: replace > right with >= right "
        + "(pkg.lib.x_is_larger__mutmut_1)",
        "pkg/lib.py:14:16: replace 1 with 2 (pkg.lib.xǁBoxǁfirst__mutmut_1)",
        'pkg/lib.py:17:16: replace "a" with "XXaXX" (pkg.lib.xǁBoxǁsecond__mutmut_1)',
        'pkg/lib.py:17:16: replace "a" with "A" (pkg.lib.xǁBoxǁsecond__mutmut_2)',
    ]


def test_patches_apply_at_the_workspace_top(tmp_path: pathlib.Path):
    workspace = _workspace(tmp_path)
    mutants = _list_mutants(workspace)
    mutants[2].apply(workspace)
    assert (workspace / _PATH).read_text(encoding="utf-8") == _SOURCE.replace(
        'return "a"', 'return "XXaXX"'
    )


def test_method_patch_changes_only_its_line(tmp_path: pathlib.Path):
    mutants = _list_mutants(_workspace(tmp_path))
    assert mutants[1].patch == (
        "--- a/pkg/lib.py\n"
        + "+++ b/pkg/lib.py\n"
        + "@@ -11,7 +11,7 @@\n"
        + '     """A box."""\n'
        + " \n"
        + "     def first(self) -> int:\n"
        + "-        return 1\n"
        + "+        return 2\n"
        + " \n"
        + "     def second(self) -> str:\n"
        + '         return "a"\n'
    )


def test_lines_with_a_no_mutate_pragma(tmp_path: pathlib.Path):
    workspace = _workspace(
        tmp_path, _SOURCE.replace("return 1", "return 1  # pragma: no mutate")
    )
    assert [listed.path for listed in _list_mutants(workspace)] == [_PATH] * 3


def test_untracked_files_have_no_mutants(tmp_path: pathlib.Path):
    workspace = _workspace(tmp_path)
    assert (
        generator.list_mutants(
            [_PATH, "pkg/other.py"], workspace=workspace, tracked_paths=frozenset()
        )
        == []
    )


def test_names_of_long_replacements_show_the_change(tmp_path: pathlib.Path):
    source = (
        "def describe(first_value: int, second_value: int) -> str:\n"
        + '    return combine(first_value, second_value, separator="a long separator")\n'
    )
    mutants = _list_mutants(_workspace(tmp_path, source=source))
    assert [listed.name for listed in mutants[1:3]] == [
        "pkg/lib.py:2:12: replace "
        + '...e(first_value, second_value, separator="a... '
        + 'with ...e(first_value, None, separator="a... '
        + "(pkg.lib.x_describe__mutmut_2)",
        "pkg/lib.py:2:12: replace "
        + '...lue, separator="a long separator") with ...lue, separator=None) '
        + "(pkg.lib.x_describe__mutmut_3)",
    ]


def test_mutants_that_no_test_could_tell_apart_are_skipped(tmp_path: pathlib.Path):
    source = """\
def check(value: int) -> int:
    found = False
    if value < 0:
        raise ValueError("negative")
    return value
"""
    mutants = _list_mutants(_workspace(tmp_path, source))
    # mutmut's first mutant sets `found` to None, and its mutants after the
    # fourth change the raised exception.
    assert [listed.name for listed in mutants] == [
        "pkg/lib.py:2:13: replace False with True (pkg.lib.x_check__mutmut_2)",
        "pkg/lib.py:3:13: replace < 0 with <= 0 (pkg.lib.x_check__mutmut_3)",
        "pkg/lib.py:3:16: replace 0 with 1 (pkg.lib.x_check__mutmut_4)",
    ]


def test_changes_to_the_type_of_a_cast_are_skipped(tmp_path: pathlib.Path):
    source = """\
import typing
from typing import cast


def convert(value: object) -> int:
    first = cast("int", value)
    return typing.cast("int", first)
"""
    mutants = _list_mutants(_workspace(tmp_path, source))
    # mutmut's mutants 2, 6 to 8, 12 and 13 change only the type.
    assert [listed.name for listed in mutants] == [
        'pkg/lib.py:6:5: replace first = cast("int", value) with first = None '
        + "(pkg.lib.x_convert__mutmut_1)",
        'pkg/lib.py:6:13: replace cast("int", value) with cast("int", None) '
        + "(pkg.lib.x_convert__mutmut_3)",
        'pkg/lib.py:6:13: replace cast("int", value) with cast(value) '
        + "(pkg.lib.x_convert__mutmut_4)",
        'pkg/lib.py:6:13: replace cast("int", value) with cast("int", ) '
        + "(pkg.lib.x_convert__mutmut_5)",
        'pkg/lib.py:7:12: replace typing.cast("int", first) with '
        + 'typing.cast("int", None) (pkg.lib.x_convert__mutmut_9)',
        'pkg/lib.py:7:12: replace typing.cast("int", first) with '
        + "typing.cast(first) (pkg.lib.x_convert__mutmut_10)",
        'pkg/lib.py:7:12: replace typing.cast("int", first) with '
        + 'typing.cast("int", ) (pkg.lib.x_convert__mutmut_11)',
    ]


def test_removed_match_arms_that_only_raise_are_skipped(tmp_path: pathlib.Path):
    source = """\
def describe(value: object) -> object:
    match value:
        case int():
            raise TypeError
        case str():
            return value
    return None
"""
    mutants = _list_mutants(_workspace(tmp_path, source))
    # mutmut's first mutant removes the arm that raises.
    assert [listed.name for listed in mutants] == [
        "pkg/lib.py:2:5: replace ...raise TypeError case str(): return value "
        + "with ...raise TypeError (pkg.lib.x_describe__mutmut_2)",
    ]


def test_removed_last_match_arms_that_do_nothing_are_skipped(
    tmp_path: pathlib.Path,
):
    source = """\
def describe(value: object) -> object:
    match value:
        case None:
            pass
        case bytes():
            return value
        case float():
            pass
    match value:
        case list():
            return value
        case other:
            pass
    return other
"""
    mutants = _list_mutants(_workspace(tmp_path, source))
    # mutmut's third mutant removes the `case float()` arm. The `case None` arm
    # is not the last arm, and the `case other` arm binds a name.
    assert [listed.name for listed in mutants] == [
        "pkg/lib.py:2:5: replace ...ch value: case None: pass case bytes(): "
        + "return... with ...ch value: case bytes(): return... "
        + "(pkg.lib.x_describe__mutmut_1)",
        "pkg/lib.py:2:5: replace ...one: pass case bytes(): return value "
        + "case float(): pass with ...one: pass case float(): pass "
        + "(pkg.lib.x_describe__mutmut_2)",
        "pkg/lib.py:9:5: replace match value: case list(): return value "
        + "case other: pass with match value: case other: pass "
        + "(pkg.lib.x_describe__mutmut_4)",
        "pkg/lib.py:9:5: replace match value: case list(): return value "
        + "case other: pass with match value: case list(): return value "
        + "(pkg.lib.x_describe__mutmut_5)",
    ]


def test_removed_default_arguments_and_lenient_zips_are_skipped(
    tmp_path: pathlib.Path,
):
    source = """\
import subprocess


def pair(left: list[int], right: list[int]) -> list[tuple[int, int]]:
    _ = subprocess.run(["true"], check=False)
    _ = zip(left, right, strict=False)
    return zip(left, right, strict=True)
"""
    mutants = _list_mutants(_workspace(tmp_path, source))
    # mutmut's mutants 5, 15 and 22 remove `check` or `strict`, and its
    # mutant 23 changes `strict=True` to `strict=False`.
    assert [listed.name for listed in mutants] == [
        'pkg/lib.py:5:5: replace _ = subprocess.run(["true"], check=False) '
        + "with _ = None (pkg.lib.x_pair__mutmut_1)",
        'pkg/lib.py:5:9: replace subprocess.run(["true"], check=False) with '
        + "subprocess.run(None, check=False) (pkg.lib.x_pair__mutmut_2)",
        'pkg/lib.py:5:9: replace subprocess.run(["true"], check=False) with '
        + 'subprocess.run(["true"], check=None) (pkg.lib.x_pair__mutmut_3)',
        'pkg/lib.py:5:9: replace subprocess.run(["true"], check=False) with '
        + "subprocess.run(check=False) (pkg.lib.x_pair__mutmut_4)",
        'pkg/lib.py:5:25: replace "true" with "XXtrueXX" '
        + "(pkg.lib.x_pair__mutmut_6)",
        'pkg/lib.py:5:25: replace "true" with "TRUE" (pkg.lib.x_pair__mutmut_7)',
        "pkg/lib.py:5:40: replace False with True (pkg.lib.x_pair__mutmut_8)",
        "pkg/lib.py:6:5: replace _ = zip(left, right, strict=False) with "
        + "_ = None (pkg.lib.x_pair__mutmut_9)",
        "pkg/lib.py:6:9: replace zip(left, right, strict=False) with "
        + "zip(None, right, strict=False) (pkg.lib.x_pair__mutmut_10)",
        "pkg/lib.py:6:9: replace zip(left, right, strict=False) with "
        + "zip(left, None, strict=False) (pkg.lib.x_pair__mutmut_11)",
        "pkg/lib.py:6:9: replace zip(left, right, strict=False) with "
        + "zip(left, right, strict=None) (pkg.lib.x_pair__mutmut_12)",
        "pkg/lib.py:6:9: replace zip(left, right, strict=False) with "
        + "zip(right, strict=False) (pkg.lib.x_pair__mutmut_13)",
        "pkg/lib.py:6:9: replace zip(left, right, strict=False) with "
        + "zip(left, strict=False) (pkg.lib.x_pair__mutmut_14)",
        "pkg/lib.py:6:33: replace False with True (pkg.lib.x_pair__mutmut_16)",
        "pkg/lib.py:7:12: replace zip(left, right, strict=True) with "
        + "zip(None, right, strict=True) (pkg.lib.x_pair__mutmut_17)",
        "pkg/lib.py:7:12: replace zip(left, right, strict=True) with "
        + "zip(left, None, strict=True) (pkg.lib.x_pair__mutmut_18)",
        "pkg/lib.py:7:12: replace zip(left, right, strict=True) with "
        + "zip(left, right, strict=None) (pkg.lib.x_pair__mutmut_19)",
        "pkg/lib.py:7:12: replace zip(left, right, strict=True) with "
        + "zip(right, strict=True) (pkg.lib.x_pair__mutmut_20)",
        "pkg/lib.py:7:12: replace zip(left, right, strict=True) with "
        + "zip(left, strict=True) (pkg.lib.x_pair__mutmut_21)",
    ]


def test_case_changes_of_codec_names_are_skipped(tmp_path: pathlib.Path):
    source = """\
def encode(text: str, codec: str) -> bytes:
    if codec == "ascii":
        return text.encode("ascii")
    return text.encode(encoding="utf-8")
"""
    mutants = _list_mutants(_workspace(tmp_path, source))
    # mutmut's mutants 6 and 9 change the case of a codec name. The `"ascii"`
    # that `codec` is compared with is not a codec name.
    assert [listed.name for listed in mutants] == [
        'pkg/lib.py:2:13: replace == "ascii" with != "ascii" '
        + "(pkg.lib.x_encode__mutmut_1)",
        'pkg/lib.py:2:17: replace "ascii" with "XXasciiXX" '
        + "(pkg.lib.x_encode__mutmut_2)",
        'pkg/lib.py:2:17: replace "ascii" with "ASCII" '
        + "(pkg.lib.x_encode__mutmut_3)",
        'pkg/lib.py:3:16: replace text.encode("ascii") with text.encode(None) '
        + "(pkg.lib.x_encode__mutmut_4)",
        'pkg/lib.py:3:28: replace "ascii" with "XXasciiXX" '
        + "(pkg.lib.x_encode__mutmut_5)",
        'pkg/lib.py:4:12: replace text.encode(encoding="utf-8") with '
        + "text.encode(encoding=None) (pkg.lib.x_encode__mutmut_7)",
        'pkg/lib.py:4:33: replace "utf-8" with "XXutf-8XX" '
        + "(pkg.lib.x_encode__mutmut_8)",
    ]
