# Windows VM

A tool that creates a local Windows Server virtual machine for building and
testing Define on Windows. For what it does and its options, run:

```sh
bazelisk run //tools/windows_vm:create_windows_vm -- --help
```

## Using the VM

Each machine needs only one VM. **Do not create a new VM if one already
exists.** Check first:

```sh
virsh --connect qemu:///session list --all
```

If `define-windows` is not listed, the VM does not exist yet. Agents should ask
the user before creating it, because creating it downloads 8 GB and takes about
an hour.

If `define-windows` is listed, use it:

1. Build the sync tool once in a Define checkout:

   ```sh
   bazelisk build //tools/windows_vm:sync_windows_vm
   ```

   Then, from the checkout you want to test, which can be any git checkout, run
   it from that Define checkout's `bazel-bin` to copy your checkout's current
   state into the VM. This starts the VM if it is shut off and waits until SSH
   is ready:

   ```sh
   "<Define checkout>/bazel-bin/tools/windows_vm/sync_windows_vm"
   ```

   Don't use `bazelisk run`, because the tool copies the checkout of the
   directory it runs in, and `bazelisk run` runs it in its runfiles.

   It copies everything git would commit, including uncommitted and untracked
   files, into `C:\src\<name>`, where `<name>` is the name of your checkout's
   directory, such as `C:\src\define4` for `~/projects/define4`. Run it again
   after each change you want to test. Its `--help` explains the details.

2. Run PowerShell 7 commands in your directory over SSH:

   ```sh
   ssh -p 2222 Administrator@localhost 'cd C:\src\define4; bazelisk build //...'
   ```

## Running Tests on the VM

`--config=windows_vm` builds everything on this host for Windows, as
`--config=windows_cross` does, and runs the tests in the VM. Results, logs,
`--test_filter` and cached results work as in any `bazelisk test`:

```sh
bazelisk test --config=windows_vm //...
```

The VM runs a remote execution service that only runs tests; every other action
runs on this host. Linux runs these tests instead, so the VM skips them:

- Clippy tests, because their runner is a Linux program.
- Tests tagged `local`, which Bazel runs only on this host.
- skylib unittests, tagged `skylib_unittest`, whose results don't depend on the
  platform.
- Tests tagged `no_windows_vm`, which need something the cross build or the VM
  lacks.

### Setting it up

1. Install or update the service in the VM. Run this again after changing
   `tools/rbe`:

   ```sh
   bazelisk run //tools/windows_vm:deploy_rbe
   ```

   The service listens in the VM on port 8980, and the VM forwards
   `localhost:2223` on this host to it. Any account on this machine can use that
   port to run commands in the VM. A VM created before this forward existed gets
   it from `deploy_rbe`, but only after the VM restarts, which `deploy_rbe`
   tells you about and leaves to you.

2. In each checkout that uses `--config=windows_vm`, make the `bazel_tools` that
   it needs, and make it again after each Bazel upgrade:

   ```sh
   bazelisk run //tools/windows_vm:bazel_tools_override
   ```

   Bazel on Linux lacks `tw.exe` and `xml.exe`, which every test needs on
   Windows (bazelbuild/bazel#19209). This copies them from the Windows release
   of the same Bazel version into `.windows_vm/` in the checkout. Without it,
   `--config=windows_vm` fails because the directory doesn't exist. After a
   Bazel upgrade, it fails because Bazel "is not compatible with module
   bazel_tools" until you run this again.

The service's store and action directories are in `C:\rbe`, and it keeps up to
30 GiB of blobs there. Its messages are in the Application event log, from the
source `rbe`.

## Sharing the VM

Several agents may use the VM at once, so:

- **Work only in your checkout's own directory.** Never change another
  checkout's directory. Bazel keeps a separate server and output tree for each
  directory, so builds in different directories do not interfere.
- **Do not shut the VM down or restart it.** Another agent may be building in
  it. Only the user shuts it down.
- **Memory is shared.** The VM has 8 GB by default, and each Bazel server in it
  takes 1 to 3 GB while builds run, so run only a few builds at once. When a
  build fails because the VM ran out of memory, stop idle Bazel servers in your
  own directory with `bazelisk shutdown`.
- **The remote execution service is shared.** Every checkout's
  `--config=windows_vm` tests run in the one service. Deploying it restarts the
  service, which can fail other checkouts' running tests.

## Shutting the VM Down

To give the host back the VM's memory, shut it down through the QEMU guest
agent, which works even when Windows' display is off:

```sh
virsh --connect qemu:///session shutdown --mode agent define-windows
```

## The Evaluation Period

The Windows Server evaluation expires 180 days after setup. The VM extends it by
another 180 days by itself when it starts, or during its daily check at 03:00
UTC, once fewer than 14 days remain. Extending it restarts Windows, so SSH
becomes available only after that check.

Windows Server 2025 allows only one extension, so the VM lasts about a year. To
see how many extensions remain and when the evaluation expires, run:

```sh
ssh -p 2222 Administrator@localhost 'cscript //nologo C:\Windows\System32\slmgr.vbs /dlv'
```

When no extensions remain, every SSH session starts with a warning that says
when the evaluation ends, beginning 14 days before. Recreate the VM then, as
`--help` describes.
