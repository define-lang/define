"""Create a Windows Server virtual machine for building and testing Define.

The virtual machine runs under the current user's libvirt session with KVM.
Windows installs unattended, sets itself up for Bazel builds, and then accepts
SSH logins with the current user's key.
"""

from __future__ import annotations

import hashlib
import http.client
import os
import platform
import secrets
import shutil
import ssl
import string
import subprocess
import sys
import tempfile
import typing
import urllib.error
import urllib.request
from http import HTTPStatus
from pathlib import Path

import click

from tools import runfiles
from tools.windows_vm import vm

_CACHE_HOME = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
_DATA_HOME = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))

# The default storage pool of a libvirt session, which virt-manager shows.
_DISK_PATH = _DATA_HOME / "libvirt" / "images" / f"{vm.DOMAIN_NAME}.qcow2"

# The English (United States) ISO from the Microsoft Evaluation Center.
_WINDOWS_ISO_URL = "https://go.microsoft.com/fwlink/?linkid=2345730"

# The stable-virtio link redirects to plain HTTP, so this names the version
# directly. autounattend.xml uses this version's driver paths.
_VIRTIO_WIN_URL = (
    "https://fedorapeople.org/groups/virt/virtio-win/direct-downloads"
    "/archive-virtio/virtio-win-0.1.302-1/virtio-win-0.1.302.iso"
)
# virtio-win publishes no checksum for its ISO, so this is the checksum of the
# ISO when it was pinned.
_VIRTIO_WIN_SHA256 = "303f7ae40dad495d6ae474fdc571df58958a4dbc5c37a522d80f9a203867949d"

_DOWNLOAD_CHUNK_BYTES = 1024 * 1024
# A read that receives nothing for this long fails, so that a stalled connection
# resumes instead of waiting forever.
_DOWNLOAD_TIMEOUT_SECONDS = 60
_DOWNLOAD_ATTEMPTS = 5

# libvirt runs passt for the virtual machine's network.
# virt-install attaches the CDs in this order: the Windows ISO, then each
# --disk CD in its order on the command line.
_INSTALL_MEDIA_TARGETS = ("sda", "sdb", "sdc")

_REQUIRED_COMMANDS = ("passt", "qemu-img", "virsh", "virt-install", "xorriso")

# virt-manager is not required, but it shows the install and the console.
_DEBIAN_PACKAGES = (
    "libvirt-clients",
    "libvirt-daemon",
    "libvirt-daemon-driver-qemu",
    "passt",
    "qemu-system-x86",
    "qemu-utils",
    "virt-manager",
    "virtinst",
    "xorriso",
)
_FEDORA_PACKAGES = (
    "libvirt-client",
    "libvirt-daemon-kvm",
    "passt",
    "qemu-img",
    "virt-install",
    "virt-manager",
    "xorriso",
)

# The package manager commands that install the required commands, by the ID
# of the Linux distribution in os-release.
_PACKAGE_INSTALLS = {
    "debian": (
        ("apt-get", "update"),
        ("apt-get", "install", "--yes", *_DEBIAN_PACKAGES),
    ),
    "fedora": (("dnf", "install", "--assumeyes", *_FEDORA_PACKAGES),),
    "ubuntu": (
        ("apt-get", "update"),
        ("apt-get", "install", "--yes", *_DEBIAN_PACKAGES),
    ),
}


def _missing_commands() -> list[str]:
    return [command for command in _REQUIRED_COMMANDS if shutil.which(command) is None]


def _install_packages(installs: tuple[tuple[str, ...], ...]):
    sudo = shutil.which("sudo")
    if sudo is None:
        raise click.ClickException(
            "Installing packages needs sudo, which is not on PATH."
        )
    click.echo("Installing virtualization packages with sudo...")
    for install in installs:
        _ = subprocess.run([sudo, *install], check=True)


def resolve_commands() -> dict[str, str]:
    """Find the path of each required command, installing them when possible."""
    if sys.platform != "linux":
        raise click.ClickException("KVM virtual machines need a Linux host.")
    installs = _PACKAGE_INSTALLS.get(platform.freedesktop_os_release()["ID"])
    if _missing_commands() and installs is not None:
        _install_packages(installs)
    missing = _missing_commands()
    if missing:
        raise click.ClickException(
            f"Missing commands: {', '.join(missing)}. Install libvirt with its "
            + "QEMU/KVM driver, qemu-img, virt-install, passt, and xorriso."
        )
    # Fedora lets every user open /dev/kvm, but Debian and Ubuntu allow only the
    # kvm group.
    if not os.access("/dev/kvm", os.R_OK | os.W_OK):
        raise click.ClickException(
            "You cannot open /dev/kvm. Run `sudo usermod --append --groups kvm "
            + '"$USER"`, log out and back in, and run this again.'
        )
    paths: dict[str, str] = {}
    for command in _REQUIRED_COMMANDS:
        paths[command] = typing.cast("str", shutil.which(command))
    return paths


def administrator_password() -> str:
    """Generate an Administrator password."""
    # Windows requires three of uppercase, lowercase, digits, and symbols, which
    # a random string can miss.
    return secrets.token_urlsafe(24) + "Aa1"


def render_autounattend(template: str, password: str) -> str:
    """Fill in the answer file template."""
    return string.Template(template).substitute(administrator_password=password)


def _copy_with_progress(
    response: http.client.HTTPResponse,
    file: typing.BinaryIO,
    downloaded_bytes: int,
    total_bytes: int,
):
    # A tenth of the download between reports shows progress without filling an
    # agent's context with output.
    next_report = downloaded_bytes * 10 // total_bytes + 1
    while chunk := response.read(_DOWNLOAD_CHUNK_BYTES):
        _ = file.write(chunk)
        downloaded_bytes += len(chunk)
        if downloaded_bytes * 10 >= next_report * total_bytes:
            click.echo(
                f"  {downloaded_bytes / 1e9:.1f} of {total_bytes / 1e9:.1f} GB "
                + f"({downloaded_bytes * 100 // total_bytes}%)"
            )
            next_report = downloaded_bytes * 10 // total_bytes + 1
    # http.client ends a read early without an error when the server closes
    # the connection before sending every byte.
    if downloaded_bytes != total_bytes:
        raise http.client.IncompleteRead(b"", total_bytes - downloaded_bytes)


def download(url: str, path: Path):
    """Download a file, resuming a download that was interrupted earlier."""
    for attempt in range(1, _DOWNLOAD_ATTEMPTS + 1):
        try:
            _download_once(url, path)
        except (
            ConnectionError,
            TimeoutError,
            http.client.IncompleteRead,
            ssl.SSLEOFError,
        ) as error:
            if attempt == _DOWNLOAD_ATTEMPTS:
                raise
            click.echo(f"  The connection failed ({error!r}). Resuming...")
        else:
            return


def _download_once(url: str, path: Path):
    partial_path = path.with_name(path.name + ".partial")
    etag_path = path.with_name(path.name + ".etag")
    request = urllib.request.Request(url)  # noqa: S310 - Callers pass fixed HTTPS URLs.
    resumed_bytes = 0
    if partial_path.exists() and etag_path.exists():
        resumed_bytes = partial_path.stat().st_size
        request.add_header("Range", f"bytes={resumed_bytes}-")
        # The server sends the whole file instead if it has changed since the
        # earlier run, such as when a link moves to a newer ISO.
        request.add_header("If-Range", etag_path.read_text(encoding="utf-8"))
    try:
        response = typing.cast(
            "http.client.HTTPResponse",
            urllib.request.urlopen(  # noqa: S310 - Callers pass fixed HTTPS URLs.
                request, timeout=_DOWNLOAD_TIMEOUT_SECONDS
            ),
        )
    except urllib.error.HTTPError as error:
        # The earlier run downloaded every byte but stopped before renaming.
        if error.code != HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE:
            raise
        _ = partial_path.rename(path)
        etag_path.unlink()
        return
    with response:
        if response.status != HTTPStatus.PARTIAL_CONTENT:
            resumed_bytes = 0
        if resumed_bytes:
            click.echo(f"  Resuming at {resumed_bytes / 1e9:.1f} GB")
        _ = etag_path.write_text(response.headers["ETag"], encoding="utf-8")
        total_bytes = resumed_bytes + int(response.headers["Content-Length"])
        with partial_path.open("ab" if resumed_bytes else "wb") as file:
            _copy_with_progress(response, file, resumed_bytes, total_bytes)
    _ = partial_path.rename(path)
    etag_path.unlink()


def _verify_sha256(path: Path, expected: str):
    with path.open("rb") as file:
        actual = hashlib.file_digest(file, "sha256").hexdigest()
    if actual != expected:
        path.unlink()
        raise click.ClickException(
            f"{path} has SHA-256 {actual}, but {expected} was expected. "
            + "It was deleted, so the next run downloads it again."
        )


def _write_private_file(path: Path, content: str):
    file_descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(file_descriptor, "w") as file:
        _ = file.write(content)


def _build_unattend_iso(
    commands: dict[str, str],
    iso_path: Path,
    autounattend: str,
    files: dict[str, Path],
):
    """Build the answer file CD, with files by their name on the CD."""
    with tempfile.TemporaryDirectory() as directory_name:
        directory = Path(directory_name)
        _ = (directory / "autounattend.xml").write_text(autounattend, encoding="utf-8")
        for name, source in files.items():
            _ = shutil.copy(source, directory / name)
        _ = subprocess.run(
            [
                commands["xorriso"],
                "-as",
                "mkisofs",
                "-quiet",
                "-joliet",
                "-rational-rock",
                "-volid",
                "DEFINE_UNATTEND",
                "-output",
                str(iso_path),
                str(directory),
            ],
            check=True,
        )


def _create_disk(commands: dict[str, str], path: Path, size_gib: int):
    # Copy-on-write on btrfs fragments a disk image with every guest write, which
    # makes the virtual disk slow. Other filesystems ignore nocow.
    _ = subprocess.run(
        [
            commands["qemu-img"],
            "create",
            "-q",
            "-f",
            "qcow2",
            "-o",
            "nocow=on",
            str(path),
            f"{size_gib}G",
        ],
        check=True,
    )


def _eject_install_media(commands: dict[str, str]):
    # The VM then starts without the downloaded ISOs, which are only a cache, or
    # the answer file, which holds the Administrator password.
    for target in _INSTALL_MEDIA_TARGETS:
        _ = vm.virsh(
            commands["virsh"],
            "change-media",
            vm.DOMAIN_NAME,
            target,
            "--eject",
            "--config",
        )


_HELP = """\
Create a Windows VM for building and testing Define on Windows.

\b
Run it from the repository with:
  bazelisk run //tools/windows_vm:create_windows_vm -- [OPTIONS]

The host must be Linux with KVM. On Fedora, Debian, and Ubuntu, the command
installs any missing packages with sudo, which asks for your password.
Elsewhere, install libvirt with its QEMU/KVM driver, qemu-img, virt-install,
passt, and xorriso. On Debian and Ubuntu, your user must also be in the kvm group.

The VM shares the host's CPUs rather than reserving them. While it runs, it
holds all of its memory, because Windows soon writes to all of it; shut it
down to give the memory back. The disk image starts small and grows as
Windows writes to it, up to --disk-gib.

The command downloads the Windows Server 2025 Evaluation ISO (8 GB) and
the virtio drivers for Windows, and reuses them on later runs. The
evaluation needs no product key and expires after 180 days. The VM extends
it once by itself, so it lasts about a year; see tools/windows_vm/README.md.

\b
Files, with $XDG_CACHE_HOME and $XDG_DATA_HOME in place of ~/.cache and
~/.local/share when they are set:
  ~/.cache/define-windows-vm/
      The downloaded ISOs, which you can delete once the VM is set up.
  ~/.local/share/libvirt/images/define-windows.qcow2
      The VM's disk, in the default storage pool of the libvirt session.
  ~/.local/share/define-windows-vm/administrator-password
  ~/.config/libvirt/qemu/define-windows.xml
      The VM's definition, which libvirt manages. Change it with virsh.

Windows installs unattended and sets itself up with SSH for your key,
PowerShell 7, Git, the Visual Studio 2022 C++ Build Tools, bazelisk, long paths,
Developer Mode, and Microsoft Defender exclusions for builds. This takes
about an hour. The command then starts the VM and prints how to connect.
To copy a checkout into the VM, use //tools/windows_vm:sync_windows_vm.

\b
Using the VM, which runs in your user's libvirt session (qemu:///session):
  ssh -p SSH_PORT Administrator@localhost
      Runs PowerShell 7 in the VM.
  virsh --connect qemu:///session start define-windows
  virsh --connect qemu:///session shutdown --mode agent define-windows
  virt-manager
      Shows the console, under the QEMU/KVM User session, where you log in
      with the Administrator password.

If setup fails, Windows stays running and the error is in
C:\\define-setup.log, which you can read on the console.

\b
To recreate the VM, remove the old one first:
  virsh --connect qemu:///session destroy define-windows
  virsh --connect qemu:///session undefine define-windows
  rm ~/.local/share/libvirt/images/define-windows.qcow2
"""


@click.command(help=_HELP, context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--ssh-public-key",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=Path.home() / ".ssh" / "id_ed25519.pub",
    show_default=True,
    help="Public key that can log in to the VM over SSH as Administrator.",
)
@click.option("--vcpus", type=int, default=8, show_default=True, help="Virtual CPUs.")
@click.option(
    "--memory-gib", type=int, default=8, show_default=True, help="Memory in GiB."
)
@click.option(
    "--disk-gib",
    type=int,
    default=80,
    show_default=True,
    help="Maximum disk size in GiB. The disk image grows only as Windows fills it.",
)
@click.option(
    "--ssh-port",
    type=int,
    default=2222,
    show_default=True,
    help="Port on localhost that forwards to the VM's SSH server.",
)
def main(
    ssh_public_key: Path,
    vcpus: int,
    memory_gib: int,
    disk_gib: int,
    ssh_port: int,
):
    """Create the Windows VM."""
    commands = resolve_commands()
    working_directory = Path(os.environ.get("BUILD_WORKING_DIRECTORY", Path.cwd()))
    ssh_public_key = (working_directory / ssh_public_key).resolve()

    cache_directory = _CACHE_HOME / "define-windows-vm"
    cache_directory.mkdir(parents=True, exist_ok=True)
    data_directory = _DATA_HOME / "define-windows-vm"
    data_directory.mkdir(parents=True, exist_ok=True)
    # qemu-img would overwrite the disk of an existing VM.
    if _DISK_PATH.exists():
        raise click.ClickException(
            f"{_DISK_PATH} already exists. To recreate the VM, see --help."
        )
    _DISK_PATH.parent.mkdir(parents=True, exist_ok=True)

    windows_iso = cache_directory / "windows-server-2025-evaluation.iso"
    if not windows_iso.exists():
        click.echo("Downloading the Windows Server 2025 evaluation ISO (8 GB)...")
        download(_WINDOWS_ISO_URL, windows_iso)
    virtio_iso = cache_directory / "virtio-win.iso"
    if not virtio_iso.exists():
        click.echo("Downloading the virtio drivers for Windows...")
        download(_VIRTIO_WIN_URL, virtio_iso)
        _verify_sha256(virtio_iso, _VIRTIO_WIN_SHA256)

    password = administrator_password()
    password_path = data_directory / "administrator-password"
    _write_private_file(password_path, password + "\n")
    unattend_iso = cache_directory / "unattend.iso"
    _build_unattend_iso(
        commands,
        unattend_iso,
        render_autounattend(
            runfiles.resolve_from_env("AUTOUNATTEND").read_text(encoding="utf-8"),
            password,
        ),
        {
            "administrators_authorized_keys": ssh_public_key,
            "extend_evaluation.ps1": runfiles.resolve_from_env("EXTEND_EVALUATION"),
            "first_logon.ps1": runfiles.resolve_from_env("FIRST_LOGON"),
        },
    )

    _create_disk(commands, _DISK_PATH, disk_gib)
    click.echo(
        "Installing Windows. This takes about an hour. To watch it, open "
        + f"{vm.DOMAIN_NAME} in virt-manager under its QEMU/KVM User session."
    )
    virt_install_arguments = [
        commands["virt-install"],
        "--connect",
        vm.LIBVIRT_URI,
        "--name",
        vm.DOMAIN_NAME,
        # Debian 12's osinfo database predates Windows Server 2025, and
        # libvirt gives both versions the same virtual hardware. virt-install
        # gives this version BIOS firmware. Under UEFI, Windows media waits
        # for a key press before booting from CD, which stalls an unattended
        # install, but BIOS boots from CD without one while the disk is
        # still empty. libvirt cannot select BIOS by name on Fedora, which
        # has no firmware descriptor for it.
        "--osinfo",
        "win2k22",
        "--vcpus",
        str(vcpus),
        "--cpu",
        "host-passthrough",
        "--memory",
        str(memory_gib * 1024),
        "--disk",
        f"path={_DISK_PATH},format=qcow2,bus=virtio,discard=unmap,cache=none,"
        + "io=native",
        "--disk",
        f"path={virtio_iso},device=cdrom",
        "--disk",
        f"path={unattend_iso},device=cdrom",
        "--cdrom",
        str(windows_iso),
        "--network",
        # Only this host can reach the VM's SSH server, over IPv4 or IPv6.
        f"passt,model=virtio,portForward0=127.0.0.1:{ssh_port}:22,"
        + "portForward1.address=::1,portForward1.proto=tcp,"
        + f"portForward1.range0.start={ssh_port},portForward1.range0.to=22",
        # The guest agent shuts Windows down reliably. Windows can ignore the
        # virtual power button, such as when its display is off.
        "--channel",
        "unix,target.type=virtio,name=org.qemu.guest_agent.0",
        "--noautoconsole",
        "--wait",
        "-1",
    ]
    try:
        _ = subprocess.run(virt_install_arguments, check=True)
    except subprocess.CalledProcessError:
        # Without a VM that uses it, the new disk would only block the next run.
        if (
            vm.DOMAIN_NAME
            not in vm.virsh(commands["virsh"], "list", "--all", "--name").split()
        ):
            _DISK_PATH.unlink()
        raise
    # Windows shuts down when its first logon setup succeeds.
    vm.wait_for_shutoff(commands["virsh"])
    _eject_install_media(commands)
    unattend_iso.unlink()
    _ = vm.virsh(commands["virsh"], "start", vm.DOMAIN_NAME)
    vm.wait_for_ssh(commands["virsh"])
    click.echo(
        f"Windows is ready. Connect with `ssh -p {ssh_port} Administrator@localhost`. "
        + f"The console password is in {password_path}."
    )


if __name__ == "__main__":
    main()
