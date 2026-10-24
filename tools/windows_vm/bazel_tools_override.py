"""Make the bazel_tools that --config=windows_vm uses in place of Bazel's own."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import urllib.request
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, cast

import click

if TYPE_CHECKING:
    import http.client

# Every test action runs these on Windows. Only the Windows release of Bazel
# has them.
_WINDOWS_TEST_TOOLS = ("tools/test/tw.exe", "tools/test/xml.exe")

# The directory in a checkout that holds the generated bazel_tools, which git
# and Bazel both ignore.
OVERRIDE_DIRECTORY = ".windows_vm"

_MODULE_DECLARATION = 'module(name = "bazel_tools")'

_HELP = f"""\
Make the bazel_tools that --config=windows_vm uses in place of Bazel's own.

\b
Run it in each checkout that uses --config=windows_vm, and again after each
Bazel upgrade:
  bazelisk run //tools/windows_vm:bazel_tools_override

Bazel on Linux has no tw.exe or xml.exe, which every test that runs on Windows
needs, so its test actions for the Windows VM can't run. This makes
{OVERRIDE_DIRECTORY}/bazel_tools in the checkout: the running Bazel's
bazel_tools, plus those two programs from the Windows release of the same
version, which it downloads once into ~/.cache/define-windows-vm.
See https://github.com/bazelbuild/bazel/issues/19209.

After a Bazel upgrade, Bazel stops with an error that it isn't compatible
with the module bazel_tools until this runs again.
"""


def _bazel_info(bazelisk: str, workspace: Path, key: str) -> str:
    return subprocess.run(
        [bazelisk, "info", key],
        cwd=workspace,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _open_url(url: str) -> http.client.HTTPResponse:
    # typeshed gives urlopen's result no type.
    return cast(
        "http.client.HTTPResponse",
        urllib.request.urlopen(url),  # noqa: S310 - Only GitHub release URLs.
    )


def _download_windows_release(version: str) -> Path:
    name = f"bazel-{version}-windows-x86_64.exe"
    cache_home = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    path = cache_home / "define-windows-vm" / name
    if path.exists():
        return path
    url = f"https://github.com/bazelbuild/bazel/releases/download/{version}/{name}"
    with _open_url(f"{url}.sha256") as response:
        expected = response.read().decode().split()[0]
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".partial")
    digest = hashlib.sha256()
    with _open_url(url) as response, partial.open("wb") as file:
        while chunk := response.read(1 << 20):
            digest.update(chunk)
            _ = file.write(chunk)
    if digest.hexdigest() != expected:
        partial.unlink()
        raise click.ClickException(f"{url} does not match its published SHA-256.")
    _ = partial.replace(path)
    return path


def _link_entries(source: Path, destination: Path, excluded: frozenset[str]):
    """Link each entry of source into destination, except the excluded names."""
    destination.mkdir()
    for entry in source.iterdir():
        if entry.name not in excluded:
            (destination / entry.name).symlink_to(entry)


def make_override(
    embedded_tools: Path, windows_release: Path, version: str, destination: Path
):
    """Make a bazel_tools of links to embedded_tools, plus the test tools."""
    module = (embedded_tools / "MODULE.bazel").read_text(encoding="utf-8")
    if module.count(_MODULE_DECLARATION) != 1:
        raise click.ClickException(
            f"bazel_tools' MODULE.bazel no longer declares {_MODULE_DECLARATION}."
        )
    if destination.exists():
        shutil.rmtree(destination)
    # Links leave the large parts, such as the JDK, where Bazel installed them.
    _link_entries(embedded_tools, destination, frozenset({"MODULE.bazel", "tools"}))
    # Another Bazel version refuses this bazel_tools, so that it isn't used with
    # a Bazel it wasn't made from.
    _ = (destination / "MODULE.bazel").write_text(
        module.replace(
            _MODULE_DECLARATION,
            f'module(name = "bazel_tools", bazel_compatibility = [">={version}", "<={version}"])',
        ),
        encoding="utf-8",
        newline="\n",
    )
    _link_entries(embedded_tools / "tools", destination / "tools", frozenset({"test"}))
    _link_entries(
        embedded_tools / "tools" / "test", destination / "tools" / "test", frozenset()
    )
    with zipfile.ZipFile(windows_release) as release:
        for tool in _WINDOWS_TEST_TOOLS:
            _ = (destination / tool).write_bytes(release.read(f"embedded_tools/{tool}"))


@click.command(help=_HELP, context_settings={"help_option_names": ["-h", "--help"]})
def main():
    """Make the bazel_tools that --config=windows_vm uses."""
    bazelisk = shutil.which("bazelisk")
    if bazelisk is None:
        raise click.ClickException("Missing command: bazelisk.")
    workspace = Path(os.environ["BUILD_WORKSPACE_DIRECTORY"])
    version = _bazel_info(bazelisk, workspace, "release").removeprefix("release ")
    install_base = Path(_bazel_info(bazelisk, workspace, "install_base"))
    embedded_tools = install_base / "embedded_tools"
    destination = workspace / OVERRIDE_DIRECTORY / "bazel_tools"
    destination.parent.mkdir(exist_ok=True)
    make_override(
        embedded_tools, _download_windows_release(version), version, destination
    )
    click.echo(f"Made {destination.relative_to(workspace)} for Bazel {version}.")


if __name__ == "__main__":
    main()
