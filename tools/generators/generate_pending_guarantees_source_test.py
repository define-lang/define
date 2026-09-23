from __future__ import annotations

from typing import TYPE_CHECKING

import click.testing
import pytest

from define.compiler import driver
from tools.generators import generate_pending_guarantees_source as gen

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize("automatic", [False, True])
@pytest.mark.parametrize("depth", [2, 4])
@pytest.mark.parametrize("position_depth", [1, 4])
def test_generated_source_triggers_actions_before_unrelated_destruction(
    depth: int, position_depth: int, *, automatic: bool
):
    lines = gen.generate_source_lines(
        3,
        2,
        depth,
        position_depth=position_depth,
        automatic_destruction=automatic,
    )
    child_names = "".join(
        f"::position</child_{index}>" for index in range(position_depth - 1)
    )
    middle_start = lines.index(
        f"define the potential action<{gen.DEFAULT_FQUN_PREFIX}:/middle> {{"
    )
    body_start = lines.index("    } and it does {", middle_start) + 1
    body_end = lines.index("    }", body_start)
    expected = ["        destroy the particle in position<run>."]
    for index in range(3):
        expected.append(
            f"        create a particle in position<unrelated_{index}>{child_names}::action</stage_0>::position<run>."
        )
    for index in range(2):
        if automatic:
            expected.append(f"        define the position<temporary_{index}>.")
            expected.append(
                f"        move the particle in position<victim_{index}> to position<temporary_{index}>."
            )
        else:
            expected.append(
                f"        destroy the particle in position<victim_{index}>."
            )
    assert lines[body_start:body_end] == expected

    for stage in range(depth):
        stage_start = (
            lines.index(
                f"define the potential action<{gen.DEFAULT_FQUN_PREFIX}:/stage_{stage}> {{"
            )
            + 1
        )
        stage_end = lines.index("}", stage_start)
        assigned = (
            "position</marker>" if stage == depth - 1 else f"action</stage_{stage + 1}>"
        )
        triggered = assigned if stage == depth - 1 else f"{assigned}::position<run>"
        assert lines[stage_start:stage_end] == [
            f"    it also assigns the {assigned}.",
            "    define the position<run>.",
            "    it happens when {",
            "        the position<run> has a particle.",
            "    } and it does {",
            f"        create a particle in {triggered}.",
            "        destroy the particle in position<run>.",
            "    }",
        ]
    for index in range(3):
        assert (
            f"        destroy the particle in position<saved_{index}>{child_names}::position</marker>."
            in lines
        )

    result = driver.Driver().validate_source("\n".join(lines) + "\n", max_threads=1)
    assert result.program_validation.all_exceptions == []
    assert result.program_validation.all_diagnostics == []


@pytest.mark.parametrize(
    ("pending", "destroyed", "depth"), [(0, 1, 2), (1, 0, 2), (1, 1, 1)]
)
def test_invalid_sizes(pending: int, destroyed: int, depth: int):
    with pytest.raises(ValueError, match="must be at least"):
        _ = gen.generate_source_lines(pending, destroyed, depth)


def test_invalid_position_depth():
    with pytest.raises(ValueError, match="position_depth"):
        _ = gen.generate_source_lines(position_depth=0)


def test_cli(tmp_path: Path):
    output = tmp_path / "pending.dfn"
    result = click.testing.CliRunner().invoke(
        gen.main,
        [
            "--output",
            str(output),
            "--pending-positions",
            "2",
            "--destroyed-positions",
            "3",
            "--call-depth",
            "3",
            "--position-depth",
            "2",
            "--automatic-destruction",
            "--fqun-prefix",
            "mv:example.com:generated",
        ],
    )
    assert result.exit_code == 0
    source = output.read_text()
    assert source.count("    define the position<unrelated_") == 2
    assert source.count("        define the position<temporary_") == 3
    assert "action<mv:example.com:generated:/stage_2>" in source
    assert "::position</child_0>::action</stage_0>" in source
