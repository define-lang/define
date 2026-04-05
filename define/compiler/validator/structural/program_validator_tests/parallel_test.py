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
from define.compiler.validator.test_helpers import assert_no_errors

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
    files = {"root.dfn": _position_with_refs("root", leaf_names)}
    for name in leaf_names:
        files[f"{name}.dfn"] = _simple_position(name)
    result = validate_project(files, entry_file="root.dfn", max_workers=4)
    assert len(result.file_results) == 11
    assert_no_errors(result)


def test_deep_chain(validate_project: ValidateProject):
    chain = ["a", "b", "c", "d", "e"]
    files: dict[str, str] = {}
    for i, name in enumerate(chain[:-1]):
        files[f"{name}.dfn"] = _position_with_ref(name, chain[i + 1])
    files[f"{chain[-1]}.dfn"] = _simple_position(chain[-1])
    result = validate_project(files, entry_file="a.dfn", max_workers=4)
    assert len(result.file_results) == 5
    assert_no_errors(result)


def test_diamond_dependency(validate_project: ValidateProject):
    result = validate_project(
        {
            "top.dfn": _position_with_refs("top", ["left", "right"]),
            "left.dfn": _position_with_ref("left", "bottom"),
            "right.dfn": _position_with_ref("right", "bottom"),
            "bottom.dfn": _simple_position("bottom"),
        },
        entry_file="top.dfn",
        max_workers=4,
    )
    assert len(result.file_results) == 4
    assert_no_errors(result)


def test_wrong_type_detected_without_deferral(
    validate_project: ValidateProject,
):
    result = validate_project(
        {
            "root.dfn": _position_with_ref("root", "hub"),
            "hub.dfn": _hub_with_refs(
                [
                    "it has the action</target>.",
                    "it has the position</checker>.",
                ]
            ),
            "target.dfn": (
                "define the potential action<my.domain.com:my_lib:/target> {\n"
                "    define the position<_noop>.\n"
                "    it happens when {\n"
                "        the position<_noop> has a dimension point.\n"
                "    } and it does {\n"
                "        define the position<__noop>.\n"
                "        create a dimension point in position<__noop>.\n"
                "    }\n"
                "}\n"
            ),
            "checker.dfn": _position_with_ref("checker", "target"),
        },
        entry_file="root.dfn",
        max_workers=1,
    )
    assert len(result.file_results) == 4
    assert result.file_results[0].file_path == PurePosixPath("root.dfn")
    assert result.file_results[0].diagnostics == []
    assert result.file_results[1].file_path == PurePosixPath("hub.dfn")
    assert result.file_results[1].diagnostics == []
    assert result.file_results[2].file_path == PurePosixPath("target.dfn")
    assert result.file_results[2].diagnostics == []
    assert result.file_results[3].file_path == PurePosixPath("checker.dfn")
    assert len(result.file_results[3].diagnostics) == 1
    diag = result.file_results[3].diagnostics[0]
    assert isinstance(diag, diagnostics.ReferencedGlobalNameWrongTypeDiagnostic)
    assert diag.location.line == 3
    assert diag.location.column == 29
    assert diag.path == "/target"
    assert diag.expected_type == "position"


def test_reference_edges_resolve_by_file_completion_order(
    validate_project: ValidateProject,
):
    # With max_workers=2, test.dfn and lib/target.dfn run concurrently.
    # We force lib/target.dfn to complete after test.dfn so that
    # test.dfn's pending reference edges get resolved by the file
    # completion callback rather than being available immediately.
    universe = "mv:define-lang.org:test_parent"

    original_validate_file = file_validator.FileStructuralValidator.validate_file
    test_completed = threading.Event()

    def ordered_validate_file(
        self: file_validator.FileStructuralValidator,
        context: file_validator.FileValidationContext,
    ):
        if context.full_path == PurePosixPath("target.dfn"):
            test_completed.wait()
        result = original_validate_file(self, context)
        if context.full_path == PurePosixPath("test.dfn"):
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
                "test.dfn": (
                    f"define the potential position<{universe}:/test> {{\n"
                    f"    it may only contain dimension points where {{\n"
                    f"        it has the position</lib/target>.\n"
                    f"        it has the position</target>.\n"
                    f"    }}\n"
                    f"}}\n"
                ),
                "lib/target.dfn": f"define the potential position<{universe}:/target>.\n",
            },
            universe_name=universe,
            local_deps={universe: "lib"},
            sub_roots={"lib": universe},
            entry_file="test.dfn",
            max_workers=2,
        )

    assert len(result.file_results) == 2
    assert all(r.exception is None for r in result.file_results)
    assert len(result.file_results[0].diagnostics) == 2
    diag0 = result.file_results[0].diagnostics[0]
    assert isinstance(diag0, diagnostics.ReferencedGlobalNameWrongTypeDiagnostic)
    assert diag0.location.line == 3
    assert diag0.location.column == 29
    assert diag0.path == "/lib/target"
    assert diag0.expected_type == "position"
    diag1 = result.file_results[0].diagnostics[1]
    assert isinstance(diag1, diagnostics.ReferencedFileNotFoundDiagnostic)
    assert diag1.location.line == 4
    assert diag1.location.column == 29
    assert diag1.file_path == "target.dfn"
    assert result.file_results[1].file_path == PurePosixPath("lib/target.dfn")
    assert len(result.file_results[1].diagnostics) == 1
    diag2 = result.file_results[1].diagnostics[0]
    assert isinstance(diag2, diagnostics.PathMismatchDiagnostic)
    assert diag2.location.line == 1
    assert diag2.location.column == 62
    assert diag2.expected_path == "/lib/target"
    assert diag2.actual_path == "/target"
