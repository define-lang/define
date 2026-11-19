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
