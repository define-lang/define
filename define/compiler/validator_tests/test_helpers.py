# pyright: reportUnusedCallResult=false
"""Shared validator test helpers."""

from pathlib import Path, PurePosixPath

from define.compiler import diagnostics, parser, validator
from define.compiler.transformer import DefineTransformer

_parser = parser.Parser()
_transformer = DefineTransformer()


def parse_transform_validate(
    source: str,
    expected_definition_path: str | None = None,
    expected_universe_name: str | None = None,
) -> list[diagnostics.Diagnostic]:
    """Parse, transform, and validate a source string."""
    tree = _parser.parse(source)
    program = _transformer.transform(tree)
    path = PurePosixPath(expected_definition_path) if expected_definition_path else None
    return validator.Validator().validate(
        program=program,
        expected_definition_path=path,
        expected_universe_name=expected_universe_name,
    )


def write_project_config(tmp_path: Path, universe_name: str) -> None:
    """Write a .define/project/config.defcl file under tmp_path."""
    config_dir = tmp_path / ".define" / "project"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.defcl").write_text(
        f'project: {{\n  universe_name: "{universe_name}"\n}}\n',
        encoding="utf-8",
    )
