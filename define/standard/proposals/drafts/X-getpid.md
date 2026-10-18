# Define Standard Library Proposal X: getpid

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** October 14, 2026
- **Date Finalized:**

## Problems

One of the simplest I/O operations you can do on almost every system is get the
current process ID. This is a good starting point for our very first I/O
operation because it can't fail and behaves almost identically on every
platform. (That is, it lets us progressively build up complexity as we build
later operations, starting with this foundation.)

As our first I/O operation, this is the first time we start to care specifically
about how operating systems behave, as the operating system intermediates all
our I/O.

### 1: Platform Differences

`getpid` behaves very similarly across most POSIX platforms, but even there,
there are differences:

| Platform | Type                     | Largest value                                                                                                                                                                                                                                                                                                         |
| -------- | ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Linux    | `pid_t`, signed 32-bit   | 4,194,303 (2^22 − 1) on 64-bit kernels, from the compile-time `PID_MAX_LIMIT`. The run-time `pid_max` (default 32,768) can only lower it. Lower on 32-bit and "small" kernel builds. Never above 2^30 − 1, because of `FUTEX_TID_MASK` in the kernel, which is an API guarantee that the kernel is unlikely to break. |
| FreeBSD  | `pid_t`, signed 32-bit   | 99,998. IDs stay below the run-time `kern.pid_max`, which can't exceed `PID_MAX` (99,999, a compile-time constant).                                                                                                                                                                                                   |
| OpenBSD  | `pid_t`, signed 32-bit   | 99,999 (`PID_MAX`)                                                                                                                                                                                                                                                                                                    |
| macOS    | `pid_t`, signed 32-bit   | 99,998 (`PID_MAX` is 99,999)                                                                                                                                                                                                                                                                                          |
| NetBSD   | `pid_t`, signed 32-bit   | No fixed maximum. `PID_MAX` is 30,000, but that's just a starting "maximum," and IDs go above it once there are more than about 16,000 processes.                                                                                                                                                                     |
| Windows  | `DWORD`, unsigned 32-bit | No documented maximum. `0xFFFFFFFF` is reserved (`ASFW_ANY`), so at most `0xFFFFFFFE`. In practice always a multiple of 4 and far smaller.                                                                                                                                                                            |

There are a few special cases, too. Linux's largest process ID actually depends
on the kernel's word size, not the processor family. On 64-bit kernels it's 2^22
− 1. On 32-bit kernels, the limit is the default, 32,768, so the largest ID is
32,767

Some of these limits have changed throughout history:

| OS                 | History of `PID_MAX`                                                                                                             | Current value since                                                                                 |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| FreeBSD            | 30,000 (inherited from 4.4BSD) → **99,999** in November 1998                                                                     | Nov 1998, about 28 years                                                                            |
| OpenBSD            | 30,000 → 99,999 (Dec 28, 1998) → 30,000 (the next day) → 65,535 (Jan 5, 1999) → 32,766 (Jan 11, 1999) → **99,999** in March 2016 | Mar 2016, about 10 years. Before that, 32,766 for 17 years.                                         |
| NetBSD             | **30,000** since its first import of 4.4BSD code in 1994                                                                         | 1994, never changed. NetBSD gives out IDs above it once there are more than about 16,000 processes. |
| macOS (XNU kernel) | 30,000 in Mac OS X 10.0 through 10.4 Tiger → **99,999** in 10.5 Leopard (`xnu-1228`, released October 2007)                      | Oct 2007, about 19 years                                                                            |

That said, they have changed _very_ rarely.

This leads us into our other problems.

### 2: POSIX or not?

Do we create a single POSIX `getpid` operation, or do we create one for each OS?
The behaviors and return constraints are _slightly_ different. Those constraints
could definitely matter for compiler optimization, but then again, the actual
encodings of each return type are actually fixed by their APIs (32-bit signed
ints). The compiler could choose to convert them to smaller ints by truncation
(should be free) to get better SIMD behavior, though, theoretically. Is that
important for PIDs? I'm not going to assume it is one way or another, it's
hubris to assume I know what's important for every program in the world.

### 3: Return Value Size

Each return value is encoded as a 32-bit signed or unsigned integer, depending
on the platform. How do we constraint the value, though? Do we say that Linux is
limited to 2^22, or 2^30, or 2^31 - 1? Do we constrain BSD to 99,999? What if
somebody recompiles the BSD kernel but it's still BSD in every other way? What
happens if those numbers change in the future?

There are in fact three different "tiers" of guarantees an OS provides for
`getpid`:

1. Guaranteed by the platform's interface (types and ABI):
   - POSIX `pid_t`: 1 to 2^31 − 1. POSIX defines a process ID as a positive
     integer.
   - Linux and NetBSD: below 2^30, because `FUTEX_TID_MASK` is part of the
     interface programs already depend on.
   - Windows: at most `0xFFFFFFFE`.
2. True of the current implementation:
   - Linux's 2^22 − 1 on 64-bit kernels.
   - The BSD and macOS `PID_MAX` limits.
3. Run-time configuration: `pid_max` and `kern.pid_max`.

We can't know the actual run-time configuration at compile-time.

Many of the constants like `PID_MAX` could change in the future. In fact,
somebody could just change them and recompile the kernel now.

### 4: Value Type

Should it return a `/number/natural` or a `/number/integer`? All of the actual
`getpid` calls can only return values that are 1 or greater. The only reason
their type is negative is that other methods take a `pid_t` and the negative
values have meaning. Another option would be to create a special
`/os/process_id` type and not guarantee anything about it, even though the APIs
of the underlying systems explicitly guarantee what it will be.

## Solution

Even though all POSIX systems have extremely similar behavior, we still create a
separate getpid for every OS target. Thus, we have

## A Real Program

## Why This is the Right Solution

## Forward Compatibility

## Refactoring Existing Systems
