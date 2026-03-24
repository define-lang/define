# pyright: reportUnusedCallResult=false
"""Parallel validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

import threading
from pathlib import PurePosixPath
from unittest import mock

from define.compiler import diagnostics
from define.compiler.conftest import ValidateProject
from define.compiler.validator.structural import file_validator

_POSITION_WITH_REF = (
    "define the potential position<my.domain.com:my_lib:/{name}> {{\n"
    "    it may only contain dimension points where {{\n"
    "        it has the position</{ref}>.\n"
    "    }}\n"
    "}}\n"
)


def _simple_position(name: str) -> str:
    return f"define the potential position<my.domain.com:my_lib:/{name}>.\n"


def _position_with_ref(name: str, ref: str) -> str:
    return _POSITION_WITH_REF.format(name=name, ref=ref)


def _position_with_refs(name: str, refs: list[str]) -> str:
    ref_lines = "".join(f"        it has the position</{r}>.\n" for r in refs)
    return (
        f"define the potential position<my.domain.com:my_lib:/{name}> {{\n"
        f"    it may only contain dimension points where {{\n"
        f"{ref_lines}"
        f"    }}\n"
        f"}}\n"
    )


def _hub_with_refs(ref_lines: list[str]) -> str:
    lines = "".join(f"        {line}\n" for line in ref_lines)
    return (
        f"define the potential position<my.domain.com:my_lib:/hub> {{\n"
        f"    it may only contain dimension points where {{\n"
        f"{lines}"
        f"    }}\n"
        f"}}\n"
    )


def test_fan_out(validate_project: ValidateProject):
    leaf_names = [f"leaf_{i}" for i in range(10)]
    files = {"root.def": _position_with_refs("root", leaf_names)}
    for name in leaf_names:
        files[f"{name}.def"] = _simple_position(name)
    result = validate_project(files, entry_file="root.def", max_workers=4)
    assert len(result.file_results) == 11
    assert not result.has_errors()


def test_deep_chain(validate_project: ValidateProject):
    chain = ["a", "b", "c", "d", "e"]
    files: dict[str, str] = {}
    for i, name in enumerate(chain[:-1]):
        files[f"{name}.def"] = _position_with_ref(name, chain[i + 1])
    files[f"{chain[-1]}.def"] = _simple_position(chain[-1])
    result = validate_project(files, entry_file="a.def", max_workers=4)
    assert len(result.file_results) == 5
    assert not result.has_errors()


def test_diamond_dependency(validate_project: ValidateProject):
    result = validate_project(
        {
            "top.def": _position_with_refs("top", ["left", "right"]),
            "left.def": _position_with_ref("left", "bottom"),
            "right.def": _position_with_ref("right", "bottom"),
            "bottom.def": _simple_position("bottom"),
        },
        entry_file="top.def",
        max_workers=4,
    )
    assert len(result.file_results) == 4
    assert not result.has_errors()


def test_wrong_type_detected_without_deferral(
    validate_project: ValidateProject,
):
    result = validate_project(
        {
            "root.def": _position_with_ref("root", "hub"),
            "hub.def": _hub_with_refs(
                [
                    "it has the action</target>.",
                    "it has the position</checker>.",
                ]
            ),
            "target.def": "define the potential action<my.domain.com:my_lib:/target>.\n",
            "checker.def": _position_with_ref("checker", "target"),
        },
        entry_file="root.def",
        max_workers=1,
    )
    assert len(result.file_results) == 4
    assert result.file_results[0].file_path == PurePosixPath("root.def")
    assert result.file_results[0].diagnostics == []
    assert result.file_results[1].file_path == PurePosixPath("hub.def")
    assert result.file_results[1].diagnostics == []
    assert result.file_results[2].file_path == PurePosixPath("target.def")
    assert result.file_results[2].diagnostics == []
    assert result.file_results[3].file_path == PurePosixPath("checker.def")
    assert len(result.file_results[3].diagnostics) == 1
    diag = result.file_results[3].diagnostics[0]
    assert isinstance(diag, diagnostics.ReferencedGlobalNameWrongTypeDiagnostic)
    assert diag.position.line == 3
    assert diag.position.column == 29
    assert diag.path == "/target"
    assert diag.expected_type == "position"


def test_reference_edges_resolve_by_file_completion_order(
    validate_project: ValidateProject,
):
    # With max_workers=2, test.def and lib/target.def run concurrently.
    # We force lib/target.def to complete after test.def so that
    # test.def's pending reference edges get resolved by the file
    # completion callback rather than being available immediately.
    universe = "mv:define-lang.org:test_parent"

    original_validate_file = file_validator.FileStructuralValidator.validate_file
    test_completed = threading.Event()

    def ordered_validate_file(
        self: file_validator.FileStructuralValidator,
        context: file_validator.FileValidationContext,
    ):
        if context.full_path == PurePosixPath("target.def"):
            test_completed.wait()
        result = original_validate_file(self, context)
        if context.full_path == PurePosixPath("test.def"):
            test_completed.set()
        return result

    with mock.patch.object(
        file_validator.FileStructuralValidator,
        "validate_file",
        autospec=True,
        side_effect=ordered_validate_file,
    ):
        result = validate_project(
            {
                "test.def": (
                    f"define the potential position<{universe}:/test> {{\n"
                    f"    it may only contain dimension points where {{\n"
                    f"        it has the position</lib/target>.\n"
                    f"        it has the position</target>.\n"
                    f"    }}\n"
                    f"}}\n"
                ),
                "lib/target.def": f"define the potential position<{universe}:/target>.\n",
            },
            universe_name=universe,
            local_deps={universe: "lib"},
            sub_roots={"lib": universe},
            entry_file="test.def",
            max_workers=2,
        )

    assert len(result.file_results) == 2
    assert all(r.exception is None for r in result.file_results)
    assert len(result.file_results[0].diagnostics) == 2
    diag0 = result.file_results[0].diagnostics[0]
    assert isinstance(diag0, diagnostics.ReferencedGlobalNameWrongTypeDiagnostic)
    assert diag0.position.line == 3
    assert diag0.position.column == 29
    assert diag0.path == "/lib/target"
    assert diag0.expected_type == "position"
    diag1 = result.file_results[0].diagnostics[1]
    assert isinstance(diag1, diagnostics.ReferencedFileNotFoundDiagnostic)
    assert diag1.position.line == 4
    assert diag1.position.column == 29
    assert diag1.file_path == "target.def"
    assert result.file_results[1].file_path == PurePosixPath("lib/target.def")
    assert len(result.file_results[1].diagnostics) == 1
    diag2 = result.file_results[1].diagnostics[0]
    assert isinstance(diag2, diagnostics.PathMismatchDiagnostic)
    assert diag2.position.line == 1
    assert diag2.position.column == 62
    assert diag2.expected_path == "/lib/target"
    assert diag2.actual_path == "/target"
