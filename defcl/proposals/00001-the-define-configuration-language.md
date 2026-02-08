# Define Configuration Language Proposal 1: The Define Configuration Language

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** January 5, 2026
- **Date Finalized:**

## Problems

As described in
[DLP 10](../../define/proposals/00010-configuration-directory.md), Define uses a
standard configuration layout and language to control build parameters instead
of relying on command-line flags.

That means we need to define the format for a configuration language. Attempting
to use any pre-existing configuration format ran into various difficulties. For
example, TOML allows

### 1: Too Many Ways to Do the Same Thing

As per the [principles of Define](../../define/spec/principles.md), we want
there to be One Right Way to do things. Most modern configuration formats allow
you to choose multiple different ways to accomplish the same thing.

For example, TOML allows nested structures to be written in three different
ways:

```toml
# Inline table syntax
[dependencies]
boost = { version = "1.82", features = ["system", "filesystem"] }

# Dotted key syntax
dependencies.boost.version = "1.82"
dependencies.boost.features = ["system", "filesystem"]

# Table header syntax
[dependencies.boost]
version = "1.82"
features = ["system", "filesystem"]
```

While this seems convenient for the user, it creates numerous problems in
practice:

- Automated refactoring becomes difficult. You have to understand how to
  refactor every format, and if you want to programmatically modify them, you
  have to know how to spit them back out in the same format they were written in
  (even though in code they all look the same to the program).
- You force the developer to make a choice that they shouldn't have to make.
- Functionally identical configuration files look different across different
  code repositories.
- It complicates the parser.

### 2: Canonical Formats

Because most configuration languages allow you to write the same thing in
various ways, it's very hard to know "when I write a program that _generates_
this configuration language, what format am I supposed to generate?" If I write
a formatter for the configuration language, what decisions should that formatter
make?

### 3: Excessive Flexibility Causes Confusing Parsing

Some formats give you far more flexibility than most developers actually need or
want, and actually this can lead to confusing bugs. For example, YAML has the
"Norway Problem":

```yaml
# Is this the boolean false or the string "NO"?
country_code: NO
```

Without explicit typing, the parser must guess, and different parsers or
contexts might guess differently. This creates a class of bugs where a
configuration file that looks correct to a human actually contains a type error
that only manifests as a runtime failure.

### 4: Parsing Complexity

It is surprisingly difficult to write a correct parser for most modern
configuration languages. For example:

- **TOML** requires complex state machines for table definitions and has edge
  cases in datetime parsing, mixed-type arrays, and unicode escape sequences
- **YAML** has a large, complex specification that is very hard to parse
  correctly.

Even formats that seem simple may have subtle edge cases that require
significant implementation effort.

We want a parser with dead-simple implementation that can be implemented in many
languages, including in Define itself.

### 5: Schema Enforcement

It is surprisingly difficult to write validation logic for some of the simplest
requirements in most configuration languages. Many configuration languages
require you to implement your own validation for things as simple as "is this a
number" or "is this a valid enum value?"

Some systems like JSON/JSONC allow you to validate them with JSON Schemas, but
in reality few people parsing the format actually do this, because it's not
built into most parsers in a way that provides useful error messages and
reliable validation.

There's a very nice configuration language called [KDL](https://kdl.dev/) that
solves almost all of the other problems described here, but doesn't have any
sort of schema enforcement that allows parsers to consistently enforce that
configurations are correctly specified.

## Solution

Make the Define Configuration Language (DCL) a strict subset of the
[Protocol Buffer Text Format](https://protobuf.dev/reference/protobuf/textformat-spec/)
(textproto) that removes all ambiguity and "more than one way to do it" from the
spec.

Require `.proto` schema files for parsing and use a textproto parser to read the
format (along with an additional validator to make sure the DCL files are in the
correct format).

DCL is used for all configuration files in the `.define` directory, with the
file extension `.defcl`.

The syntax and parsing rules for DCL are specified in the
[Define Configuration Language Specification](../spec/spec.md).

## A Real Program

Here is an example `.define/project/config.defcl` file:

```
project: {
    universe_name: "mv:example.com:my_project"
    author: "Max Developer"
    dependencies: [
        { universe: "mv:alice.com:math_utils" },
        { universe: "mv:bob.com:networking" }
    ]
}
```

## Why This is the Right Solution

### The "One Way" Philosophy

Using textproto enforces a single structure defined by the proto schema. This
rigidity ensures that every Define configuration file looks identical, reducing
cognitive load when moving between projects and making automated refactoring
much easier.

### Simple Parsing Complexity for Self-Hosting

The grammar of DCL format is recursive but extremely simple. It does not require
lookahead for type inference (unlike YAML). It does not require complex state
machines for table definitions (unlike TOML). The parser can be implemented in a
few hundred lines of code in any language (Python, Rust, or Define itself). This
drastically simplifies the eventual roadmap to a self-hosting compiler, as we do
not need to port a heavy library like `toml++`.

### Alternatives Considered

I evaluated the current industry standards, and here is why I didn't choose each
of them.

#### JSON / JSONC

JSON is probably the most ubiquitous data-structure language in use today. It
has a lot of very robust parsers.

However, using JSON as a configuration language has a lot of issues, mostly
around ambiguity of parsing. For example, parsers often treat integers as
floating point numbers. Parsers do different things with duplicate keys in
dictionaries.

JSON also doesn't allow comments, which is a constant source of frustration for
programmers attempting to write configurations in pure JSON. JSONC was invented
to solve this problem, though it has no spec.

I also happen to find it annoying that JSON forbids trailing commas, leading to
diffs that look like you're modifying the last key in a dictionary when you're
just adding a new line to the end of it. Some JSON parsers actually do allow it,
but others don't.

JSON5 does solve many of those problems.

The biggest problem that I have with JSON, though, is validation. JSON Schemas
exist, but there's no guarantee that they get used by parsers. I rarely ever see
schemas get actually used by people consuming JSON, even when the schemas exist.

The schemas also only provide validation, they don't inherently create data
structures that match your intent. You could still have bugs like this in your
code:

```Python
config = json.load(f)

# I don't get a Config object with a log_level enum.
# I just get a dictionary where I have to use literal strings.
if config["log_level"] == "DEBUG":
    enable_debugging()

# If I typo the string, no programming language will even warn me.
if config["log_level"] == "DBUG": # <--- BUG!
  ...
```

The solutions for this are always language-specific, like using Pydantic in
Python.

#### YAML

YAML is used by a lot of systems, like Kubernetes and GitHub Actions, for
configuration.

However, it has numerous problems in practice:

- It allows too many ways to do the same thing (see the Norway problem higher up
  in this document for one example of a problem that causes)
- The YAML specification is very large and complex to implement.
- There is no built-in schema validation for YAML; most programs just have to
  implement their own validators.

Most modern systems have moved away from YAML as their configuration language
for these and other reasons.

#### TOML

TOML is the most obvious choice. It is the industry standard for programming
language configuration (Rust, Python). It's much simpler than YAML.

However, there are no straightforward solutions that automatically enable
validation for all TOML configuration files, that would be (a) intuitive for
people writing new configurations and (b) trivial to implement when you're
parsing new configuration files. That was the biggest reason I didn't choose it.

Also, nested configurations in TOML (a) have too many possible syntaxes and (b)
can become hard to read and manage over time. I was particularly worried about
forward compatibility if we chose TOML, because most TOML configurations look
like:

```toml
[some_header]
some_field = "some_value"
```

You can require the headers, which helps a lot (so that you can add different
header sections in the future) but when you want to nest them the configuration
becomes less clear (in particular, the fact that you _have_ nesting can be
scattered all over the file, with it not being clear that one of the child
configurations is modifying what the parent said in some way).

#### KDL

Really great at solving almost all of our problems, but doesn't have any sort of
standard schema language. There's a proposal for one from 2011 that was never
implemented, and it's been so long I have to assume it never will be.

#### CUE

[CUE (Configure, Unify, Execute)](https://cuelang.org/) is a super cool
configuration language with extremely powerful validation mechanisms. There are
a lot of strong arguments for why we would want to use CUE:

- It has a very powerful validation system that goes beyond just types and into
  constraints.
- Because the validation system is so powerful, the IDE can catch many errors
  while you are writing the config.
- It allows for inheriting configuration values. What happens when you have a
  Debug and Release config that want to share 90% of their settings?
- It allows for imports and has a whole module/package system.

There are a few problems, at present:

- CUE is essentially an entire logic validator, not just a file format.
  Implementing a full-featured native CUE parser in Define is almost as much
  work as implementing a new programming language. Today you could link against
  a C library that embeds the Go runtime, though, and just use it that way.
  Theoretically proto actually has the same problem, but it is something we will
  probably want to implement in Define anyway eventually so that we can interact
  with APIs that use gRPC and so forth.
- I'm slightly concerned about the "heaviness" of CUE as a dependency for
  something as low-level as a language compiler. (Then again, perhaps proto has
  the same problem.)
- CUE has a lot of features that make deterministic refactoring of the sort that
  we want to guarantee quite difficult. It does have an amazing `cue fix` tool
  that can handle a lot of it, as well as the ability to write aliases that
  handle old field names. However, for example, once you allow inheritance or if
  somebody writes something like `options: { "time" + "out": 10 }` in CUE then
  the AST-based refactoring tool breaks.

All that said, CUE is probably the strongest contender out of all the options.
We could easily switch to it in the future. CUE supports automatically
converting proto schemas
[and textproto files](https://pkg.go.dev/cuelang.org/go/encoding/protobuf/textproto)
to CUE, and textproto files can be deterministically converted to CUE configs.

## Forward Compatibility

Protos were designed to solve forward compatibility. We do have to add another
constraint (don't change field names), but that's common already for people
using protos over JSON. Provided we enforce certain proto best practices, we
should be fine.

If we needed to change the format entirely in the future, we could
deterministically transform DCL files to any new format, as the structure is
unambiguous and the schema provides the type information we would need to ensure
this.

## Refactoring Existing Systems

Since Define is a new language, there are no existing Define projects to
refactor. If we had used a different configuration format (such as TOML or
YAML), it would be hard to automatically convert the data. You have to first
deserialize it into a data structure, then validate the data in the data
structure (which can fail) and then write it back out.
