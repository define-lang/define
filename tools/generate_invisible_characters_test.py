from __future__ import annotations

from tools import generate_invisible_characters, runfiles


def test_generated_data_matches_generator_unicode_version():
    rust_data = runfiles.resolve_from_env("INVISIBLE_RANGES").read_text(
        encoding="utf-8"
    )
    assert f"//! Unicode {generate_invisible_characters.UNICODE_VERSION}." in rust_data
