from __future__ import annotations

from define.compiler.parsing import invisible_characters_data
from tools import generate_invisible_characters, runfiles


def test_generated_data_matches_generator_unicode_version():
    assert (
        invisible_characters_data.UNICODE_VERSION
        == generate_invisible_characters.UNICODE_VERSION
    )


def test_rust_data_matches_python_data():
    rust_data = runfiles.resolve_from_env("INVISIBLE_RANGES").read_text(
        encoding="utf-8"
    )
    assert rust_data == generate_invisible_characters.render_rust(
        list(invisible_characters_data.INVISIBLE_RANGES)
    )
