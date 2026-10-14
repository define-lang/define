# `getpid` Notes

## Why `getpid`

Reading a byte from standard input brings in failure and byte sequences.
`getpid` avoids both, which makes it the simplest first I/O operation:

- **It can't fail.** POSIX says: "The `getpid()` function shall always be
  successful and no return value is reserved to indicate an error." Windows'
  `GetCurrentProcessId()` also has no failure case.
- **No sequence.** It returns one number. `pid_t` is a signed integer type, but
  process IDs are always positive, so the result fits `value</number/natural>`.
  On Linux it's at most about 4 million (`pid_max` tops out at 2^22).
- **The same behavior on every POSIX system:** a positive number that identifies
  this process and stays the same for the whole run.
- **No ordering problem.** The value is constant for the life of the process, so
  the compiler may run it at any point, reorder it, or merge two executions of
  it.

### Other Candidates

- `getuid()` / `getgid()`: the same "shall always be successful" guarantee, and
  also constant. Windows has no numeric user IDs (it uses SIDs), so they're
  POSIX-only in a way the process ID isn't.
- `isatty(0)`: whether standard input is a terminal, as a boolean. Any problem
  just means "no," but it sets `errno` when the answer is "no."
- `_exit` with success or failure: can't fail and never returns, but it's a
  value going out rather than coming in, and it needs a design for what ending
  the program means in Define.
- The monotonic clock: also can't fail in practice and returns one number, but
  its result depends on when it runs, so it needs an ordering design first.

## Name

`operation<standard:/os/posix/getpid>`, with one output view whose particle has
`value</number/natural>`. This follows the decision to put POSIX under `/os` and
mirror POSIX's own function names (see [Basic I/O](X-basic-io.md)).

## Open Question: No Input Views

The operation has no input views. The spec chooses the encoding operation from
the encodings of the input views, so it needs a rule for this case, such as
choosing by the output view's encoding.

## Where It Works

- **Natively:** Linux, macOS, the BSDs, Android, and iOS through `getpid()`.
  Windows through `GetCurrentProcessId()` (or the C runtime's `_getpid`), which
  is also what Python's `os.getpid()` calls there.
- **No real process ID:**
  - WASI has no process ID call in preview 1 or 2. wasi-libc offers an opt-in
    fake (`_WASI_EMULATED_GETPID`) that returns a fixed number.
  - Browsers have no processes. Emscripten's `getpid()` returns a fixed number
    (42).
  - Bare metal and small real-time OSes have no OS process, only tasks or a
    single program.

On targets with no real process ID, `/os/posix/getpid` should be a compile error
rather than a fake value. Windows is the exception worth allowing, because its
process ID means the same thing.

### Subtleties Where It Works

- **Containers:** Linux PID namespaces mean a process sees its ID within its
  container, and the main process is often 1. That's correct by POSIX, but
  process IDs aren't unique across the whole machine.
- **Threads:** every thread in a process gets the same value. On Linux, `getpid`
  returns the thread group ID, not the per-thread `gettid`. POSIX requires this.
- **`fork`:** the child gets a new value. This is the only way the value changes
  during a program's life.

## Implementations

### Operating Systems

**Linux**

- System call 39 on x86-64 (172 on ARM64). The kernel side is:
  ```c
  SYSCALL_DEFINE0(getpid) { return task_tgid_vnr(current); }
  ```
  It looks up the current task's thread group ID and turns it into the number
  this process sees in its PID namespace.
- It isn't in the vDSO, the kernel-provided code that lets some calls like
  `clock_gettime` run without entering the kernel. Every call is a real trip
  into the kernel, about 50–100+ ns.
- glibc cached the value in thread-local storage until 2.25 (2017), when it
  dropped the cache. Programs that called `clone()` directly, instead of through
  `fork()`, got the parent's stale ID. musl never cached it. Every `getpid()` on
  Linux is now a system call.

**macOS**

- BSD system call 20. libSystem's wrapper caches the value in user memory after
  the first call and resets the cache in the child after `fork`, so later calls
  are a memory read.

**FreeBSD and OpenBSD**

- System call 20, the old Unix numbering. Each call enters the kernel.

**Windows**

- `GetCurrentProcessId()` makes no system call. It reads the ID from the
  thread's Thread Environment Block, a per-thread structure the OS keeps in the
  process's own memory: `ClientId.UniqueProcess`, at `gs:[0x40]` on x64.
- The result is a 32-bit unsigned `DWORD`. Windows process IDs are always
  multiples of 4, because they share numbering with kernel handle tables.

**WASI and Emscripten**

- No real process ID. Both offer a fixed fake value: Emscripten's is 42, and
  wasi-libc's is opt-in.

### Languages

| Language | API                             | Type                                    | How it gets the value                                                                                                           |
| -------- | ------------------------------- | --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| C        | `getpid()`                      | `pid_t` (signed 32-bit on Linux, macOS) | The C library's wrapper, as above                                                                                               |
| Python   | `os.getpid()`                   | `int`                                   | Calls `getpid()` (or `GetCurrentProcessId()` on Windows) every time. No caching.                                                |
| Rust     | `std::process::id()`            | `u32`                                   | Calls `libc::getpid()` on Unix, `GetCurrentProcessId()` on Windows, every time                                                  |
| Go       | `os.Getpid()`                   | `int`                                   | On Linux a raw system call that doesn't involve Go's scheduler. On macOS through libSystem, on Windows `GetCurrentProcessId()`. |
| Java     | `ProcessHandle.current().pid()` | `long`                                  | Read once when the class loads, then cached                                                                                     |
| Node.js  | `process.pid`                   | `number`                                | Set once at startup through libuv's `uv_os_getpid()`                                                                            |
| .NET     | `Environment.ProcessId`         | `int`                                   | Read on first use, then cached                                                                                                  |

## What This Means for Define

- **The types agree.** Every platform's process ID is a positive number that
  fits in 32 bits, so a natural number holds it everywhere.
- **Caching is safe until Define has `fork`.** Since the value is constant for
  the run, the compiler may get it once and reuse it, as Java, Node.js, and .NET
  do. glibc's experience shows the risk: a cache goes stale in a child created
  by `fork` or `clone`. If Define ever creates processes, the cache has to be
  reset there.
- **Generated Python doesn't need to cache.** Calling `os.getpid()` each time is
  simplest. Each call costs one system call on Linux, which is negligible next
  to Python's own overhead.
