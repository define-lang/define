from __future__ import annotations

from typing import TYPE_CHECKING

from tools.windows_vm import hermetic_launcher_override

if TYPE_CHECKING:
    from pathlib import Path


def test_writes_a_repository_with_the_template(tmp_path: Path):
    template = tmp_path / "runfiles-stub.exe"
    _ = template.write_bytes(b"template")
    destination = tmp_path / "override"
    (destination / "stale").mkdir(parents=True)

    hermetic_launcher_override.write_template_repository(template, destination)

    assert sorted(
        path.relative_to(destination).as_posix() for path in destination.rglob("*")
    ) == [
        "REPO.bazel",
        "file",
        "file/BUILD",
        "file/runfiles-stub-x86_64-windows.exe",
    ]
    assert (destination / "REPO.bazel").read_text(encoding="utf-8") == ""
    assert (destination / "file" / "BUILD").read_text(encoding="utf-8") == (
        'package(default_visibility = ["//visibility:public"])\n'
        + "\n"
        + 'exports_files(["runfiles-stub-x86_64-windows.exe"])\n'
        + "\n"
        + "filegroup(\n"
        + '    name = "file",\n'
        + '    srcs = ["runfiles-stub-x86_64-windows.exe"],\n'
        + ")\n"
    )
    assert (
        destination / "file" / "runfiles-stub-x86_64-windows.exe"
    ).read_bytes() == b"template"
