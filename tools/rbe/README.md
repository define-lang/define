# rbe

`rbe` runs Bazel's remote caching and execution on your own Linux machine. Each
action runs in its own directory, with its inputs hardlinked from a content
store on a dedicated XFS filesystem. Every build on the machine shares its
cache.

## Requirements

- Linux with systemd.
- `xfsprogs`, for `mkfs.xfs` and `xfs_growfs`.
- Free disk space for the store, 300 GiB by default. The store is an image file
  that takes space only as it fills.

## Setup

From your checkout, run:

```sh
sudo tools/rbe/deploy/setup.sh
bazelisk run //tools/rbe/deploy
```

The service runs as its own `rbe` user. The account that ran `setup.sh` with
`sudo` is the one that uses and deploys it: only that account's primary group
can connect to the service, and only that account can deploy new versions,
without a password. Pass `--size` to choose another store size, such as
`--size 500G`. Run `setup.sh` again after changing it or the unit files next to
it, or to grow the store.

`setup.sh` creates:

- The `rbe` system user, which runs the service and its actions.
- The store image, `/var/lib/rbe/store.img`, which `rbe-store.service` mounts at
  `/var/lib/rbe/store`.
- `rbe.socket`, `rbe.service` and `rbe-store.service` in `/etc/systemd/system`.
  systemd listens on `/run/rbe/rbe.sock` and starts the service when Bazel first
  connects.
- `/usr/local/libexec/rbe`, which holds the deployed binary.
- `/etc/sudoers.d/rbe`, which lets you restart the service without a password.

## Using it

Add these lines to your `~/.bazelrc`:

```
build --remote_executor=unix:///run/rbe/rbe.sock
# Remote actions don't use local runfiles trees, and building them took most of
# a warm build's time. Bazel still builds them for bazel run and local actions.
build --nobuild_runfile_links
```

Actions run as the `rbe` user, so they can't change your files.

## Deploying changes

After changing the code in `tools/rbe`, run:

```sh
bazelisk run //tools/rbe/deploy
```

This installs the new binary and restarts the service. A build that's running
keeps going: Bazel waits for the service to come back and runs again the actions
the restart cut off.

The service logs to the journal: `journalctl -u rbe.service`.

## Removing it

```sh
sudo tools/rbe/deploy/setup.sh --uninstall
```

This removes everything `setup.sh` created, including the store. Remove the
lines you added to `~/.bazelrc`.
