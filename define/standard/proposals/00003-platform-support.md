# Define Standard Library Proposal 3: Platform Support

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** October 18, 2026
- **Date Finalized:**

## Problems

We will need to implement various I/O and kernel-level operations in Define's
standard library.

What platforms do we support as part of Define's Standard Library? There are
many problems we have to solve.

### 1: What is a platform?

The simplest concept of an operating system would be a kernel: the lowest layer
that intermediates programs to hardware, the thing that implements syscalls.

However, most operating systems also provide a standard library for interfacing
with the kernel, such as glibc on Linux. Sometimes there is more than one (for
example, nowadays we also have musl for Linux). You might also sometimes choose
to skip the library and just talk straight to the kernel.

There's also the question of if and when a processor is an important part of a
platform. For example, if you're doing direct syscalls, Linux `getpid` is
syscall 39 on x86-64 but 172 on ARM64.

A few other operations that could depend on the processor:

- **Memory layouts of OS structures**. For example, file information from
  `stat`, and `time_t`, which is still 32 bits in some older 32-bit Linux
  setups. That gives a different date range: those times run out in 2038.
- **Page size**. macOS on Apple processors uses 16 KB memory pages, and Intel
  macOS uses 4 KB. This matters for operations like `mmap`.
- **Byte order**. IBM's s390x mainframe processor is big-endian, so the bytes of
  every multi-byte encoding are in the opposite order.
- Operations that aren't OS operations at all, like atomic memory operations or
  SIMD. Those depend only on the processor.

Some of these are handled by Define's split between encoding operations and
value operations, but others are genuinely different logical behavior across
platforms.

Sometimes there are bugs in certain operations only when run on certain CPUs,
too. For example, Node's `libuv` contains a comment about ARM32 and PowerPC64
for `io_uring`, noting that there are bugs and random crashes just for that
syscall on those CPUs.

### 2: How many platforms?

Supporting too many means too much maintenance work, especially as new versions
of OSes or their standard libraries come out. Supporting too few means people
can't rely on the standard library for most of their programming.

### 3: How do you name an OS?

macOS, iOS, tvOS, etc. are all technically just Darwin. Windows used to be
multiple platforms (NT and non-NT) but now is basically just the NT platform. Is
musl Linux a different OS from glibc Linux? Are FreeBSD, OpenBSD, and NetBSD all
separate OSes? Is POSIX an "operating system" from our perspective?

### 4: What about versioning?

Different versions of an OS have different capabilities. How do we support the
latest capabilities without breaking existing programs that still run on older
versions of the OS? What about that can we determine at compile time, versus
what _must_ we figure out at runtime?

It's not just capabilities, too---sometimes you have to deal with bugs in
certain OS versions.

### 5: Do all OSes get the same level of support?

In many languages, such as Rust and Go, platforms get different support tiers.
For example, in Rust:

- Tier 1: "will always build and pass tests" in Rust's automated testing.
- Tier 2: "will always build, but they may or may not pass tests."
- Tier 3: "no guarantees...they exist in the codebase, but may or may not
  build."

These tiers are actually counted by OS _and_ processor.

Go has a very similar model to Rust.

- **First class ports**: For these, a broken build blocks a release, and
  Google's Go team must own the test machines.
- **Secondary ports**: A change that breaks one "will not necessarily be rolled
  back," and "ultimately the port maintainers are responsible for keeping their
  ports working." A port that stays broken for a release can be removed in the
  next one.
- Go also drops old OS versions on purpose. For example, it deprecates old macOS
  versions at about the rate Apple does.

Node.js has a slightly different, but overall similar, policy:

- **Tier 1**: Node's Build Working Group, the team that runs its build and test
  machines, keeps full automated testing running for them, and test failures
  block releases.
- **Tier 2**: They get the same full testing, and test failures also block
  releases. The only difference from Tier 1 is that "infrastructure issues may
  delay the release of binaries." For example, if a test machine is down, the
  official download for that platform can come out later.
- **Experimental**: these "may not compile," and the tests might not pass. Node
  doesn't release builds for them, and test failures don't block releases.

Platforms can move between Node's tiers only between major release versions,
such as from Node 24 to Node 26.

### 6: GPUs or custom hardware

We might not be running just on CPUs. We might sometimes want to run whole
Define programs on a GPU or ASIC or other hardware.

GPUs in particular have other considerations. Their "libc" equivalents are a bit
different, whether you're using OpenGL or DirectX or Vulkan or CUDA, for
example, might be relevant.

### 7: Hardware Features

The same processor family actually can have different instruction sets. Not all
ARM64 processors have the same instruction sets. x86-64 processors have widely
varying instruction sets.

### 8: Using the C library vs direct syscall access

On all platforms, we have the choice to talk to the C library that intermediates
between the hardware and user programs, just directly issue syscalls, or (in
some cases) talk directly to the hardware. Whether you want to do this varies a
lot by platform.

For example, Apple versions Darwin and libSystem together, but only guarantees
stability for the interfaces in libSystem and is free to change syscall behavior
however it wants between releases. Theoretically, if you happen to know you are
building code for just one specific machine, you could have a more efficient
implementation than going through libSystem, but if you ever hope for
portability between macOS versions, you have to go through libSystem.

Android is similar, where it has an "API level" and all guarantees are made only
by the NDK and the bionic library. However, the API level is simply Android's
own version number, not the actual version number of bionic. One _can_ make
direct syscalls on Android (Go does this sometimes, for example, though it is
limited by Android's seccomp filter) but Google doesn't guarantee their
stability.

On the other hand, Linux and glibc do not move in lockstep in any way, really.
Many languages use direct syscalls on Linux and bypass glibc so that they don't
have to link in glibc for common or simple operations.

### 9: What makes the promise?

Some guarantees about a system's behavior come from the CPU, others from the
kernel, and others from the standard C runtime library.

For example, `getpid` has guarantees that come fundamentally from the kernel,
because it's actually just code in the kernel. A process is a kernel concept,
the kernel tracks the process table, and so on.

On the other hand, imagine that we wanted to somehow guarantee the exact
behavior of glibc's `printf`, such as its formatting syntax. That is a promise
that comes entirely from glibc.

### 10: CPU promises have special considerations

CPUs can also make certain promises, such as the data returned from `CPUID` or
how built-in random number instructions work. Some CPUs also have operations
that others don't. That information is contained only in feature flags from
`CPUID` calls or similar calls for the platform.

It is worth noting that for CPU features, you can't necessarily know they are
there in advance just by knowing the model number, because firmware updates
could disable instructions. For example, Intel disabled TSX instructions for
security reasons. A virtual machine or emulator might also hide certain features
even though it otherwise is an accurate emulation of the hardware. You can know
that certain older models _can't_ have certain instruction sets, but you can't
promise that an instruction _does_ exist.

To make that even more complicated, some CPU behaviors also require the OS to
participate. For example, AVX instructions use larger registers, so the OS has
to agree to save and restore those larger registers when switching the active
process.

For x86, there are standard groupings, called "microarchitecture levels":
x86-64-v1 through v4, defined in 2020 by the x86-64 ABI document. For example,
v3 means AVX2, FMA, BMI, and a few others. Distributions use them as baselines:
Red Hat Enterprise Linux 9 required v2, and RHEL 10 required v3. Go has a
matching setting, `GOAMD64=v1` through `v4`.

ARM has architecture versions (ARMv8.0, 8.1, 9.x, etc.). These list which
features are required, but many features are optional within each version. A
chip can also include some features from a later version early. So the version
number gives a minimum, not the full set.

There's another complication, too. Some hardware models have instructions, but
they are slow or otherwise problematic. For example, AMD processors before Zen 3
have the bit-manipulation instructions that move bits around according to a mask
(`PDEP` and `PEXT`), but they're implemented very slowly, so you probably don't
want to actually emit or run them for that processor.

Plus, sometimes instructions have changed their actual API guarantees over time.
`RDTSC` on Intel processors used to measure actual clock cycles, back when CPUs
had fixed clock speeds (1993 through early 2000's). Then there was a "constant
TSC" in the mid 2000's to compensate for CPUs changing their clock speed
dynamically (like Intel SpeedStep). Then some time around 2007 or 2008 they had
to deal with another problem, which was CPUs could go into deep power suspend
states and stop the constant rate counter, so there was a new "invariant TSC."
However, exposing an invariant TSC to a virtual machine breaks the ability to
live-migrate VMs because the counter would change between physical hardware
devices. So tons of complexity there. `RDTSC` is just used as an example
here---there are other examples and will be more in the future.

As another piece of information, which may or may not be relevant for us, on x86
you can call `CPUID` directly, but ARM's feature flags are in a register that is
only accessible through a call to the OS kernel.

### 11: Hardware Versioning

There is no really good numeric versioning system that is reliably used by
hardware vendors to differentiate their hardware or to say "this chip is more
advanced than that one."

As an example, on x86 processors, family, model, and stepping are returned by
`CPUID`:

- **Family**: a broad design line.
- **Model**: a specific design within the family.
- **Stepping**: the chip's revision. A new stepping usually fixes bugs.

However, these numbers can't be compared to mean "newer" or "more capable."

- Intel has used family 6 for almost everything from the Pentium Pro (1995)
  through today's Core chips. Model numbers within it are assigned in no
  consistent order, and low-power Atom designs are mixed in with desktop Core
  ones. So model `0x9E` isn't "later" than `0x8C` in any useful sense.
- AMD gives each generation a new family number, which is closer to a version.
  However, these are design lines, not feature levels. Low-power and
  high-performance lines got separate families in the same years: Jaguar, the
  low-power AMD chip (`0x16`) was contemporary with Bulldozer (`0x15`), the
  high-performance desktop/server chip. And one family can span generations with
  different features: Zen 4 added AVX-512 _within_ family `0x19`.

Even the x86-64-v1 to v4 levels aren't reported anywhere. Software works them
out by checking the individual feature bits. In fact, Intel and AMD both tell
software to use the feature bits: family and model are only reliable for
applying bug fixes and performance tuning for one specific chip.

It is safe to assume that this difficult behavior affects all or most other
hardware as well.

### 12: Minimum Support Versions

If we support all versions of a platform back to the start of computing, we
would be creating a ton of code that we would have to maintain with questionable
value. In general, backwards compatibility is primarily a return on investment
proposition, plus a question of security surface area (the more code we have,
the more chance there is a security issue in it somewhere).

## Solution

There are many components to this solution.

### What is a Value Operation?

We name and create low-level value operations based on what is making the
promise.

Thus, `getpid` would be `operation</os/linux/getpid>`, because the only thing
making the API guarantees is the Linux kernel itself (even if we were to call it
via glibc, it's not glibc that makes the guarantees for `getpid`, actually).

Where there is code that a runtime library implements totally independently of
the kernel, like `printf`, the naming would be
`operation</os/runtime/glibc/printf>`. It doesn't seem likely we would want a
pure value operation for something like that in Define, but maybe we would and
if so, that's how we would do it.

Sometimes you will have runtime behaviors that are specific only to a particular
OS. For example `close` would be `operation</os/linux/glibc/close>`. Its
behavior differs between `musl` and `glibc`. In general, the differentiator
there is, are we promising the API contract of the kernel, or the specific API
contract of the runtime library on top of the kernel?

CPU operations are usually represented as encoding operations, not value
operations, but if there is one that is CPU-specific, it would look like:
`operation</hardware/cpu/x86/cpuid>`. (In that case, we chose x86 instead of
x86_64 because the API contract of CPUID has been the same since the Pentium.)
If there were ever some sort of model-specific CPU operation, it would look like
`operation</hardware/cpu/x86/sandy_bridge/foo>`, and an instruction-set-specific
one would look like `operation</hardware/cpu/x86/avx_512/vfmadd231ps>` (though
we would determine their presence through feature flags in the CPU, most
likely).

### Naming

In case it wasn't obvious from the section above, we name things according to
the component that the standard library is providing guarantees about. Kernels
have names (Linux, XNU, NT), runtime libraries have names (glibc, libSystem,
win32 or "the Windows API"), etc.

### Selecting Compile-Time and Runtime Behavior

Define will create a mechanism (via a future Define Language Proposal) that
allows setting conditions that can _either_ be determined at compile time or at
runtime. Thus, Define developers will be able to specify that certain conditions
are always true for a target platform, but others will be checked at runtime for
that target platform.

Many feature selection aspects will be handled by our backends (for example, if
we have a C backend, what the C compiler does for that platform will determine
our exact behavior) but in cases where we need to decide the behavior, there
will also need to be some way to make certain decisions either (a) at the time a
program starts (so you don't check the same conditions over and over) or (b) the
first time some functionality is used in a program (although we have to consider
the effectiveness and safety of doing this in a concurrent environment).

### Variables for Platform Targeting

We will need to be able to target platforms (at runtime and compile time) using
at least the following components:

- `kernel`
- `kernel_version`
- `runtime`
- `runtime_version`
- `hardware`

However, we may choose to have even more targeting capability to get more
granular on specific platforms. The `hardware` category in particular may have
various detailed fields depending on the hardware. We don't have a
`hardware_version` field because it is not usually meaningful.

`runtime_version` is whatever version the guarantor uses for its promises. For
example, macOS uses its OS version for the promises, not the actual `libSystem`
version. For Android it's the Android API level. For Windows it's the Windows
version (8, 10 update 1607, 11, etc.).

We will need comparison mechanisms for all the versioning systems. Software
mostly uses numeric major.minor.patch versioning, which we could write a
comparison action for. For hardware it is more complex and instead of
comparisons there may just need to be sets of numbers you check against for
features (or, as noted in the Problems, runtime checks in some cases for the
existence of those features). Some comparison functions may just be a list of
identifiers with timestamps, similar to how Renovate looks at various version
registries today.

### Feature Flags

Instead of directly writing conditions on the platform targeting criteria in
Define code, most features should be turned on by a flag specifically named for
that feature, using the normal Define naming system (using a mechanism that will
be described in a future Define Language Proposal). Thus, you might have a flag
named `/hardware/cpu/x86/rdtsc/invariant_tsc`. Then there would be a separate
configuration system that associates platform targeting criteria with that flag.
This allows for supporting new hardware or platforms, in many cases, simply by
writing a configuration file, without having to modify the actual conditionals
in Define code.

### Strive for Precision

Our general [principle](../../spec/principles.md) in Define is "guarantee
soundness, strive for precision."

Where APIs are unstable over time, we have two options:

- Guarantee only the minimum sound behavior.
- Create version-specific operations.

In general, we prefer to create version-specific operations when reasonable, so
that we know the exact logical behavior of the system at compile time. These
would likely be wrapped with actions that handle the version differences. This
does create a maintenance burden, but it's the sort of maintenance burden that
should be pretty easy to handle with coding agents.

There will be times at which it is not reasonable to create version-specific
operations. There might also be layers of the standard library at which we are
guaranteeing a particular cross-platform API, as opposed to concrete hardware/OS
behavior. In those cases, we would guarantee only the minimum sound behavior
that we believe to be completely reliable across all platforms.

When there are different _implementation_ details that all have the same _API_,
those would often be represented with encoding operations (when the differences
have to do with some underlying data format that has logically identical
behavior at the value operation level).

### Cross-Platform Operations

For cross-platform standards like POSIX, we _may_ choose to have an `/os/posix`
or things like that available for certain operations, but they can only provide
the guarantees that (a) POSIX actually provides and that (b) all the
implementations behind it actually guarantee.

### Tiering

Because we are a verified language, we can't exactly duplicate the tiering
systems of other languages, because soundness and precision are part of our
guarantees (problems that other major languages don't have). However, we can
still have tiers:

- **Fully Supported**: We work to guarantee soundness and precision and the full
  range of support for the language. These are part of the standard library and
  are maintained as part of the core functionality of the standard library.
  Releases are blocked for soundness, precision, or completeness for a platform.
  We guarantee forward compatibility.
- **Sound**: We guarantee that anything that exists for this platform is sound,
  but not necessarily precise, and the support for the platform may not be
  complete. Support may come from volunteers. Releases are blocked only for
  proven unsound behavior. If volunteers are unresponsive to unsound behavior,
  the platform will be downgraded to unsound.
- **Unsound**: We do not guarantee soundness for the platform, but we do have
  operations for it. Support for the platform may not be complete. Releases are
  never blocked unless there is a high-severity security issue, in which case
  our recourse may be to delete the functionality with that security issue.

My intention is that by the time we reach Define 1.0, our Fully Supported
platforms will be Linux, macOS, and Windows on x86_64 and ARM64.

### Using the Library vs the Kernel

Define can choose to implement both the runtime library operation and the direct
kernel operation where doing so is reasonable. _Actions_ within the standard
library may choose one or the other for reasons of optimization or stability,
but the standard library may provide any operation it can provide with soundness
and precision for that platform, even if it provides the same functionality with
overlapping implementations across the CPU, kernel, and OS runtime.

### Versioning Operations

Once in a while, when the API guarantees of some OS or hardware feature have
changed over time, we may actually have different operations that explicitly
have versions to them. We would do this simply by putting the version into the
name of the operation itself, as an extra path segment. We don't guarantee a
particular versioning format, but if it's a numeric version, we start it with
`v` and replace any `.` with `_` (and any `_` with `__`).

So you might have `operation</os/linux/unstable_op/v6_1>` and
`operation</os/linux/unstable_op/v6_2>`. In general, when an API guarantee is
presently documented as unstable, we should version it this way.

### Minimum Support Versions

Our goal in terms of platform support is to generally provide as much backward
compatibility as we can without putting an undue burden on the maintainers of
the standard library.

Version support is judged by how popular it would _potentially_ be to still
_compile_ new code for that platform. If popularity declines below a threshold
where maintenance is worthwhile, we will drop support for that version.

In general, we should strive to support any version that is still either (a)
supported by its creator (it gets updates) (b) still being manufactured (if
hardware), or (c) widely used. (a) and (b) override (c). We can choose to
override these rules for systems that are very sparsely used, though, if
maintenance is causing significant problems for the maintainers.

## A Real Program

All of these examples involve imaginary syntax for conditionals and constants.

### Random Bytes Action

Linux added the `getrandom` syscall in kernel 3.17, and a seccomp filter can
still block it. When it isn't available, programs read `/dev/urandom` instead.

```define
define the potential action<standard:/os/linux/random/get_bytes> {
    define the position<run>.
    define the position<byte_count> {
        it may only contain particles where {
            it has the value</number/natural>.
        }
    }
    define the position<bytes> {
        it may only contain particles where {
            it has the value</binary>.
        }
    }

    it happens when {
        the position<run> has a particle.
    } and it does {
        create a particle in position<bytes>.

        match the constant</os/linux/getrandom/available> {
            case literal</boolean>"true" {
                execute the operation</os/linux/getrandom> {
                    with view<byte_count> looking at position<byte_count>.
                    with view<result> looking at position<bytes>.
                }
            }
            case literal</boolean>"false" {
                execute the operation</os/linux/read_dev_urandom> {
                    with view<byte_count> looking at position<byte_count>.
                    with view<result> looking at position<bytes>.
                }
            }
        }

        destroy the particle in position<byte_count>.
        destroy the particle in position<run>.
    }
}
```

### Container Init Check

A program running as process 1 in a Linux container has to collect orphaned
child processes and handle shutdown signals itself. Containers are a Linux
feature, so this program calls the Linux operation directly, and it only
compiles for Linux.

```define
define the potential action<define-lang.org:container:/container/check_init> {
    define the position<run>.
    define the position<is_init> {
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }

    it happens when {
        the position<run> has a particle.
    } and it does {
        define the position<process_id> {
            it may only contain particles where {
                it has the value<standard:/number/natural>.
            }
        }
        create a particle in position<process_id>.
        execute the operation<standard:/os/linux/getpid> {
            with view<result> looking at position<process_id>.
        }

        create a particle in position<is_init>.
        execute the operation<standard:/number/natural/equal> {
            with view<a> looking at position<process_id>.
            with view<b> looking at literal<standard:/number>"1".
            with view<result> looking at position<is_init>.
        }

        destroy the particle in position<run>.
    }
}
```

### Trace ID

A distributed tracing system gives each request a random 16-byte trace ID, so
that every service the request passes through can record the same ID.

In this program, `/trace/id` has the value `standard:/binary`.

```define
define the potential action<define-lang.org:trace:/trace/start> {
    it also assigns the position</trace/id>.

    define the position<run>.

    it happens when {
        the position<run> has a particle.
    } and it does {
        define the position<random> {
            it may only contain particles where {
                it has the action<standard:/os/linux/random/get_bytes>.
            }
        }
        create a particle in position<random>.
        create a particle in position<random>::action<standard:/os/linux/random/get_bytes>::position<byte_count>.
        set the value of position<random>::action<standard:/os/linux/random/get_bytes>::position<byte_count> to literal<standard:/number>"16".
        create a particle in position<random>::action<standard:/os/linux/random/get_bytes>::position<run>.

        move the particle in position<random>::action<standard:/os/linux/random/get_bytes>::position<bytes> to position</trace/id>.

        destroy the particle in position<random>.
        destroy the particle in position<run>.
    }
}
```

## Why This is the Right Solution

In general we choose flexibility and precision. Instead of trying to turn
_everything_ into a generic operation that hides all the details from developers
and never giving them access to the underlying primitives, we _start_ with the
underlying primitives and then we can create libraries on top of that that
abstract that away for critical pieces that have common behavior across
platforms. It also allows the Define ecosystem to have other versions of these
libraries that provide more platform support, by allowing them to reach into the
implementation details of various platforms and re-use them in their own
libraries.

My fundamental assumption here is that platforms will provide guarantees at
_some_ level, even if it's just "this version of this OS and this runtime on
this hardware." That's not much of a guarantee, but our system would still allow
us to take advantage of it if we _had_ to.

With past languages, our policy would have become extremely annoying to maintain
because of the vast number of different operations it would require us to
create. However, with coding agents I believe maintaining many similar but
slightly different implementations will become much simpler.

## Forward Compatibility

The biggest danger to forward compatibility is if we accidentally guarantee
something unsound in a released version of Define, because it would be hard to
prove logical equivalence through an automated refactoring. If we accidentally
_do_ do this, at the very least we will know what version of the standard
library it happened in, and can add in conditional code during the refactoring
to preserve the bad behavior unchanged. (Or provide the option to do optimal but
breaking refactorings on upgrades.)

Also, when we choose to version some operation, there's a slight risk in terms
of "what does the unversioned one mean" and "what if we chose the wrong
version?" However, we should be able to automatically rename those with little
issue.

## Refactoring Existing Systems

The flagging system should support matching the behavior of every existing
programming language, although that doesn't mean we will choose to implement the
operations available on every existing programming language.
