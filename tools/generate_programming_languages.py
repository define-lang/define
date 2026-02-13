#!/usr/bin/env python3
"""Generate define/reserved_words/programming_languages.txt from GitHub Linguist languages.yml.

Requires: PyYAML (pip install pyyaml)
"""

import re
import sys
import typing
import urllib.request
from pathlib import Path
from typing import cast

if typing.TYPE_CHECKING:
    import http.client

import yaml

LINGUIST_URL = "https://raw.githubusercontent.com/github/linguist/master/lib/linguist/languages.yml"
OUTPUT_PATH = (
    Path(__file__).resolve().parent.parent
    / "define"
    / "reserved_words"
    / "programming_languages.txt"
)

_INVALID_CHARS = re.compile(r"[^a-z0-9]+")
_MULTIPLE_UNDERSCORES = re.compile(r"_+")


def normalize_token(name: str) -> str:
    """Normalize a name to [a-z0-9_]: lowercase, replace invalid chars with _."""
    normalized = _INVALID_CHARS.sub("_", name.lower())
    normalized = _MULTIPLE_UNDERSCORES.sub("_", normalized)
    return normalized.strip("_")


def variants_for_name(name: str) -> set[str]:
    """Return normalized tokens for a language name (canonical + space variants)."""
    tokens = {normalize_token(name)}
    if " " in name:
        tokens.add(normalize_token(name.replace(" ", "_")))
        tokens.add(normalize_token(name.replace(" ", "")))
    tokens.discard("")
    return tokens


def main() -> int:
    """Download Linguist YAML, parse it, and write programming_languages.txt."""
    try:
        with cast(
            "http.client.HTTPResponse",
            urllib.request.urlopen(LINGUIST_URL, timeout=30),  # noqa: S310
        ) as resp:
            content: str = resp.read().decode("utf-8")
    except OSError as e:
        print(f"Failed to fetch {LINGUIST_URL}: {e}", file=sys.stderr)
        return 1

    languages = cast("dict[str, dict[str, object]]", yaml.safe_load(content))
    tokens: set[str] = set()
    for lang_name, props in languages.items():
        if props.get("type") != "programming":
            continue
        tokens.update(variants_for_name(lang_name))
        for alias in cast("list[str]", props.get("aliases", [])):
            tokens.update(variants_for_name(alias))

    sorted_tokens = sorted(tokens)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _ = OUTPUT_PATH.write_text("\n".join(sorted_tokens) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
