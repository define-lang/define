from __future__ import annotations

import http.server
import os
import platform
import string
import threading
import typing
from http import HTTPStatus
from typing import TYPE_CHECKING
from unittest import mock

import click.testing

from tools import runfiles
from tools.windows_vm import create_windows_vm

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_autounattend_sets_administrator_and_autologon_passwords():
    template = runfiles.resolve_from_env("AUTOUNATTEND").read_text(encoding="utf-8")

    autounattend = create_windows_vm.render_autounattend(template, "Password1")

    assert autounattend.count("<Value>Password1</Value>") == 2
    assert "$" not in autounattend


def test_administrator_password_meets_windows_complexity():
    password = create_windows_vm.administrator_password()

    assert any(character in string.ascii_uppercase for character in password)
    assert any(character in string.ascii_lowercase for character in password)
    assert any(character in string.digits for character in password)


def _invoke_with_path(tmp_path: Path, path: Path) -> click.testing.Result:
    public_key = tmp_path / "key.pub"
    public_key.touch()
    with mock.patch.dict(os.environ, {"PATH": str(path)}):
        return click.testing.CliRunner().invoke(
            create_windows_vm.main,
            ["--ssh-public-key", str(public_key)],
        )


def _fake_sudo(tmp_path: Path) -> tuple[Path, Path]:
    bin_directory = tmp_path / "bin"
    bin_directory.mkdir()
    sudo_arguments = tmp_path / "sudo-arguments"
    sudo = bin_directory / "sudo"
    _ = sudo.write_text(f'#!/bin/sh\necho "$@" >> {sudo_arguments}\n')
    sudo.chmod(0o755)
    return bin_directory, sudo_arguments


def test_installs_packages_with_dnf_on_fedora(tmp_path: Path):
    bin_directory, sudo_arguments = _fake_sudo(tmp_path)

    with mock.patch.object(
        platform,
        "freedesktop_os_release",
        autospec=True,
        return_value={"ID": "fedora"},
    ):
        result = _invoke_with_path(tmp_path, bin_directory)

    assert sudo_arguments.read_text() == (
        "dnf install --assumeyes libvirt-client libvirt-daemon-kvm passt "
        + "qemu-img virt-install virt-manager xorriso\n"
    )
    assert result.exit_code == 1
    assert result.output == (
        "Installing virtualization packages with sudo...\n"
        + "Error: Missing commands: passt, qemu-img, virsh, virt-install, "
        + "xorriso. Install libvirt with its QEMU/KVM driver, qemu-img, "
        + "virt-install, passt, and xorriso.\n"
    )


def test_installs_packages_with_apt_on_ubuntu(tmp_path: Path):
    bin_directory, sudo_arguments = _fake_sudo(tmp_path)

    with mock.patch.object(
        platform,
        "freedesktop_os_release",
        autospec=True,
        return_value={"ID": "ubuntu"},
    ):
        result = _invoke_with_path(tmp_path, bin_directory)

    assert sudo_arguments.read_text() == (
        "apt-get update\n"
        + "apt-get install --yes libvirt-clients libvirt-daemon "
        + "libvirt-daemon-driver-qemu passt qemu-system-x86 qemu-utils "
        + "virt-manager virtinst xorriso\n"
    )
    assert result.exit_code == 1
    assert result.output == (
        "Installing virtualization packages with sudo...\n"
        + "Error: Missing commands: passt, qemu-img, virsh, virt-install, "
        + "xorriso. Install libvirt with its QEMU/KVM driver, qemu-img, "
        + "virt-install, passt, and xorriso.\n"
    )


def test_reports_missing_commands_on_other_distributions(tmp_path: Path):
    with mock.patch.object(
        platform,
        "freedesktop_os_release",
        autospec=True,
        return_value={"ID": "arch"},
    ):
        result = _invoke_with_path(tmp_path, tmp_path)

    assert result.exit_code == 1
    assert result.output == (
        "Error: Missing commands: passt, qemu-img, virsh, virt-install, "
        + "xorriso. Install libvirt with its QEMU/KVM driver, qemu-img, "
        + "virt-install, passt, and xorriso.\n"
    )


_CONTENT = bytes(range(256)) * (40 * 1024)
_ETAG = '"current"'


class _RangeHandler(http.server.BaseHTTPRequestHandler):
    requested_ranges: typing.ClassVar[list[str | None]] = []

    def do_GET(self):
        requested_range = self.headers.get("Range")
        type(self).requested_ranges.append(requested_range)
        start = 0
        if requested_range is not None and self.headers.get("If-Range") == _ETAG:
            start = int(requested_range.removeprefix("bytes=").removesuffix("-"))
        if start >= len(_CONTENT):
            self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
            self.end_headers()
            return
        body = _CONTENT[start:]
        self.send_response(HTTPStatus.PARTIAL_CONTENT if start else HTTPStatus.OK)
        self.send_header("ETag", _ETAG)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        _ = self.wfile.write(body)

    @typing.override
    def log_message(self, format: str, *args: object):
        pass


def _download_from_server(
    path: Path, capsys: pytest.CaptureFixture[str]
) -> tuple[list[str | None], str]:
    _RangeHandler.requested_ranges = []
    with http.server.ThreadingHTTPServer(("127.0.0.1", 0), _RangeHandler) as server:
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        create_windows_vm.download(f"http://127.0.0.1:{server.server_port}/", path)
        server.shutdown()
        thread.join()
    return _RangeHandler.requested_ranges, capsys.readouterr().out


def test_download_reports_each_tenth(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    path = tmp_path / "file.iso"

    requested_ranges, output = _download_from_server(path, capsys)

    assert requested_ranges == [None]
    assert path.read_bytes() == _CONTENT
    assert sorted(tmp_path.iterdir()) == [path]
    assert output == "".join(
        f"  0.0 of 0.0 GB ({percent}%)\n"
        for percent in (10, 20, 30, 40, 50, 60, 70, 80, 90, 100)
    )


def test_download_resumes_unfinished_download(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    path = tmp_path / "file.iso"
    _ = (tmp_path / "file.iso.partial").write_bytes(_CONTENT[: 6 * 1024 * 1024])
    _ = (tmp_path / "file.iso.etag").write_text(_ETAG, encoding="utf-8")

    requested_ranges, output = _download_from_server(path, capsys)

    assert requested_ranges == ["bytes=6291456-"]
    assert path.read_bytes() == _CONTENT
    assert sorted(tmp_path.iterdir()) == [path]
    assert output == (
        "  Resuming at 0.0 GB\n"
        + "  0.0 of 0.0 GB (70%)\n"
        + "  0.0 of 0.0 GB (80%)\n"
        + "  0.0 of 0.0 GB (90%)\n"
        + "  0.0 of 0.0 GB (100%)\n"
    )


def test_download_restarts_when_file_changed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    path = tmp_path / "file.iso"
    _ = (tmp_path / "file.iso.partial").write_bytes(b"old file")
    _ = (tmp_path / "file.iso.etag").write_text('"old"', encoding="utf-8")

    requested_ranges, _ = _download_from_server(path, capsys)

    assert requested_ranges == ["bytes=8-"]
    assert path.read_bytes() == _CONTENT
    assert sorted(tmp_path.iterdir()) == [path]


def test_download_finishes_completely_downloaded_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    path = tmp_path / "file.iso"
    _ = (tmp_path / "file.iso.partial").write_bytes(_CONTENT)
    _ = (tmp_path / "file.iso.etag").write_text(_ETAG, encoding="utf-8")

    requested_ranges, output = _download_from_server(path, capsys)

    assert requested_ranges == [f"bytes={len(_CONTENT)}-"]
    assert path.read_bytes() == _CONTENT
    assert sorted(tmp_path.iterdir()) == [path]
    assert output == ""
