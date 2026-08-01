from pathlib import Path

from define.compiler.codegen.literal.python import template_env


def test_source_template_loader_finds_codegen_templates():
    environment = template_env.create_environment(Path(__file__).parent)

    assert environment.get_template("position_definition.j2").name == (
        "position_definition.j2"
    )
