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

1. Copy your checkout's current state into the VM. This starts the VM if it is
   shut off and waits until SSH is ready:

   ```sh
   bazelisk run //tools/windows_vm:sync_windows_vm
   ```

   It copies everything git would commit, including uncommitted and untracked
   files, into `C:\src\<name>`, where `<name>` is the name of your checkout's
   directory, such as `C:\src\define4` for `~/projects/define4`. Run it again
   after each change you want to test. Its `--help` explains the details.

2. Run PowerShell 7 commands in your directory over SSH:

   ```sh
   ssh -p 2222 Administrator@localhost 'cd C:\src\define4; bazelisk build //...'
   ```

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
