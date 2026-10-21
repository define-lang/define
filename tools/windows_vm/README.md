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

If `define-windows` is listed, use it:

1. If its state is `shut off`, start it:

   ```sh
   virsh --connect qemu:///session start define-windows
   ```

2. Run PowerShell commands in it over SSH. The repository is in `C:\src\define`:

   ```sh
   ssh -p 2222 Administrator@localhost 'cd C:\src\define; bazelisk test //...'
   ```

3. Shut it down when you are done, so that it stops using the host's memory:

   ```sh
   virsh --connect qemu:///session shutdown define-windows
   ```

If `define-windows` is not listed, the VM does not exist yet. Agents should ask
the user before creating it, because creating it downloads 8 GB and takes about
an hour.

## The Evaluation Period

The Windows Server evaluation expires 180 days after setup. The VM extends it by
another 180 days by itself when it starts, or during its daily check at 03:00
UTC, once fewer than 14 days remain. Extending it restarts Windows, so SSH
becomes available only after that check.

Windows allows only a limited number of extensions. To see how many remain and
when the evaluation expires, run:

```sh
ssh -p 2222 Administrator@localhost 'cscript //nologo C:\Windows\System32\slmgr.vbs /dlv'
```

When no extensions remain, every SSH session starts with a warning that says
when the evaluation ends, beginning 14 days before. Recreate the VM then, as
`--help` describes.
