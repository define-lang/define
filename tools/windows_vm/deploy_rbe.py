"""Install or update the Windows VM's remote execution service."""

from __future__ import annotations

import os
import shutil
import subprocess
import xml.etree.ElementTree as ET  # noqa: S405 - It parses only virsh's output.
from pathlib import Path, PureWindowsPath

import click

from tools import runfiles
from tools.windows_vm import vm

_REQUIRED_COMMANDS = ("bazelisk", "scp", "ssh", "virsh")

_SSH_OPTIONS = ("-o", "BatchMode=yes", "-o", "ConnectTimeout=10")

_SERVICE_DIRECTORY = "C:\\rbe"
_BIN_DIRECTORY = PureWindowsPath(_SERVICE_DIRECTORY, "bin")

# The VM's disk is shared and scarce.
_MAX_CAS_BYTES = 30 << 30

_HELP = f"""\
Install or update the Windows VM's remote execution service.

\b
Build and run it from a Define checkout:
  bazelisk run //tools/windows_vm:deploy_rbe

It builds rbe for Windows and installs it in the VM as the Windows service
rbe, which starts at boot and restarts if it fails. Its store and action
directories are in {_SERVICE_DIRECTORY}. It serves on port {vm.RBE_VM_PORT} in
the VM, which the VM forwards to a port on localhost, {vm.DEFAULT_RBE_PORT} by
default. Every account on this machine can use that port to run commands in
the VM.

A VM made before this port was forwarded needs the forward added to its
definition. The command adds it, and the forward starts working the next time
the VM starts. It never restarts the VM itself, since other checkouts may be
using it.

See tools/windows_vm/README.md for how to run tests on the VM.
"""


def _resolve_commands() -> dict[str, str]:
    paths: dict[str, str] = {}
    missing: list[str] = []
    for command in _REQUIRED_COMMANDS:
        path = shutil.which(command)
        if path is None:
            missing.append(command)
        else:
            paths[command] = path
    if missing:
        raise click.ClickException(f"Missing commands: {', '.join(missing)}.")
    return paths


def _forwards_port(definition: ET.Element, rbe_port: int) -> bool:
    for forward in definition.iterfind("devices/interface/portForward"):
        for port_range in forward.iterfind("range"):
            if port_range.get("start") == str(rbe_port):
                return True
    return False


def add_rbe_port_forward(definition_xml: str, rbe_port: int) -> str | None:
    """Return the VM definition with the remote execution port forwarded.

    Returns None if the definition already forwards it.
    """
    definition = ET.fromstring(definition_xml)  # noqa: S314 - virsh's output.
    if _forwards_port(definition, rbe_port):
        return None
    interface = definition.find("devices/interface[@type='user']")
    if interface is None:
        raise click.ClickException(
            f"{vm.DOMAIN_NAME} has no passt network interface to forward a port on."
        )
    # Only this host can reach the service, over IPv4 or IPv6.
    for address in ("127.0.0.1", "::1"):
        forward = ET.SubElement(
            interface, "portForward", {"proto": "tcp", "address": address}
        )
        _ = ET.SubElement(
            forward, "range", {"start": str(rbe_port), "to": str(vm.RBE_VM_PORT)}
        )
    return ET.tostring(definition, encoding="unicode")


def _build_rbe(bazelisk: str) -> Path:
    """Build rbe for Windows in the checkout that bazel run started in."""
    # Building it from this command, instead of as a dependency, keeps a Windows
    # program out of every other build, since it needs Microsoft's runtime.
    workspace = Path(os.environ["BUILD_WORKSPACE_DIRECTORY"])
    arguments = ["--config=windows_cross", "//tools/rbe"]
    _ = subprocess.run([bazelisk, "build", *arguments], cwd=workspace, check=True)
    output = subprocess.run(
        [bazelisk, "cquery", "--output=files", *arguments],
        cwd=workspace,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return workspace / output


@click.command(help=_HELP, context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--ssh-port",
    type=int,
    default=2222,
    show_default=True,
    help="Port on localhost that forwards to the VM's SSH server.",
)
@click.option(
    "--rbe-port",
    type=int,
    default=vm.DEFAULT_RBE_PORT,
    show_default=True,
    help="Port on localhost that forwards to the VM's remote execution service.",
)
def main(ssh_port: int, rbe_port: int):
    """Install or update the Windows VM's remote execution service."""
    commands = _resolve_commands()
    rbe = _build_rbe(commands["bazelisk"])
    virsh = commands["virsh"]
    if vm.DOMAIN_NAME not in vm.virsh(virsh, "list", "--all", "--name").split():
        raise click.ClickException(
            f"{vm.DOMAIN_NAME} does not exist. See tools/windows_vm/README.md."
        )
    updated = add_rbe_port_forward(
        vm.virsh(virsh, "dumpxml", "--inactive", vm.DOMAIN_NAME), rbe_port
    )
    if updated is not None:
        _ = subprocess.run(
            [virsh, "--connect", vm.LIBVIRT_URI, "define", "/dev/stdin"],
            input=updated,
            check=True,
            capture_output=True,
            text=True,
        )
    if vm.virsh(virsh, "domstate", vm.DOMAIN_NAME).strip() == "shut off":
        click.echo(f"Starting {vm.DOMAIN_NAME}...")
        _ = vm.virsh(virsh, "start", vm.DOMAIN_NAME)
    # A running VM keeps the definition it started with.
    restart_needed = (
        add_rbe_port_forward(vm.virsh(virsh, "dumpxml", vm.DOMAIN_NAME), rbe_port)
        is not None
    )
    vm.wait_for_ssh(virsh)

    ssh = [
        commands["ssh"],
        *_SSH_OPTIONS,
        "-p",
        str(ssh_port),
        "Administrator@localhost",
    ]
    _ = subprocess.run(
        [
            *ssh,
            f"$null = New-Item -ItemType Directory -Force '{_BIN_DIRECTORY}'",
        ],
        check=True,
    )
    script = PureWindowsPath(_BIN_DIRECTORY, "install_rbe.ps1")
    for source, destination in (
        (rbe, PureWindowsPath(_BIN_DIRECTORY, "rbe.exe.new")),
        (runfiles.resolve_from_env("INSTALL_RBE"), script),
    ):
        _ = subprocess.run(
            [
                commands["scp"],
                "-q",
                *_SSH_OPTIONS,
                "-P",
                str(ssh_port),
                str(source),
                f"Administrator@localhost:{destination.as_posix()}",
            ],
            check=True,
        )
    _ = subprocess.run(
        [
            *ssh,
            f"pwsh -NoProfile -NonInteractive -File '{script}' -Root '{_SERVICE_DIRECTORY}'"
            + f" -Port {vm.RBE_VM_PORT} -MaxCasBytes {_MAX_CAS_BYTES}",
        ],
        check=True,
    )
    click.echo(f"Deployed rbe to {vm.DOMAIN_NAME}.")
    if restart_needed:
        click.echo(
            f"Restart {vm.DOMAIN_NAME} when no one is using it, so that "
            + f"localhost:{rbe_port} forwards to the service."
        )


if __name__ == "__main__":
    main()
