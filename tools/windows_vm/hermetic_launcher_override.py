"""Make the Windows launcher template that --config=windows_vm uses."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import click

from tools.windows_vm import bazel_tools_override

# TODO: Remove this override once a hermetic-launcher release has
# https://github.com/hermeticbuild/hermetic-launcher/pull/87, and upgrade to it.
# This commit is that PR's branch, on top of the merged #83, #84 and #85.
_REPOSITORY = "https://github.com/mkanat/hermetic-launcher.git"
_COMMIT = "5169496348324aed5d4a026a6fccc698665914fc"

_TEMPLATE_TARGET = "//runfiles-stub:runfiles-stub_x86_64-pc-windows-gnullvm"
_TEMPLATE_NAME = "runfiles-stub-x86_64-windows.exe"

# The same package that hermetic-launcher's download of the template has.
_BUILD_FILE = f"""\
package(default_visibility = ["//visibility:public"])

exports_files(["{_TEMPLATE_NAME}"])

filegroup(
    name = "file",
    srcs = ["{_TEMPLATE_NAME}"],
)
"""

_HELP = f"""\
Make the Windows launcher template that --config=windows_vm uses.

\b
Run it in each checkout that uses --config=windows_vm:
  bazelisk run //tools/windows_vm:hermetic_launcher_override

The released hermetic-launcher template, which starts each Windows test, lacks
fixes that Windows tests need. This builds the template from a commit that has
them, once, into ~/.cache/define-windows-vm, and makes
{bazel_tools_override.OVERRIDE_DIRECTORY}/runfiles_stub_x86_64_windows in the
checkout from it.
"""


def write_template_repository(template: Path, destination: Path):
    """Make a repository like hermetic-launcher's download of the template."""
    if destination.exists():
        shutil.rmtree(destination)
    (destination / "file").mkdir(parents=True)
    (destination / "REPO.bazel").touch()
    _ = (destination / "file" / "BUILD").write_text(
        _BUILD_FILE, encoding="utf-8", newline="\n"
    )
    _ = shutil.copyfile(template, destination / "file" / _TEMPLATE_NAME)


def _build_template(bazelisk: str, git: str, template: Path):
    """Build the template at _COMMIT into template."""
    with tempfile.TemporaryDirectory() as checkout_name:
        checkout = Path(checkout_name)
        for command in (
            [git, "init", "--quiet"],
            [git, "fetch", "--quiet", "--depth=1", _REPOSITORY, _COMMIT],
            [git, "checkout", "--quiet", "FETCH_HEAD"],
        ):
            _ = subprocess.run(command, cwd=checkout, check=True)
        try:
            _ = subprocess.run(
                [bazelisk, "build", "--config=release", _TEMPLATE_TARGET],
                cwd=checkout,
                check=True,
            )
            built = Path(
                subprocess.run(
                    [
                        bazelisk,
                        "cquery",
                        "--config=release",
                        "--output=files",
                        _TEMPLATE_TARGET,
                    ],
                    cwd=checkout,
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout.strip()
            )
            template.parent.mkdir(parents=True, exist_ok=True)
            partial = template.with_suffix(".partial")
            _ = shutil.copyfile(checkout / built, partial)
            _ = partial.replace(template)
        finally:
            # The checkout's Bazel server and output tree would otherwise
            # outlive the checkout.
            _ = subprocess.run(
                [bazelisk, "clean", "--expunge"], cwd=checkout, check=True
            )


@click.command(help=_HELP, context_settings={"help_option_names": ["-h", "--help"]})
def main():
    """Make the launcher template that --config=windows_vm uses."""
    bazelisk = shutil.which("bazelisk")
    if bazelisk is None:
        raise click.ClickException("Missing command: bazelisk.")
    git = shutil.which("git")
    if git is None:
        raise click.ClickException("Missing command: git.")
    workspace = Path(os.environ["BUILD_WORKSPACE_DIRECTORY"])
    cache_home = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    template = cache_home / "define-windows-vm" / f"runfiles-stub-{_COMMIT}.exe"
    if not template.exists():
        _build_template(bazelisk, git, template)
    destination = (
        workspace
        / bazel_tools_override.OVERRIDE_DIRECTORY
        / "runfiles_stub_x86_64_windows"
    )
    destination.parent.mkdir(exist_ok=True)
    write_template_repository(template, destination)
    click.echo(f"Made {destination.relative_to(workspace)}.")


if __name__ == "__main__":
    main()
