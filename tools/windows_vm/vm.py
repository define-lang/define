"""Control the Windows VM through libvirt."""

from __future__ import annotations

import subprocess

import click

DOMAIN_NAME = "define-windows"

# The port in the VM that its remote execution service listens on, and the
# port on this host that forwards to it. See deploy_rbe.py.
RBE_VM_PORT = 8980
DEFAULT_RBE_PORT = 2223

# A session VM needs no root access, libvirt group, or file permissions for the
# system's QEMU user.
LIBVIRT_URI = "qemu:///session"


def virsh(virsh_path: str, *arguments: str) -> str:
    """Run virsh on the libvirt session and return its output."""
    return subprocess.run(
        [virsh_path, "--connect", LIBVIRT_URI, *arguments],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _wait_for_event(virsh_path: str, event: str):
    arguments = [
        virsh_path,
        "--connect",
        LIBVIRT_URI,
        "event",
        "--domain",
        DOMAIN_NAME,
        "--event",
        event,
        "--timeout",
        "60",
    ]
    result = subprocess.run(arguments, check=False, capture_output=True, text=True)
    # virsh exits with 1 both when it fails and when its timeout expires.
    if result.returncode != 0 and "event loop timed out" not in result.stdout:
        raise subprocess.CalledProcessError(
            result.returncode, arguments, result.stdout, result.stderr
        )


def wait_for_shutoff(virsh_path: str):
    """Wait until the VM shuts off."""
    # Rechecking the state after each wait catches a shutdown that happens
    # before virsh starts listening for events.
    while virsh(virsh_path, "domstate", DOMAIN_NAME).strip() != "shut off":
        _wait_for_event(virsh_path, "lifecycle")


def _guest_agent_answers(virsh_path: str) -> bool:
    result = subprocess.run(
        [
            virsh_path,
            "--connect",
            LIBVIRT_URI,
            "qemu-agent-command",
            DOMAIN_NAME,
            '{"execute":"guest-ping"}',
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def wait_for_ssh(virsh_path: str):
    """Wait until the VM's SSH server accepts connections."""
    # extend_evaluation.ps1 starts the guest agent only after it starts sshd, so
    # the guest agent answering means that SSH is ready. Rechecking after each
    # wait catches an agent that connects before virsh starts listening.
    while not _guest_agent_answers(virsh_path):
        if virsh(virsh_path, "domstate", DOMAIN_NAME).strip() != "running":
            raise click.ClickException(f"{DOMAIN_NAME} stopped before SSH was ready.")
        _wait_for_event(virsh_path, "agent-lifecycle")
