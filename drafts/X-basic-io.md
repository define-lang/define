# Basic I/O

## First Step: Read One Byte

The first I/O operation reads one byte from standard input as a
`value</binary>`.

### Name

`operation<standard:/os/posix/read>`

- The operation's meaning is POSIX `read` with a count of one. POSIX is a
  written standard, so it gives the operation a precise meaning that doesn't
  depend on any one kernel.
- POSIX goes under `/os` rather than at the top of the standard universe,
  because the top-level standard namespace should stay small.
- POSIX doesn't go under `/io`, because POSIX is an operating system interface,
  not only an I/O one. The monotonic clock (`clock_gettime`), `getpid`, and
  signals are all POSIX, and none of them is I/O.
- POSIX's own function names are flat and unique (`read`, `pread`, `readv`,
  `readdir`…), so the Define names can follow them directly. Windows can later
  be a sibling, such as `/os/windows/read_file`.

### Behavior

- Binary values have no width, so the byte `0x05` reads as the binary value
  `101`, and `0x00` reads as `0`.
- Generated Python calls `os.read(0, 1)`. It returns `b""` at end of input, and
  otherwise one byte, whose `[0]` is a Python `int`, the same representation as
  `/binary/ascii`.
- `os.read` skips `sys.stdin`'s buffer, so all reading of standard input in
  generated Python must go through `os.read`.

### Open Questions

- **Views.** One option is an input view for the file descriptor (a natural
  number, looking at the literal `0` for standard input) plus an output view for
  the byte. That mirrors `read`, and it gives the compiler an input encoding to
  choose the encoding operation by. The other option is only an output view for
  the byte, which avoids promising `read`'s general behavior but needs replacing
  once file descriptors exist.
- **End of input.** One byte can't represent "no byte," and an output view's
  particle always has its value set by the operation. The options:
  - End of input and errors stop the program with an error. Nothing in the
    language changes.
  - The operation leaves its output view's particle unset at end of input
    (building on DLP 53). This needs a spec change and a way for a program to
    check whether a value is set.
  - A second, boolean output view for "reached end of input." The byte view
    still has nothing to hold at end of input, so this needs the previous option
    anyway.
- **Ordering.** Two reads give different results depending on which runs first,
  but every operation so far gets its result entirely from its input views, so
  the compiler is free to reorder them. DLP 44 covers ordering of create, move,
  and destroy statements and leaves ordering of value operations for a later
  proposal. One approach is to treat standard input as a particle in a position
  whose value the outside world changes, and let reads depend on that position.

## How Reading Works on Each Platform

Everywhere except the Windows console, the basic read is "copy up to N bytes
into a buffer and report how many were copied."

### Linux

- `ssize_t read(int fd, void *buf, size_t count)`. Standard input is file
  descriptor 0.
- System call number 0 on x86-64. Linux is the only major OS with a stable
  system call interface, so programs may call the kernel directly. glibc's
  `read()` is a thin wrapper.
- A result greater than 0 is the number of bytes copied. It can be fewer than
  requested even when more data is coming (a "short read"). 0 means end of
  input.
- The kernel returns one number, in `RAX`. Values from −4095 to −1 are errors,
  the negated error code. There is no separate error register or flag.

### macOS and the BSDs

- The same POSIX `read()`.
- The kernel returns the positive error code and sets the CPU's carry flag to
  mean "this is an error."
- Apple doesn't promise system call numbers. The stable interface is libSystem.
  OpenBSD blocks system calls that don't come from libc.

### Windows

- `ReadFile(handle, buf, count, &count_read, overlapped)`, with the handle from
  `GetStdHandle(STD_INPUT_HANDLE)`. `kernel32!ReadFile` calls
  `ntdll!NtReadFile`, which makes the system call. NT system call numbers change
  between builds, so the stable interface is kernel32.
- When standard input is a console, `ReadFile` returns bytes in the console's
  input code page, which is often a legacy one such as 437. `ReadConsoleW`
  returns UTF-16 code units. This is the only case on a major platform where a
  read returns something other than bytes.
- End of input: a file at its end returns `TRUE` with 0 bytes. A pipe whose
  writer closed returns `FALSE` with `ERROR_BROKEN_PIPE`. In a console, Ctrl-Z
  followed by Enter ends input.
- The C runtime opens standard input in text mode, which rewrites `\r\n` to `\n`
  and treats a Ctrl-Z byte as end of input, even for files and pipes.
  `_setmode(_fileno(stdin), _O_BINARY)` turns that off.

### WASI

- Preview 1: `fd_read(fd, iovs, iovs_len, *nread)`, with the same rules as POSIX
  `readv`.
- Preview 2: `wasi:io/streams`, where `input-stream.read(len)` returns a
  `list<u8>` or a `stream-error` (`closed` or a failure).

### Browsers

- There is no standard input. Byte streams are `ReadableStream`s that deliver
  `Uint8Array` chunks, read asynchronously.

### Terminals

Terminal behavior differs between platforms and no language makes it the same:
line editing and delivering input only after Enter, echoing typed characters,
Ctrl-D (Unix) versus Ctrl-Z then Enter (Windows) for end of input, and "raw
mode" for single keypresses. These happen before any bytes exist, so a byte read
can't hide them. Programs that care use `termios` on Unix or `SetConsoleMode` on
Windows.

## How Languages Implement Reading

Most languages implement the POSIX shape on every platform, special-case the
Windows console, and build buffering and text decoding as separate layers on
top.

| Language | Lowest-level read                            | End of input               | Errors                            |
| -------- | -------------------------------------------- | -------------------------- | --------------------------------- |
| C        | `read()` / `fread()` / `getc()`              | 0 bytes / `EOF` + `feof()` | −1 + `errno` / `EOF` + `ferror()` |
| Java     | `System.in.read()`, one byte as `int` 0–255  | `-1`                       | `IOException`                     |
| Rust     | `Read::read(&mut [u8]) -> io::Result<usize>` | `Ok(0)`                    | `Err(io::Error)`                  |
| Go       | `os.Stdin.Read([]byte) (int, error)`         | `io.EOF` error             | other `error` values              |
| Python   | `os.read(0, n)`                              | `b""`                      | `OSError`                         |
| Node.js  | `process.stdin` stream of `Buffer` chunks    | `'end'` event              | `'error'` event                   |

- **Interrupted reads (`EINTR`):** Rust, Go, and Python retry automatically. C
  doesn't.
- **Closed standard input:** Rust treats it as end of input.
- **Windows console:** Rust, Go, Python (PEP 528), and Node.js's libuv read
  UTF-16 with `ReadConsoleW` and convert it to UTF-8 bytes, so the byte layer
  gives the same results as a pipe or file on Linux.
- **Buffering:** done by the language, not the OS. Rust's `stdin()` has an 8 KiB
  buffer shared through a lock. Python layers a raw stream, a `BufferedReader`,
  and a `TextIOWrapper`. Go has no buffer unless the program adds
  `bufio.Reader`.
- **Calling the OS:** Rust's standard library calls libc everywhere, including
  Linux. Go makes raw system calls on Linux and calls libSystem on macOS. Zig
  calls the kernel directly on Linux and uses libc elsewhere.
- **Text decoding:** Rust requires valid UTF-8 and returns an error otherwise.
  Go doesn't check. Java and .NET use a configurable character set. Python uses
  the locale's encoding unless UTF-8 mode is on, and PEP 686 makes UTF-8 mode
  the default. Languages disagree on invalid bytes: raise an error, replace them
  with U+FFFD, or carry them through (Python's `surrogateescape`).
- **Line endings:** translated in the text layer by Python, C text mode, and
  .NET. Never translated by Rust or Go.

### How C's `getc` Works (glibc)

- `stdin` is a `FILE` with a buffer, a read position, and sticky end-of-input
  and error flags.
- If the buffer has bytes left, `getc` returns the next one with no system call.
  Otherwise it refills the buffer with one `read` of `st_blksize` bytes
  (usually 4096) or `BUFSIZ` (8192).
- Before reading from a terminal, it flushes line-buffered output streams, so
  prompts without a newline still appear.
- It doesn't retry `EINTR`. That shows up as an error unless the signal handler
  was installed with `SA_RESTART`.
- `getwc` decodes through the locale. In a UTF-8 locale it returns one Unicode
  scalar, but in the `C` locale it doesn't decode UTF-8 at all.

## Errors

### What POSIX Specifies for `read`

- "Shall fail" errors, such as `EAGAIN`, `EBADF`, `EINTR`, `EIO`, `EOVERFLOW`,
  and for sockets `ECONNRESET`, `ENOTCONN`, and `ETIMEDOUT`.
- "May fail" errors, such as `EIO` for a physical I/O error, `ENOBUFS`,
  `ENOMEM`, and `ENXIO`.
- Implementations may return additional errors, and may return listed errors in
  other situations. The list isn't closed.

### What Linux Returns from `read`

| Code     | Value | Meaning                                                             |
| -------- | ----- | ------------------------------------------------------------------- |
| `EINTR`  | 4     | A signal interrupted the call before any data was read              |
| `EIO`    | 5     | Low-level I/O error, or a background process read from its terminal |
| `EBADF`  | 9     | `fd` isn't open, or isn't open for reading                          |
| `EAGAIN` | 11    | Non-blocking stream and nothing is ready yet                        |
| `EFAULT` | 14    | The buffer address is outside the program's memory                  |
| `EISDIR` | 21    | `fd` is a directory                                                 |
| `EINVAL` | 22    | The object can't be read, or `O_DIRECT` alignment is wrong          |

"Other errors may occur, depending on the object connected to fd." Sockets add
`ECONNRESET` (104) and `ETIMEDOUT` (110), and drivers and filesystems add their
own. `EFAULT` isn't a POSIX error for `read`: in POSIX, a bad buffer is
undefined behavior.

- The codes are listed in `/usr/include/asm-generic/errno-base.h` (1–34) and
  `/usr/include/asm-generic/errno.h` (35 and up).
- The numbers differ by platform. `EAGAIN` is 11 on Linux and 35 on macOS.
  Alpha, MIPS, PA-RISC, and SPARC Linux use different numbers for some codes.
  Only the names are portable.
- The kernel's internal codes from 512 up (`ERESTARTSYS` and others) are turned
  into a restart or `EINTR` before returning, so programs never see them.
- `errno` isn't a kernel concept. It's a per-thread variable in the C library,
  which the libc wrapper sets from the kernel's negative return value.

### How Languages Handle Error Codes

Programs don't translate error codes when they compare against them. Error names
are compile-time constants that each platform's build fills in with its own
numbers:

- In C, `EAGAIN` is a macro, so `errno == EAGAIN` compiles to "compare with 11"
  on Linux and "compare with 35" on macOS.
- Go's `syscall.EAGAIN` is a constant from generated files for each OS and CPU,
  such as `zerrors_linux_amd64.go`.

Translation happens only when a call fails, and only when the program asks for
something portable or readable:

- Rust stores the raw platform code in `io::Error`, and `.kind()` turns it into
  a portable `ErrorKind` with a `match` when called.
- Go's `errors.Is(err, fs.ErrNotExist)` checks a raw `Errno` against a portable
  category when called.
- Python picks an `OSError` subclass (`FileNotFoundError`, `BlockingIOError`…,
  PEP 3151) with a dictionary lookup on the error number.
- `strerror` indexes a table of messages.
- The Windows C runtime maps Windows error codes to `errno` values through a
  table (`_dosmaperr`). This is the one real translation, and it only happens on
  failure.

### What This Means for Define

- `/os/posix/read` promises errors by POSIX name, not by number, and promises
  only "an error with a name," not a fixed set. A Define error model should
  treat the POSIX names as known cases and have a case for any other error the
  platform reports.
- Error names fit the value/encoding split. The value is the POSIX error (`EIO`,
  `EAGAIN`), the encoding is the platform's number, and a literal naming an
  error would be turned into the target's number at compile time by a literal
  parser. Checking for a specific error then compiles to a single integer
  comparison. Converting to another platform's numbers or to a message would be
  an encoding converter, used only when a call fails.
- In Python, `errno.errorcode[e.errno]` gives the name and `os.strerror` gives
  the message.

## How Verified Languages Order I/O

### SPARK (Ada): Properties of External State

SPARK describes each thing the outside world can see or change as **external
state**: a volatile variable (often placed at a device register's address) or an
`Abstract_State` declared `External` that stands for a whole device or stream.
Four boolean properties describe how the outside world interacts with it:

- **`Async_Writers`:** the outside world may change it at any time. Proof can't
  assume two reads give the same value, and can't assume any particular value.
  Example: a sensor.
- **`Async_Readers`:** the outside world may observe it at any time. Example: an
  actuator.
- **`Effective_Reads`:** reading it changes it. Each read consumes something,
  like the next byte of an input port. Requires `Async_Writers`.
- **`Effective_Writes`:** every write matters, and the final value is considered
  to be the whole sequence of values written, not just the last one. Two writes
  in a row can't be merged into one. Example: an output port. Requires
  `Async_Readers`.

A plain `Volatile` object has all four. Once any one is specified, the rest
default to false. Typical combinations: a sensor is `Async_Writers`, an actuator
is `Async_Readers`, an input port is `Async_Writers` + `Effective_Reads`, and an
output port is `Async_Readers` + `Effective_Writes`.

How the properties enter the rest of the language:

- **Every subprogram declares which state it touches.** A `Global` contract
  lists each piece of state with a mode (`Input`, `Output`, `In_Out`), and a
  `Depends` contract says which outputs depend on which inputs. Flow analysis
  checks the body against both.
- **With `Effective_Reads`, a read is also a write.** Reading an input port must
  be declared `In_Out`, with `Depends => (Port => Port)`. So reads of the same
  input port depend on each other, and the order comes from ordinary data flow,
  not from a separate ordering rule.
- **Restrictions keep these reads visible.**
  - A read of an `Async_Writers` object must be the entire right-hand side of an
    assignment, so it can't hide inside a larger expression.
  - Ordinary functions can't read external state at all, because SPARK functions
    must be free of side effects. A function may read `Async_Writers` state (but
    not `Effective_Reads` state) if it's marked `Volatile_Function`, and calls
    to it have the same restrictions as a direct read.
- **Abstract state hides the details but keeps the properties.** A package can
  declare
  `Abstract_State => (Port with External => (Async_Writers, Effective_Reads))`
  and later refine it into concrete variables. The concrete variables must not
  have properties the abstract state didn't declare. Callers only see the
  abstract state and its properties.

SPARK executes statements in the order written, so these properties are used for
analysis rather than for reordering. What carries over is the dependency model:
operations on different external states have no dependency between them, and the
properties say exactly when operations on the same state depend on each other.

To copy this design into Define:

- Model each stream or device as a particle with properties corresponding to the
  four above.
- Treat reading a particle with the `Effective_Reads` property as both reading
  and changing it, so that position dependencies (DLP 44) keep reads of the same
  stream in order.
- Let operations on different particles be reordered freely.
- Forbid merging writes to a particle with the `Effective_Writes` property.

### IronFleet (Dafny): Reduction

IronFleet verifies distributed systems: several hosts, each running its own
single-threaded program, communicating only by UDP packets. The proofs are
simplest if each host's step (receive packets, compute, send packets) happens
atomically, with no other host's operations in between. In reality, all hosts
run at the same time and their operations interleave arbitrarily. IronFleet
bridges the gap with **reduction**: proving that any real interleaving is
equivalent to one where each host's step is contiguous.

The pieces:

- **A trusted UDP interface.** Dafny has no networking, so IronFleet adds
  trusted `Init`, `Send`, and `Receive` methods that call the .NET UDP stack.
- **A journal of I/O events.** The network interface keeps a ghost variable (one
  that exists only for verification and isn't compiled) recording every send and
  receive, with all arguments and return values.
- **A mandatory main loop.** Each host runs `ImplInit` and then repeats
  `ImplNext` forever. Each iteration returns the list of I/O events it
  performed, and the loop asserts that the journal grew by exactly those events
  and that they satisfy the **reduction-enabling obligation**:

  ```dafny
  method Main() {
    var s := ImplInit();
    while (true)
      invariant ImplInvariant(s);
    {
      ghost var journal_old := get_event_journal();
      ghost var ios_performed:seq<IoEvent>;
      s, ios_performed := ImplNext(s);
      assert get_event_journal() == journal_old + ios_performed;
      assert ReductionObligation(ios_performed);
    }
  }
  ```

- **The obligation.** Within one step, a host performs all of its receives
  before all of its sends. Time-dependent operations get an extra rule, because
  a clock reading is a sample of a reality shared with every other host and so
  creates an ordering constraint with them even without any messages. A step may
  perform at most one time-dependent operation: a clock read, a blocking
  receive, or a non-blocking receive that returns nothing. All receives must
  come before it and all sends after it.

Why the obligation is enough: hosts can't see each other's state, only the
packets they send. So any real execution can be rearranged into another one,
keeping:

1. each host receiving the same packets in the same order,
2. the order of packet sends,
3. every packet being sent before it's received,
4. the order of operations on each individual host.

Any proof about the rearranged execution also holds for the real one, because
only the packets sent, their contents and their order, are visible from outside.
Receives can always move earlier: whatever was received was already sent. Sends
can always move later: nothing another host did in between can depend on a
packet that hadn't arrived. When each step does all receives before all sends,
these moves can pull each step's operations together until no other host's
operations sit between them. The paper argues this informally; the
machine-checked part is only that every step obeys the obligation.

The implementation itself doesn't reorder anything. Each host still runs its
operations in program order. The reduction argument only lets the proof treat
each step as one atomic action.

To copy this design into Define:

- Keep a record of the I/O events each action performs, as a value that exists
  only for analysis.
- Classify each kind of I/O event by which way it can move relative to other
  hosts' or processes' events: receives can move earlier and sends can move
  later, while time-dependent events (clock reads, receives that wait or find
  nothing) can move in neither direction.
- Require each action's events to follow the pattern "receives, then at most one
  time-dependent event, then sends." Actions that follow it can be treated as
  atomic with respect to the outside world.

### Sources

- AdaCore,
  [Advanced SPARK: Systems Programming](https://learn-latest.adacore.com/courses/advanced-spark/chapters/systems_programming.html).
- [SPARK Reference Manual: Packages](https://docs.adacore.com/spark2014-docs/html/lrm/packages.html).
- Hawblitzel et al.,
  [IronFleet: Proving Practical Distributed Systems Correct](https://www.andrew.cmu.edu/user/bparno/papers/ironfleet.pdf),
  SOSP 2015, sections 2.3, 3.4, 3.6, and 3.7.

## Related

- [I/O alternatives](io-alternatives.md): ways to avoid the kernel's extra copy
  or extra system calls, and which apply to standard input.
