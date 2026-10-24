from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING

from tools.windows_vm import bazel_tools_override

if TYPE_CHECKING:
    from pathlib import Path


def test_links_bazel_tools_and_adds_windows_test_tools(tmp_path: Path):
    embedded_tools = tmp_path / "embedded_tools"
    (embedded_tools / "jdk").mkdir(parents=True)
    (embedded_tools / "tools" / "cpp").mkdir(parents=True)
    (embedded_tools / "tools" / "test").mkdir()
    _ = (embedded_tools / "MODULE.bazel").write_text(
        'module(name = "bazel_tools")\nbazel_dep(name = "platforms")\n',
        encoding="utf-8",
        newline="\n",
    )
    _ = (embedded_tools / "tools" / "test" / "BUILD").write_text(
        "", encoding="utf-8", newline="\n"
    )
    release = tmp_path / "bazel.exe"
    with zipfile.ZipFile(release, "w") as archive:
        archive.writestr("embedded_tools/tools/test/tw.exe", "test wrapper")
        archive.writestr("embedded_tools/tools/test/xml.exe", "xml writer")
    destination = tmp_path / "override"

    bazel_tools_override.make_override(embedded_tools, release, "9.3.0", destination)

    assert (destination / "MODULE.bazel").read_text(encoding="utf-8") == (
        'module(name = "bazel_tools", bazel_compatibility = [">=9.3.0", "<=9.3.0"])\n'
        + 'bazel_dep(name = "platforms")\n'
    )
    for link in ("jdk", "tools/cpp", "tools/test/BUILD"):
        assert (destination / link).is_symlink()
        assert (destination / link).resolve() == (embedded_tools / link).resolve()
    assert (destination / "tools" / "test" / "tw.exe").read_text(
        encoding="utf-8"
    ) == "test wrapper"
    assert (destination / "tools" / "test" / "xml.exe").read_text(
        encoding="utf-8"
    ) == "xml writer"


def test_replaces_an_existing_override(tmp_path: Path):
    embedded_tools = tmp_path / "embedded_tools"
    (embedded_tools / "tools" / "test").mkdir(parents=True)
    _ = (embedded_tools / "MODULE.bazel").write_text(
        'module(name = "bazel_tools")\n', encoding="utf-8", newline="\n"
    )
    release = tmp_path / "bazel.exe"
    with zipfile.ZipFile(release, "w") as archive:
        archive.writestr("embedded_tools/tools/test/tw.exe", "test wrapper")
        archive.writestr("embedded_tools/tools/test/xml.exe", "xml writer")
    destination = tmp_path / "override"
    (destination / "stale").mkdir(parents=True)

    bazel_tools_override.make_override(embedded_tools, release, "9.3.0", destination)

    assert sorted(entry.name for entry in destination.iterdir()) == [
        "MODULE.bazel",
        "tools",
    ]
