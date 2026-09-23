# pyright: reportUnusedCallResult=false
from __future__ import annotations

from pathlib import Path

import click.testing
import pytest

from define.compiler import diagnostics, driver
from tools.generators import generate_reference_graph_project as gen


class TestGenerateProjectFiles:
    def test_too_few_layers_raises(self):
        with pytest.raises(ValueError, match="layers must be at least"):
            gen.generate_project_files(layers=1)

    def test_fewer_modules_than_layers_raises(self):
        with pytest.raises(ValueError, match="modules must be at least"):
            gen.generate_project_files(modules=4, layers=8)

    def test_zero_fan_out_raises(self):
        with pytest.raises(ValueError, match="fan_out must be at least"):
            gen.generate_project_files(fan_out=0)

    def test_utility_fraction_out_of_range_raises(self):
        with pytest.raises(ValueError, match="utility_fraction must be in"):
            gen.generate_project_files(utility_fraction=1.5)

    def test_writes_one_file_per_module_plus_config_and_entry(self):
        files = gen.generate_project_files(modules=40, layers=4)
        assert len(files) == 42
        assert ".define/project/config.defcl" in files
        assert "test.dfn" in files

    def test_same_seed_generates_identical_files(self):
        first = gen.generate_project_files(modules=40, layers=4, seed=3)
        second = gen.generate_project_files(modules=40, layers=4, seed=3)
        assert first == second

    def test_deepest_layer_definitions_reference_nothing(self):
        files = gen.generate_project_files(modules=40, layers=4)
        assert files["lib/pkg39/m39.dfn"].endswith("m39>.\n")


class TestWriteProject:
    def test_writes_project_to_new_directory(self, tmp_path: Path):
        output = tmp_path / "project"

        gen.write_project(output, {"nested/source.dfn": "source\n"})

        assert (output / "nested/source.dfn").read_text(encoding="utf-8") == "source\n"

    def test_refuses_to_replace_existing_directory(self, tmp_path: Path):
        output = tmp_path / "project"
        output.mkdir()
        sentinel = output / "keep.txt"
        sentinel.write_text("keep\n", encoding="utf-8")

        with pytest.raises(FileExistsError):
            gen.write_project(output, {"source.dfn": "source\n"})

        assert sentinel.read_text(encoding="utf-8") == "keep\n"


class TestMain:
    def test_writes_custom_universe_project(self, tmp_path: Path):
        output = tmp_path / "project"
        result = click.testing.CliRunner().invoke(
            gen.main,
            [
                "--output",
                str(output),
                "--modules",
                "4",
                "--layers",
                "2",
                "--universe-name",
                "mv:example.com:generated",
            ],
        )

        assert result.exit_code == 0
        assert "mv:example.com:generated" in (output / "test.dfn").read_text(
            encoding="utf-8"
        )

    def test_refuses_existing_output_directory(self, tmp_path: Path):
        output = tmp_path / "project"
        output.mkdir()

        result = click.testing.CliRunner().invoke(
            gen.main,
            ["--output", str(output), "--modules", "4", "--layers", "2"],
        )

        assert result.exit_code == 2
        assert "File exists" in result.output


class TestGeneratedProjectCompiles:
    def test_project_compiles_without_diagnostics_or_exceptions(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        files = gen.generate_project_files(modules=12, layers=3)
        for relative_path, content in files.items():
            file_path = tmp_path / relative_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        output_dir = tmp_path / "generated"
        result = driver.Driver().compile_program(Path("test.dfn"), output_dir)

        assert result.all_exceptions == []
        assert result.all_diagnostics == []
        assert (output_dir / "__main__.py").is_file()


@pytest.mark.parametrize(
    "shape",
    [
        gen.Shape.INDEPENDENT,
        gen.Shape.CHAIN,
        gen.Shape.FAN_IN,
        gen.Shape.DEPTH_UPDATES,
        gen.Shape.DIAMONDS,
        gen.Shape.BOTTLENECKS,
        gen.Shape.CONFIG_CHAIN,
    ],
)
@pytest.mark.parametrize("modules", [1, 7])
def test_structured_projects_load_every_definition(
    shape: gen.Shape, modules: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    output = tmp_path / "project"
    gen.write_project(
        output,
        gen.generate_project_files(
            modules=modules, shape=shape, fan_out=3, path_depth=2
        ),
    )
    monkeypatch.chdir(output)
    validation = driver.Driver().validate_program(Path("test.dfn"), max_threads=1)
    assert validation.program_validation.all_exceptions == []
    assert validation.program_validation.all_diagnostics == []
    assert len(validation.program_validation.definition_results) == modules + 1


@pytest.mark.parametrize(
    ("shape", "fan_out", "references"),
    [
        (gen.Shape.INDEPENDENT, 3, [list[int]() for _ in range(4)]),
        (gen.Shape.CHAIN, 3, [[1], [2], [3], []]),
        (gen.Shape.FAN_IN, 3, [[3], [3], [3], []]),
        (gen.Shape.DEPTH_UPDATES, 3, [[1, 2, 3], [], [1], [2]]),
        (gen.Shape.CYCLES, 3, [[1, 2, 3], [0], [0], [0]]),
        (gen.Shape.MISSING, 3, [[4], [4], [4], [4]]),
        (gen.Shape.DIAMONDS, 3, [[1, 2], [3], [3], [4, 5], [], []]),
        (gen.Shape.DIAMONDS, 3, [[1, 2], [3], [3], [4], []]),
        (gen.Shape.BOTTLENECKS, 3, [[1, 2, 3], [4], [4], [4], [5, 6], [], []]),
        (gen.Shape.BOTTLENECKS, 1, [[1], [2], [3], []]),
    ],
)
def test_structured_reference_patterns(
    shape: gen.Shape, fan_out: int, references: list[list[int]]
):
    files = gen.generate_project_files(
        modules=len(references), shape=shape, fan_out=fan_out
    )
    assert len(files) == len(references) + 2
    for index, targets in enumerate(references):
        declaration = f"define the potential position<{gen.DEFAULT_UNIVERSE_NAME}:/lib/pkg{index}/m{index}>"
        if targets:
            expected = [
                f"{declaration} {{",
                "    it may only contain particles where {",
            ]
            for target in targets:
                expected.append(
                    f"        it has the position</lib/pkg{target}/m{target}>."
                )
            expected.extend(["    }", "}"])
        else:
            expected = [f"{declaration}."]
        assert files[f"lib/pkg{index}/m{index}.dfn"].splitlines() == expected


@pytest.mark.parametrize("modules", [4, 8])
def test_depth_update_shape_references_all_positions_then_predecessors(
    modules: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    output = tmp_path / "project"
    files = gen.generate_project_files(modules=modules, shape=gen.Shape.DEPTH_UPDATES)
    assert files["test.dfn"].splitlines() == [
        f"define the potential action<{gen.DEFAULT_UNIVERSE_NAME}:/test> {{",
        "    it happens when {",
        "        this particle is created.",
        "    } and it does {",
        "        define the position<references> {",
        "            it may only contain particles where {",
        "                it has the position</lib/pkg0/m0>.",
        "            }",
        "        }",
        "        create a particle in position<references>.",
        "        create a particle in position<references>::position</lib/pkg0/m0>.",
        "    }",
        "}",
    ]
    for index in range(modules):
        declaration = f"define the potential position<{gen.DEFAULT_UNIVERSE_NAME}:/lib/pkg{index}/m{index}>"
        if index == 1:
            expected = [f"{declaration}."]
        else:
            targets = range(1, modules) if index == 0 else [index - 1]
            expected = [
                f"{declaration} {{",
                "    it may only contain particles where {",
            ]
            for target in targets:
                expected.append(
                    f"        it has the position</lib/pkg{target}/m{target}>."
                )
            expected.extend(["    }", "}"])
        assert files[f"lib/pkg{index}/m{index}.dfn"].splitlines() == expected

    gen.write_project(output, files)
    monkeypatch.chdir(output)
    result = (
        driver.Driver()
        .validate_program(Path("test.dfn"), max_threads=1)
        .program_validation
    )
    assert result.all_exceptions == []
    assert result.all_diagnostics == []
    assert len(result.definition_results) == modules + 1


@pytest.mark.parametrize("shape", [gen.Shape.CYCLES, gen.Shape.MISSING])
def test_invalid_project_shapes(
    shape: gen.Shape, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    output = tmp_path / "project"
    gen.write_project(output, gen.generate_project_files(modules=4, shape=shape))
    monkeypatch.chdir(output)
    result = (
        driver.Driver()
        .validate_program(Path("test.dfn"), max_threads=1)
        .program_validation
    )
    if shape == gen.Shape.CYCLES:
        assert result.all_exceptions == []
        assert [type(diagnostic) for diagnostic in result.all_diagnostics] == [
            diagnostics.CircularGlobalReferenceDiagnostic
        ] * 3
    else:
        assert result.all_exceptions == []
        assert [type(diagnostic) for diagnostic in result.all_diagnostics] == [
            diagnostics.ReferencedFileNotFoundDiagnostic
        ] * 4


def test_new_cli_options(tmp_path: Path):
    output = tmp_path / "project"
    result = click.testing.CliRunner().invoke(
        gen.main,
        [
            "--output",
            str(output),
            "--shape",
            "depth-updates",
            "--modules",
            "4",
            "--path-depth",
            "3",
        ],
    )
    assert result.exit_code == 0
    assert (output / "directory/directory/directory/lib/pkg3/m3.dfn").is_file()
    assert (output / "test.dfn").is_file()


@pytest.mark.parametrize(("modules", "depth"), [(0, 0), (2, -1)])
def test_invalid_structured_sizes(modules: int, depth: int):
    with pytest.raises(ValueError, match="must be at least"):
        gen.generate_project_files(
            modules=modules, path_depth=depth, shape=gen.Shape.CHAIN
        )
