# pyright: reportUnusedCallResult=false

from pathlib import Path, PurePosixPath

import pytest

from define.compiler import diagnostics
from define.compiler.validator import program_validator
from define.compiler.validator.program_validator_tests import test_helpers
from define.compiler.validator.program_validator_tests.conftest import ValidateProject

_PARENT = "mv:define-lang.org:parent"
_CHILD = "mv:define-lang.org:child"


def _write_source(tmp_path: Path, rel_path: str, source: str) -> None:
    path = tmp_path / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def _setup_cross_fqun(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    test_helpers.write_project_config(tmp_path, _PARENT)
    test_helpers.write_local_deps_config(tmp_path, {_CHILD: "lib"})
    test_helpers.write_sub_root(tmp_path, "lib", _CHILD)
    monkeypatch.chdir(tmp_path)


def test_cross_fqun_local_to_local_satisfies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _setup_cross_fqun(tmp_path, monkeypatch)
    _write_source(
        tmp_path,
        "lib/x.def",
        f"define the potential position<{_CHILD}:/x>.\n",
    )
    _write_source(
        tmp_path,
        "test.def",
        (
            f"define the potential action<{_PARENT}:/test> {{\n"
            f"    define the position<run>.\n"
            f"    it happens when {{\n"
            f"        the position<run> has a dimension point.\n"
            f"    }} and it does {{\n"
            f"        define the position<from_pos> {{\n"
            f"            it may only contain dimension points where {{\n"
            f"                it has the position<{_CHILD}:/x>.\n"
            f"            }}\n"
            f"        }}\n"
            f"        define the position<to_pos> {{\n"
            f"            it may only contain dimension points where {{\n"
            f"                it has the position<{_CHILD}:/x>.\n"
            f"            }}\n"
            f"        }}\n"
            f"        create a dimension point in position<from_pos>.\n"
            f"        move the dimension point in position<from_pos> to position<to_pos>.\n"
            f"    }}\n"
            f"}}\n"
        ),
    )
    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def")
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert all_diags == []


def test_cross_fqun_local_to_local_violates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _setup_cross_fqun(tmp_path, monkeypatch)
    _write_source(
        tmp_path,
        "lib/x.def",
        f"define the potential position<{_CHILD}:/x>.\n",
    )
    _write_source(
        tmp_path,
        "lib/y.def",
        f"define the potential position<{_CHILD}:/y>.\n",
    )
    _write_source(
        tmp_path,
        "test.def",
        (
            f"define the potential action<{_PARENT}:/test> {{\n"
            f"    define the position<run>.\n"
            f"    it happens when {{\n"
            f"        the position<run> has a dimension point.\n"
            f"    }} and it does {{\n"
            f"        define the position<from_pos> {{\n"
            f"            it may only contain dimension points where {{\n"
            f"                it has the position<{_CHILD}:/x>.\n"
            f"            }}\n"
            f"        }}\n"
            f"        define the position<to_pos> {{\n"
            f"            it may only contain dimension points where {{\n"
            f"                it has the position<{_CHILD}:/y>.\n"
            f"            }}\n"
            f"        }}\n"
            f"        create a dimension point in position<from_pos>.\n"
            f"        move the dimension point in position<from_pos> to position<to_pos>.\n"
            f"    }}\n"
            f"}}\n"
        ),
    )
    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def")
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].missing_qualities == [
        f"position<{_CHILD}:/y>",
    ]


def test_cross_fqun_local_to_chained_satisfies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _setup_cross_fqun(tmp_path, monkeypatch)
    _write_source(
        tmp_path,
        "lib/x.def",
        (
            f"define the potential position<{_CHILD}:/x> {{\n"
            f"    it may only contain dimension points where {{\n"
            f"        it has the position</y>.\n"
            f"    }}\n"
            f"}}\n"
        ),
    )
    _write_source(
        tmp_path,
        "lib/y.def",
        f"define the potential position<{_CHILD}:/y>.\n",
    )
    _write_source(
        tmp_path,
        "test.def",
        (
            f"define the potential action<{_PARENT}:/test> {{\n"
            f"    define the position<run>.\n"
            f"    it happens when {{\n"
            f"        the position<run> has a dimension point.\n"
            f"    }} and it does {{\n"
            f"        define the position<from_pos> {{\n"
            f"            it may only contain dimension points where {{\n"
            f"                it has the position<{_CHILD}:/y>.\n"
            f"            }}\n"
            f"        }}\n"
            f"        define the position<dest> {{\n"
            f"            it may only contain dimension points where {{\n"
            f"                it has the position<{_CHILD}:/x>.\n"
            f"            }}\n"
            f"        }}\n"
            f"        create a dimension point in position<from_pos>.\n"
            f"        move the dimension point in position<from_pos> to position<dest>::position<{_CHILD}:/x>.\n"
            f"    }}\n"
            f"}}\n"
        ),
    )
    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def")
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert all_diags == []


def test_cross_fqun_local_to_chained_violates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _setup_cross_fqun(tmp_path, monkeypatch)
    _write_source(
        tmp_path,
        "lib/x.def",
        (
            f"define the potential position<{_CHILD}:/x> {{\n"
            f"    it may only contain dimension points where {{\n"
            f"        it has the position</y>.\n"
            f"    }}\n"
            f"}}\n"
        ),
    )
    _write_source(
        tmp_path,
        "lib/y.def",
        f"define the potential position<{_CHILD}:/y>.\n",
    )
    _write_source(
        tmp_path,
        "test.def",
        (
            f"define the potential action<{_PARENT}:/test> {{\n"
            f"    define the position<run>.\n"
            f"    it happens when {{\n"
            f"        the position<run> has a dimension point.\n"
            f"    }} and it does {{\n"
            f"        define the position<from_pos>.\n"
            f"        define the position<dest> {{\n"
            f"            it may only contain dimension points where {{\n"
            f"                it has the position<{_CHILD}:/x>.\n"
            f"            }}\n"
            f"        }}\n"
            f"        create a dimension point in position<from_pos>.\n"
            f"        move the dimension point in position<from_pos> to position<dest>::position<{_CHILD}:/x>.\n"
            f"    }}\n"
            f"}}\n"
        ),
    )
    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def")
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].missing_qualities == [
        f"position<{_CHILD}:/y>",
    ]


def test_cross_fqun_chained_to_local_satisfies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _setup_cross_fqun(tmp_path, monkeypatch)
    _write_source(
        tmp_path,
        "lib/x.def",
        (
            f"define the potential position<{_CHILD}:/x> {{\n"
            f"    it may only contain dimension points where {{\n"
            f"        it has the position</y>.\n"
            f"    }}\n"
            f"}}\n"
        ),
    )
    _write_source(
        tmp_path,
        "lib/y.def",
        f"define the potential position<{_CHILD}:/y>.\n",
    )
    _write_source(
        tmp_path,
        "test.def",
        (
            f"define the potential action<{_PARENT}:/test> {{\n"
            f"    define the position<run>.\n"
            f"    it happens when {{\n"
            f"        the position<run> has a dimension point.\n"
            f"    }} and it does {{\n"
            f"        define the position<src> {{\n"
            f"            it may only contain dimension points where {{\n"
            f"                it has the position<{_CHILD}:/x>.\n"
            f"            }}\n"
            f"        }}\n"
            f"        define the position<dest> {{\n"
            f"            it may only contain dimension points where {{\n"
            f"                it has the position<{_CHILD}:/y>.\n"
            f"            }}\n"
            f"        }}\n"
            f"        create a dimension point in position<src>.\n"
            f"        move the dimension point in position<src>::position<{_CHILD}:/x> to position<dest>.\n"
            f"    }}\n"
            f"}}\n"
        ),
    )
    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def")
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert all_diags == []


def test_cross_fqun_chained_to_local_violates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _setup_cross_fqun(tmp_path, monkeypatch)
    _write_source(
        tmp_path,
        "lib/x.def",
        f"define the potential position<{_CHILD}:/x>.\n",
    )
    _write_source(
        tmp_path,
        "lib/y.def",
        f"define the potential position<{_CHILD}:/y>.\n",
    )
    _write_source(
        tmp_path,
        "test.def",
        (
            f"define the potential action<{_PARENT}:/test> {{\n"
            f"    define the position<run>.\n"
            f"    it happens when {{\n"
            f"        the position<run> has a dimension point.\n"
            f"    }} and it does {{\n"
            f"        define the position<src> {{\n"
            f"            it may only contain dimension points where {{\n"
            f"                it has the position<{_CHILD}:/x>.\n"
            f"            }}\n"
            f"        }}\n"
            f"        define the position<dest> {{\n"
            f"            it may only contain dimension points where {{\n"
            f"                it has the position<{_CHILD}:/y>.\n"
            f"            }}\n"
            f"        }}\n"
            f"        create a dimension point in position<src>.\n"
            f"        move the dimension point in position<src>::position<{_CHILD}:/x> to position<dest>.\n"
            f"    }}\n"
            f"}}\n"
        ),
    )
    results = program_validator.ProgramValidator().validate_program(
        PurePosixPath("test.def")
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].missing_qualities == [
        f"position<{_CHILD}:/y>",
    ]


def test_cross_fqun_move_to_chained_action_local_satisfies(
    validate_project: ValidateProject,
):
    results = validate_project(
        {
            "lib/quality.def": f"define the potential position<{_CHILD}:/quality>.\n",
            "lib/act.def": (
                f"define the potential action<{_CHILD}:/act> {{\n"
                f"    define the position<trigger>.\n"
                f"    define the position<local_dest> {{\n"
                f"        it may only contain dimension points where {{\n"
                f"            it has the position</quality>.\n"
                f"        }}\n"
                f"    }}\n"
                f"    it happens when {{\n"
                f"        the position<trigger> has a dimension point.\n"
                f"    }} and it does {{\n"
                f"        create a dimension point in position<local_dest>.\n"
                f"    }}\n"
                f"}}\n"
            ),
            "test.def": (
                f"define the potential action<{_PARENT}:/test> {{\n"
                f"    define the position<run>.\n"
                f"    it happens when {{\n"
                f"        the position<run> has a dimension point.\n"
                f"    }} and it does {{\n"
                f"        define the position<src> {{\n"
                f"            it may only contain dimension points where {{\n"
                f"                it has the position<{_CHILD}:/quality>.\n"
                f"            }}\n"
                f"        }}\n"
                f"        create a dimension point in position<src>.\n"
                f"        move the dimension point in position<src> to action<{_CHILD}:/act>::position<local_dest>.\n"
                f"    }}\n"
                f"}}\n"
            ),
        },
        universe_name=_PARENT,
        local_deps={_CHILD: "lib"},
        sub_roots={"lib": _CHILD},
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert all_diags == []


def test_cross_fqun_move_to_chained_action_local_violates(
    validate_project: ValidateProject,
):
    results = validate_project(
        {
            "lib/quality.def": f"define the potential position<{_CHILD}:/quality>.\n",
            "lib/act.def": (
                f"define the potential action<{_CHILD}:/act> {{\n"
                f"    define the position<trigger>.\n"
                f"    define the position<local_dest> {{\n"
                f"        it may only contain dimension points where {{\n"
                f"            it has the position</quality>.\n"
                f"        }}\n"
                f"    }}\n"
                f"    it happens when {{\n"
                f"        the position<trigger> has a dimension point.\n"
                f"    }} and it does {{\n"
                f"        create a dimension point in position<local_dest>.\n"
                f"    }}\n"
                f"}}\n"
            ),
            "test.def": (
                f"define the potential action<{_PARENT}:/test> {{\n"
                f"    define the position<run>.\n"
                f"    it happens when {{\n"
                f"        the position<run> has a dimension point.\n"
                f"    }} and it does {{\n"
                f"        define the position<src>.\n"
                f"        create a dimension point in position<src>.\n"
                f"        move the dimension point in position<src> to action<{_CHILD}:/act>::position<local_dest>.\n"
                f"    }}\n"
                f"}}\n"
            ),
        },
        universe_name=_PARENT,
        local_deps={_CHILD: "lib"},
        sub_roots={"lib": _CHILD},
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 1
    assert isinstance(all_diags[0], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[0].missing_qualities == [
        f"position<{_CHILD}:/quality>",
    ]


def test_cross_fqun_move_from_chained_nonexistent_local_to_constrained(
    validate_project: ValidateProject,
):
    results = validate_project(
        {
            "lib/quality.def": f"define the potential position<{_CHILD}:/quality>.\n",
            "lib/act.def": (
                f"define the potential action<{_CHILD}:/act> {{\n"
                f"    define the position<trigger>.\n"
                f"    define the position<inner>.\n"
                f"    it happens when {{\n"
                f"        the position<trigger> has a dimension point.\n"
                f"    }} and it does {{\n"
                f"        create a dimension point in position<inner>.\n"
                f"    }}\n"
                f"}}\n"
            ),
            "test.def": (
                f"define the potential action<{_PARENT}:/test> {{\n"
                f"    define the position<run>.\n"
                f"    define the position<src> {{\n"
                f"        it may only contain dimension points where {{\n"
                f"            it has the action<{_CHILD}:/act>.\n"
                f"        }}\n"
                f"    }}\n"
                f"    it happens when {{\n"
                f"        the position<run> has a dimension point.\n"
                f"    }} and it does {{\n"
                f"        define the position<dest> {{\n"
                f"            it may only contain dimension points where {{\n"
                f"                it has the position<{_CHILD}:/quality>.\n"
                f"            }}\n"
                f"        }}\n"
                f"        create a dimension point in position<src>.\n"
                f"        move the dimension point in position<src>::action<{_CHILD}:/act>::position<no_such> to position<dest>.\n"
                f"    }}\n"
                f"}}\n"
            ),
        },
        universe_name=_PARENT,
        local_deps={_CHILD: "lib"},
        sub_roots={"lib": _CHILD},
    )
    all_diags = [d for r in results for d in r.diagnostics]
    assert len(all_diags) == 2
    assert isinstance(all_diags[0], diagnostics.ChainElementNotInActionDiagnostic)
    assert all_diags[0].element_name == "position<no_such>"
    assert all_diags[0].parent_name == f"action<{_CHILD}:/act>"
    assert isinstance(all_diags[1], diagnostics.MoveViolatesConstraintsDiagnostic)
    assert all_diags[1].missing_qualities == [
        f"position<{_CHILD}:/quality>",
    ]
