"""Copy a checkout's current state into its own directory in the Windows VM."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import click

from tools.windows_vm import vm

_REQUIRED_COMMANDS = ("git", "ssh", "virsh")

# The snapshot commit is never pushed anywhere but the VM, so it does not need
# the user's identity, and a fixed one works where no identity is configured.
_SNAPSHOT_IDENTITY = {
    "GIT_AUTHOR_NAME": "Windows VM sync",
    "GIT_AUTHOR_EMAIL": "windows-vm-sync@localhost",
    "GIT_COMMITTER_NAME": "Windows VM sync",
    "GIT_COMMITTER_EMAIL": "windows-vm-sync@localhost",
}

_SSH_OPTIONS = ("-o", "BatchMode=yes", "-o", "ConnectTimeout=10")

_HELP = """\
Copy the current directory's checkout into its own directory in the Windows VM.

\b
Build it once in a Define checkout, then run it from any checkout:
  bazelisk build //tools/windows_vm:sync_windows_vm
  <Define checkout>/bazel-bin/tools/windows_vm/sync_windows_vm

The VM directory is C:\\src\\ followed by the name of the checkout's
directory, such as C:\\src\\define4 for ~/projects/define4. The command
starts the VM if it is shut off, and waits until its SSH server is ready.

It copies every file that git would commit: committed, modified, staged, and
untracked files, but not ignored files. It does this through a snapshot
commit, without changing this checkout's branch, index, or files. The VM
directory then has exactly that state, detached from any branch. Files
there that the snapshot does not have are deleted, except ignored files,
such as Bazel's output links.

See tools/windows_vm/README.md for how to use the VM.
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


def _git(
    git: str,
    checkout: Path,
    *arguments: str,
    environment: dict[str, str] | None = None,
) -> str:
    return subprocess.run(
        [git, *arguments],
        cwd=checkout,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def snapshot_commit(git: str, checkout: Path) -> str:
    """Commit the checkout's working tree without changing its branch or index."""
    checkout_index = checkout / _git(git, checkout, "rev-parse", "--git-path", "index")
    with tempfile.TemporaryDirectory() as directory:
        index = Path(directory) / "index"
        # Starting from the checkout's index lets git skip unchanged files.
        _ = shutil.copy(checkout_index, index)
        environment = {**os.environ, "GIT_INDEX_FILE": str(index)}
        _ = _git(git, checkout, "add", "--all", environment=environment)
        tree = _git(git, checkout, "write-tree", environment=environment)
    return _git(
        git,
        checkout,
        "commit-tree",
        tree,
        "-p",
        _git(git, checkout, "rev-parse", "HEAD"),
        "-m",
        f"Snapshot of {checkout} for the Windows VM",
        environment={**os.environ, **_SNAPSHOT_IDENTITY},
    )


@click.command(help=_HELP, context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--ssh-port",
    type=int,
    default=2222,
    show_default=True,
    help="Port on localhost that forwards to the VM's SSH server.",
)
def main(ssh_port: int):
    """Copy the current directory's checkout into the Windows VM."""
    commands = _resolve_commands()
    checkout = Path(_git(commands["git"], Path.cwd(), "rev-parse", "--show-toplevel"))
    virsh = commands["virsh"]
    if vm.DOMAIN_NAME not in vm.virsh(virsh, "list", "--all", "--name").split():
        raise click.ClickException(
            f"{vm.DOMAIN_NAME} does not exist. See tools/windows_vm/README.md."
        )
    if vm.virsh(virsh, "domstate", vm.DOMAIN_NAME).strip() == "shut off":
        click.echo(f"Starting {vm.DOMAIN_NAME}...")
        _ = vm.virsh(virsh, "start", vm.DOMAIN_NAME)
    vm.wait_for_ssh(virsh)

    commit = snapshot_commit(commands["git"], checkout)
    vm_directory = f"C:\\src\\{checkout.name}"
    ssh = [
        commands["ssh"],
        *_SSH_OPTIONS,
        "-p",
        str(ssh_port),
        "Administrator@localhost",
    ]
    _ = subprocess.run([*ssh, f"git init --quiet '{vm_directory}'"], check=True)
    _ = subprocess.run(
        [
            commands["git"],
            "push",
            "--quiet",
            "--force",
            # Git for Windows has git-receive-pack only outside PATH.
            "--receive-pack=git receive-pack",
            # An ssh:// URL would give Windows the path /C:/src/..., which git
            # rejects, so the port goes in GIT_SSH_COMMAND instead.
            f"Administrator@localhost:C:/src/{checkout.name}",
            f"{commit}:refs/heads/windows-vm-snapshot",
        ],
        cwd=checkout,
        env={
            **os.environ,
            "GIT_SSH_COMMAND": " ".join(
                [commands["ssh"], *_SSH_OPTIONS, "-p", str(ssh_port)]
            ),
        },
        check=True,
    )
    _ = subprocess.run(
        [*ssh, f"git -C '{vm_directory}' checkout --quiet --force --detach {commit}"],
        check=True,
    )
    _ = subprocess.run(
        [*ssh, f"git -C '{vm_directory}' clean --quiet --force -d"], check=True
    )
    click.echo(
        f"{vm_directory} in the VM now has this checkout's current state, as "
        + f"commit {commit[:12]}."
    )


if __name__ == "__main__":
    main()
