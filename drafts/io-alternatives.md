# Alternatives to Buffered Reads on Linux

The ordinary way to read input on Linux is the `read` system call. The kernel
keeps the data in its own memory, and each `read` copies some of it into the
program's memory. Each call costs a trip into the kernel and back (roughly 100
to a few hundred nanoseconds), plus the copy itself.

For small reads, the trip into the kernel costs far more than the copy. Copying
memory runs at about 10–20+ GB per second, so copying a 4 KiB chunk takes a few
hundred nanoseconds or less. The usual fix is to make fewer trips with bigger
chunks, which is what C's `getc` does with its buffer. The copy only becomes the
main cost when moving very large amounts of data, such as gigabytes per second
from a fast network or disk.

The kernel keeps its own buffer for reasons beyond the cost of the trip:

- **Data often arrives before the program asks for it.** Keystrokes, network
  packets, and another program's writes to a pipe arrive whenever they arrive.
  If the program isn't in `read` at that moment, the data has to wait somewhere.
- **One copy serves many programs.** File data in the kernel's cache (the "page
  cache") is shared. If ten programs read the same file, the disk is read once
  and the kernel keeps one copy in memory.
- **Safety.** Another thread in the program can change program memory at any
  moment. The kernel can't safely check or process data that the program can
  change while the kernel is looking at it.
- **Hardware needs memory that stays put.** A device that copies data into RAM
  by itself needs that memory pinned in place, so that the OS can't move it or
  swap it to disk during the transfer. Kernel buffers are always pinned. Program
  memory usually isn't.

When the extra trips or copies do matter, Linux offers these alternatives.

## Memory-Mapping a File (`mmap`)

The kernel makes its cached copy of a file appear directly in the program's
memory. The program reads the file by reading memory: no copy, and no system
call per read. The first time the program touches each page of the file, the CPU
stops the program and the kernel loads that page, but later reads of the same
page cost nothing extra.

- **Works for:** regular files.
- **Doesn't work for:** terminals, pipes, or network connections, because their
  data isn't sitting in a cache that can be mapped.
- **Costs:** an I/O error while reading a mapped file arrives as a signal
  (`SIGBUS`) rather than an error return, which is harder to handle. If another
  program shortens the file while it's mapped, reading past the new end also
  raises `SIGBUS`.

## `io_uring`

The program and the kernel share two queues in memory: one for requests and one
for results. The program writes many read requests into the request queue, makes
a single system call to tell the kernel to look at them, and later picks up the
results from the result queue. If the program asks for it, a kernel thread
watches the request queue continuously, and the program makes no system calls at
all.

- **Works for:** files, pipes, network connections, and most other kinds of
  streams.
- **Avoiding copies:** the program can register its buffers with the kernel up
  front, so the kernel doesn't have to look them up and pin them on every
  request. Newer kernels can also receive network data directly into program
  buffers without a copy.
- **Costs:** a much more complex interface than `read`. Some environments
  (certain container setups, and Android) disable it because of its history of
  security bugs.

## Moving Data Between Two Streams (`splice`, `sendfile`)

These move data from one stream to another without it ever entering the
program's memory. For example, a web server can send a file to a network
connection with `sendfile`, and the kernel moves the data from its file cache
directly to the network.

- **Works for:** cases where the program only needs to pass data along, not look
  at it. `splice` requires one of the two streams to be a pipe.
- **Doesn't work for:** cases where the program needs to read the data itself.

## Direct Disk Reads (`O_DIRECT`)

Opening a file with `O_DIRECT` makes the disk copy data straight into the
program's buffer, skipping the kernel's file cache. Databases use this because
they keep their own cache and don't want the kernel keeping a second copy of the
same data.

- **Works for:** files on disks and filesystems that support it.
- **Costs:** the program's buffer, the file position, and the amount read must
  usually be aligned to the disk's block size (often 512 or 4096 bytes). There's
  no caching, so a program that doesn't do its own caching gets slower, not
  faster.

## Bypassing the Kernel Entirely (DPDK, SPDK, RDMA, AF_XDP)

The network card or SSD is handed to the program, which talks to the device
directly. The device copies data straight into program memory, and the program
checks for new data in a tight loop instead of waiting for the kernel to wake it
up. There are no system calls and no kernel copies.

- **DPDK:** networking. The program drives the network card itself.
- **SPDK:** storage. The program drives NVMe SSDs itself.
- **RDMA:** networking between machines. One machine's network card reads or
  writes another machine's memory directly.
- **AF_XDP:** networking, but with the kernel still in charge of the network
  card. Packets selected by a small program loaded into the kernel go straight
  into memory the program shares with the kernel.
- **Used in:** high-frequency trading, storage systems, and supercomputing.
- **Costs:** for DPDK and SPDK, the device belongs to one program, so the
  kernel's sharing, protection, and tools (such as `tcpdump` and normal
  filesystems) don't apply to it. Checking for data in a loop keeps a CPU core
  busy all the time, even when no data is arriving.

## Standard Input

Which of these alternatives apply to standard input depends on what it's
connected to, which can be different on every run of the program:

| Standard input is…   | Example                   | `mmap`  | `io_uring`         | `splice` / `sendfile`               | `O_DIRECT`  | Kernel bypass |
| -------------------- | ------------------------- | ------- | ------------------ | ----------------------------------- | ----------- | ------------- |
| A terminal           | `./prog`                  | No      | Yes, but pointless | No                                  | No          | No            |
| A pipe               | `cat x \| ./prog`         | No      | Yes                | `splice`, only to pass data along   | No          | No            |
| A regular file       | `./prog < x`              | **Yes** | Yes                | `sendfile`, only to pass data along | Technically | No            |
| A network connection | systemd socket activation | No      | Yes                | `splice`, only to pass data along   | No          | No            |

- **Only `mmap` is a real gain when the program reads the bytes itself, and only
  when standard input is a regular file.** GNU grep and ripgrep do this for
  files. One catch: the program shares its position in the file with whatever
  process gave it the file, usually the shell. So it has to start from the
  current position rather than the beginning, and move that position forward to
  match what it consumed. Otherwise a command like `(./prog; ./other) < x`
  breaks.
- **`io_uring` works on all of them but adds little for one stream read in
  order.** A buffered `read` already makes few trips into the kernel. Its real
  benefit is letting the program keep working while a read is pending, which
  matters only once a program handles several streams, or I/O and computation,
  at the same time.
- **`splice` and `sendfile` only pass data along.** They help a program that
  forwards its input to standard output or a file without looking at it, not one
  that reads bytes.
- **`O_DIRECT` isn't worth it here.** The setting applies to the shell's open
  file too, not just the program, so turning it on would affect other processes.
  It also gives up caching.
- **Kernel bypass doesn't apply.** Standard input isn't a device the program
  owns.
- **Pipes always involve two copies**, from the writer into the kernel's pipe
  buffer and then into the reader. The reader can't avoid either one, because
  the writer is a different program.
- **Terminals don't need to be fast.** People type a few bytes per second, so
  how it's implemented makes no difference.

So for standard input, the realistic choices are a buffered `read` in every
case, plus `mmap` as a fast path when the input turns out to be a regular file.
That can't be decided at compile time. The runtime has to check what file
descriptor 0 is (with `fstat`) when the program starts.

## What This Means for Define

Programs mean the same thing whichever of these the compiler uses. A program
that reads one byte at a time has the same behavior whether the compiler emits
one `read` per byte, a buffered `read`, `mmap` for files, or batches through
`io_uring`. So "read one byte" can be an abstract operation, and the compiler
can choose the implementation based on what the stream is and how the program
uses it. The simplest correct implementation is one `read` per byte
(`os.read(0, 1)` in generated Python). A faster implementation can come later
without changing any Define program.
