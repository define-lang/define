from __future__ import annotations

from define.compiler.parsing import invisible_characters_data
from tools import generate_invisible_characters


def test_generated_data_matches_generator_unicode_version():
    assert (
        invisible_characters_data.UNICODE_VERSION
        == generate_invisible_characters.UNICODE_VERSION
    )
