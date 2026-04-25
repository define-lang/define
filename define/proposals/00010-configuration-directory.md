# Define Language Proposal 10: Configuration Directory

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** January 3, 2026
- **Date Finalized:**

## Problems

Many programming languages configure how their tools will behave through
command-line flags. For example, you might compile a C++ program like:

```bash
g++ -std=c++17 -O2 -march=native -Wall -Wextra -Werror -Wno-unused-parameter \
    -I./include -I./third_party/boost/include -I./third_party/protobuf/include \
    -I/usr/local/include -I./generated/proto \
    -DDEBUG=1 -DLOG_LEVEL=3 -DFEATURE_FLAG_ENABLED -DVERSION_STRING="1.2.3" \
    -DPLATFORM_LINUX -DARCH_X86_64 \
    -L./lib -L./third_party/boost/lib -L/usr/local/lib \
    -lboost_system -lboost_filesystem -lprotobuf -lpthread -ldl \
    -g -fno-omit-frame-pointer -fstack-protector-strong \
    -Wl,-rpath,./lib -Wl,-rpath,./third_party/boost/lib \
    -o my_program \
    src/main.cpp src/utils.cpp src/parser.cpp src/network.cpp \
    generated/proto/messages.pb.cc
```

Obviously, this is very hard to read. It also causes numerous problems in
practice.

### 1: Lack of Version Control

Command-line flags are typically not stored in version control. This means they
have no recorded history, and often aren't reviewed as part of a code review
process, even though they significantly affect how the codebase works.

They might be documented in a README, or stored in a build script, but if you go
back in time to build an old version of a system, you might just have to "know"
what the right build configuration was to successfully build that binary.

It's also not clear what command-line flags a binary was actually built with,
because that probably is just sitting in the CI configuration, which is often
separate from the code. Or worse, there was no CI system and the flags were just
typed out by a developer on the command line, and you'll never know what they
were.

### 2: Build Configuration is Error-Prone

There is no guarantee that a developer will specify the build configuration
appropriately on the command-line. It is extremely frustrating sometimes to have
to discover that there are "magic switches" you always have to set to build a
particular piece of software, after you have struggled for an hour trying to
figure out why it won't build.

### 3: Build Configuration is Hard to Understand

When a new developer joins a project, they have to figure out what flags to use,
often by asking other developers or reading documentation that may be out of
date.

In general, there's usually no single place to look to understand how a project
is configured. You might need to check:

- Build scripts (Makefiles, build.sh, etc.)
- CI configuration files (.github/workflows, .gitlab-ci.yml, etc.)
- Documentation (README files, wiki pages)
- Individual developer knowledge

This makes it difficult for any human to understand the build configuration.

### 4: Build Configuration is Hard to Generate

Languages like C and C++ resorted to complex scripts like `autoconf` just to
generate the command-line flags appropriately and to solve some of the problems
above. While these are very powerful, they are extremely complex and the end
result (a set of scripts that generate a very long command-line flag string) is
quite hard to understand.

### 5: Inconsistent, Non-Reproducible Builds

Different developers on the same team might use different compiler flags even
when they are intending to create the same build, leading to builds that work
differently on one developer's machine vs another.

Continuous integration and deployment systems also need to know what flags to
use, and can also be using different flags than developers are using locally.
Sometimes this is intentional, but other times it's completely accidental. This
can lead to builds that pass in CI but fail locally, or vice-versa.

In general, without a single source of truth for build configuration, it's much
harder to have consistent, reproducible builds across multiple users and
environments.

### 6: Configuration Complexity and Cognitive Load

As compilers add more features, the number of command-line flags grows. Some
flags might conflict with each other, or have subtle interactions that are hard
to understand. The cognitive load of remembering and correctly applying all the
necessary flags becomes significant.

Because command-line flags are typically just strings passed to the compiler,
there's also not an IDE or other tool that's helping the developer to remember
what they are. There's no schema that validates them when typing them. Invalid
flags or combinations of flags can't be caught until you actually try to run the
compiler.

## Solution

All configuration for Define goes into a `.define` directory in the project
root. This directory contains all compiler settings, project metadata, and other
configuration needed to build the project.

Adding command-line flags to Define tools is discouraged unless there is a clear
requirement for a situation where the configuration files can't be used. (Tools
may of course accept flags such as `--help` or `--version` that purely provide
information to the user about the tool.)

### Structure

The top-level `.define` directory contains only subdirectories, no files. These
subdirectories are referred to as "configuration directories."

Configuration directory names may contain only lowercase ASCII characters and
the underscore character.

Define reserves all configuration directory names for its own use. Third-party
libraries and tools may not create any new configuration directory name.

At the time of writing this proposal, there are only two configuration
directories:

- `project`: contains the file `config.defcl` which defines a directory as being
  a project root, and which contains at least the universe name of the current
  project.
- `x`: A directory for all third-party configuration, following a specific
  format.

Define Language Proposals may create new configuration directories.

### File Contents

Most files that contain configuration values inside of configuration directories
are expected to have the extension `.defcl` and be written in the
[Define Configuration Language](../../defcl/spec/spec.md).

### Format of the `x` Directory

The `x` directory contains a subdirectory structure that matches the multiverse,
authority, and universe of the tool that wishes to create a configuration file.

For example, if the universe `mv:example.com:math_utils` wants to have its own
configuration, it would place it into the directory
`.define/x/mv/example.com/math_utils/`.

Third party configurations may contain anything they want to contain. However,
if they contain configuration values, they are strongly encouraged to write them
in the [Define Configuration Language](../../defcl/spec/spec.md).

When Define tooling removes a universe from being a dependency of a codebase, it
may delete that universe's configuration files from the project root of the
codebase. However, the tool should clearly inform the developer that removing
the library will also remove the configuration (only if such configuration
exists).

## A Real Program

Consider a Define project with the following structure:

```
my_project/src/.define/project/config.defcl
my_project/src/.define/x/alice.com/math_utils/numbers.defcl
my_project/src/main.dfn
```

At the time this proposal is being written, we have not yet specified the Define
Configuration Language. However, we could imagine the contents of `config.defcl`
might look something like:

```bash
project: {
    universe: "mv:example.com:my_project"
    author: "Max Developer"
    dependencies: {
        universe: { multiverse "mv" authority "alice.com" universe "math_utils" }
    }
}
```

And then the `math_utils` library has a special config just for this codebase,
in `my_project/src/.define/x/alice.com/math_utils/numbers.defcl`.

Then when a developer does `define src/main.dfn` the compiler reads those
configurations without the developer having to specify anything special on the
command line.

## Why This is the Right Solution

Storing all configuration in a well-known location on the filesystem that gets
version controlled solves all the problems listed above. All environments and
all developers read from the same configuration files, which are versioned in
history. Tools can see, validate, and refactor these files. Also, configuration
files are much easier to read than a long string of command-line flags.

By reserving all configuration directory names for define, we create infinite
future possibility, a key to forward compatibility.

By specifying that there is a special format that third parties may use, but
that it is tied to our existing namespacing system (fully-qualified universe
names) we create sufficient flexibility for third parties to be able to re-use
the system without potential namespace conflicts. The only potential downside is
that it could lead to a lot of separate filesystem accesses to read
configuration files, and that it does lead to longer filesystem paths (which can
be an issue on systems like Windows that historically limited paths to 260
characters in many tools).

### Why Not a Single File?

Most other languages use just a single file for this: Node.js's `package.json`,
and the new Python standard for `pyproject.toml`. What these have actually led
to is either:

- A proliferation of different configuration files spread all over the root
  directory of a program, because other tools can't use the same file easily, or
- A bunch of tools adding new sections to one giant configuration file, which
  becomes very unwieldy over time.

### What About Environment Variables?

Those are just command-line flags with another name. They have all the same
problems, but actually they are even worse:

- They often don't get logged in the same place that command lines get logged,
  so you have to figure out by magic what environment variables were specified
  for a build when you're figuring out what happened in CI.
- Not every environment variable actually is relevant to your build, and so you
  could be searching through hundreds of environment variables to try to figure
  out which ones are actually affecting your build.

Define tooling should attempt to never accept or operate on environment
variables.

## Forward Compatibility

Because we have reserved all configuration directory names, we can add, remove,
or change the layout of define configurations as we wish, provided that we
provide tools to migrate old codebases to the new format.

## Refactoring Existing Systems

Since Define is a new language, there are no existing Define projects to
refactor. It would be impossible to refactor systems that used command-line
flags into this model, which is why it has to be part of the language from the
start.
