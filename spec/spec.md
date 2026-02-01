<!--
Instructions for humans and AI agents modifying this file:

This is a concise description of exactly what the compiler needs to do in
order to correctly implement Define's syntax and semantics. It is a specification
for a programming language called Define.

Nothing may be added to this spec unless there is first a Define Language Proposal
for that aspect of the language.

This file does not contain justifications or reasons for why decisions were made.
Instead, sections link to the relevant Define Language Proposals, like this:

## Naming

Proposals:
- [DLP 1: Types of Names](../proposals/00001-types-of-names.md)
- [DLP 2: Universes](../proposals/00002-universes.md)
- [DLP 3: Authorities](../proposals/00003-authorities.md)

Then after that the section contains concise wording, EBNF specifications, and
whatever else is needed to convey the precise details the compiler needs to know.

If a parent header lists a Define Language Proposal, the subheaders do not also
need to list that proposal. However, some DLPs will only be relevant to a subheader,
and so would be listed there.

This comment may not be modified by AI agents.
-->

# The Define Language Specification

## Introduction

This specification defines the syntax and semantics needed to compile Define
programs.

Every aspect of this specification is covered by a
[Define Language Proposal](../proposals/). Sections of this doc link to those
proposals, which contain the rationale behind Define's language decisions. This
specification contains only the specifics required for the compiler to correctly
implement Define.

The concepts behind Define are described in
[The Conceptual Basis of Define](concepts.md). It is expected that the reader
has at least a general understanding of the concepts described there.

At a high level, the language's design is guided also by our
[Principles](principles.md) and [Requirements](requirements.md).

Whenever possible, this spec defines concepts before referencing them. As such,
later sections build on or modify earlier sections. If there is a conflict, the
section that appears later in this spec "wins."

## A Note About Undefined Behavior

Define is intended to be a very strict language. Any syntax or semantics not
specified in this spec is an error.

Define has no "undefined behavior." If the compiler encounters a situation not
described in this spec, it will provide an error and refuse to compile the
program.

In the case that there is a bug in the compiler and it does not behave according
to the spec, future versions of Define may fix that bug even if it causes
existing programs to fail to compile (that is, even if it breaks backward
compatibility).

## Filesystem vs Non-Filesystem Contexts

When Define tools are parsing a file that contains source code, in a filesystem,
that is considered a "filesystem context."

When Define tools are parsing source code via some other mechanism, such as Unix
`stdin`, some form of Read/Eval/Print Loop (aka a "REPL"), a text box on a
website, etc. that is considered a "non-filesystem context."

These terms are defined here so that they can be used elsewhere in this spec.

## Parsing Define Source Code

Proposals:

- [DLP 35: Parsing Define Files](../proposals/00035-parsing-define-files.md)

Define conforms to
[Unicode Technical Standard #55 (Unicode Source Code Handling)](https://www.unicode.org/reports/tr55/).
When Define is less restrictive than UTS #55, that is a bug.

Note that all rules laid out in this section apply in both filesystem contexts
and non-filesystem contexts.

### Encoding

- Define source code is written in UTF-8.
- Define uses Unicode 17.0.0.
- Byte-order marks are forbidden.
- Invalid Unicode sequences are forbidden.

### Newlines

- The only valid line terminator is `U+000A` (line feed).
- A source file must end with a newline.
- There may not be a space (`U+0020`) immediately before a newline.
- Unless otherwise specified, a newline must immediately follow a statement
  terminator, `{`, or `}`.

### Invisible Characters

The only invisible characters allowed in Define source code files are:

- Space (`U+0020`)
- Line feed (`U+000A`)
- Characters necessary for correctly rendering visible Unicode text, provided
  their use conforms to UTS #55 (especially for BiDi handling).

An invisible character is necessary for rendering visible text if and only if it
is part of an extended grapheme cluster (per
[UAX #29](https://www.unicode.org/reports/tr29/) Section 3.1.1, Grapheme Cluster
Boundary Rules) that contains at least one character with a visible glyph.

### Allowed Syntax Characters

Syntax with semantics may use only these Unicode codepoints:

- `U+0020` through `U+0040`
- `U+005B` through `U+007E`

Exceptions:

- Names have their own rules.
- Comments allow all characters except those restricted elsewhere; UTS #55
  applies to comments.

### Spaces in Syntax

When syntax specifies a space, the parser requires exactly one space (`U+0020`)
in that position.

## Lexical Elements

There are a few EBNF productions that are frequently re-used in this spec, so
they are defined here.

```ebnf
digit = "0" | "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9" ;
lowercase_ascii = "a" | "b" | "c" | "d" | "e" | "f" | "g" | "h" | "i" | "j" | "k" | "l"
    | "m" | "n" | "o" | "p" | "q" | "r" | "s" | "t" | "u" | "v" | "w" | "x" | "y" | "z" ;
uppercase_ascii = "A" | "B" | "C" | "D" | "E" | "F" | "G" | "H" | "I" | "J" | "K" | "L"
    | "M" | "N" | "O" | "P" | "Q" | "R" | "S" | "T" | "U" | "V" | "W" | "X" | "Y" | "Z" ;
```

## Idiomatic Define

There is a style and structure that Define programs should have when written
natively in Define (as opposed to being translations of other programming
languages). When relevant, we explicitly refer to this style and structure as
"Idiomatic Define" in this spec.

The compiler will, by default, enforce the rules and restrictions of Idiomatic
Define. However, the compiler may provide the programmer the ability to specify
configurations that override the rules and restrictions of Idiomatic Define.

## Comments

Proposals:

- [DLP 11: Comments](../proposals/00011-comments.md)

Define supports single-line comments. A `#` character starts a comment;
everything from that `#` to the end of the line is ignored by the parser. A `#`
inside a string literal does not start a comment.

```ebnf
comment      = "#", comment_text ;
comment_text = { ? any character allowed per Define parsing rules, excluding U+000A ? } ;
```

## Name Format

### Types of Names

Proposals:

- [DLP 1: Types of Names](../proposals/00001-types-of-names.md)

Define reserves all words and symbols for its own use in syntax.

Names defined by the programmer are only allowed when prefixed by a name type
and surrounded by angle brackets (`<` and `>`).

The valid name types are currently:

- `position`
- `action`

```ebnf
typed_name = name_type, "<", name_content, ">" ;
name_type  = "position" | "action" ;
```

Define Language Proposals sometimes sometimes use the term "name" to mean
`typed_name`, but also sometimes to mean `name_content`. The EBNF in this spec
clarifies the actual intent when there is ambiguity.

### Restricted Characters in `name_content`

Proposals:

- [DLP 36: Allowed Name Characters](../proposals/00036-allowed-name-characters.md)

As described below in various sections, Define allows configuration to exist
that changes what characters are allowed in names. However, regardless of what
the configuration says, there are certain rules that always override the
configuration.

This EBNF production is intended to indicate "the characters configured to be
allowed in this section of a name, provided they obey the following restriction
rules."

```ebnf
{ ? allowed name characters ? }
```

#### Banned Unicode Codepoints

The following Unicode codepoints are banned in names and may never be allowed by
configuration:

- `U+0000` through `U+001F` (control characters)
- `U+007F` through `U+009F` (extended control characters)
- `U+00A0` (non-breaking space)

If configuration allows characters that violate
[UAX #31](https://www.unicode.org/reports/tr31/) `ID_Start` or `ID_Continue`, an
additional configuration value must be specified indicating the user
acknowledges unsafe characters are allowed.

Allowing these characters is considered an error in the configuration file and
Define tooling must refuse to parse files if configuration violates these rules.

#### Normalization

If configuration allows characters requiring normalization per
[UAX #15](https://unicode.org/reports/tr15/), the parser normalizes names to
Normalization Form C (NFC). Thus, Define considers two `name_content` values to
be identical if they have the same Normalization Form C. Tools that
automatically modify Define source code files may rewrite `name_content` bytes
in source code to NFC without prompting the user.

#### Escapes

The following characters must always be escaped with `\` to appear in
`name_content`: `\`, `<`, `>`.

If configuration allows any character that must be escaped to appear, then `\`
is automatically also a valid character in that part of the name syntax.

### Local vs Global Name Syntax

There are two types of names defined by the programmer that can be in
`name_content`: "local names" and "global names."

```ebnf
name_content = local_name | global_name
```

### Local Name Syntax

In Idiomatic Define, local names only contain lowercase ASCII letters and `_`.
They also may not start with a digit. However, configuration may override this,
changing the parser's restrictions.

If configuration allows `/` in local names, it must be escaped.

```ebnf
local_start_char = lowercase_ascii | "_" ;
local_continue_char = lowercase_ascii | digit | "_" ;
local_name = ( local_start_char, { local_continue_char } ) | { ? allowed name characters ? };
```

### Global Name Syntax

Proposals:

- [DLP 5: Global Names, Local Names, and Scopes](../proposals/00005-global-names-local-names-and-scopes.md)

Global names have four components:

1. Multiverse
2. Authority
3. Universe
4. Path

The first three components combine to form what is called a "fully-qualified
universe name," or "FQUN."

```ebnf
fqun =
    ( multiverse, ":", authority, ":", universe, ":"
    | authority, ":", universe, ":"
    | "standard:"
    | "" ) ;
global_name = fqun, global_name_path ;
```

#### Path

The "path" component of a global name may contain the exact same characters as a
local name, plus `/`. A path must start with `/`. Every `/` in the path must be
followed by at least one other valid character.

In Idiomatic Define, the first character after any `/` in a path may not be a
digit.

Unlike local names, `/` in a path does not need to be escaped.

If configuration allows the path to contain a `:`, it must be escaped with `\`.

```ebnf
global_name_path = "/", local_name, { "/", local_name } ;
```

#### Universe

Universe names may only contain ASCII letters, digits, and `_`. Configuration
may not allow any other characters in universe names.

Universe names must contain at least two characters, and may not start or end
with `_`.

In a codebase written in Idiomatic Define, the universe name of that codebase
(as defined later in this spec) may not contain uppercase ASCII letters.

```ebnf
universe_boundary_char = uppercase_ascii | lowercase_ascii | digit ;
universe_char          = universe_boundary_char | "_" ;
universe               = universe_boundary_char, { universe_char }, universe_boundary_char ;
```

##### Reserved Universe Names

The following universe names are reserved:

- `standard`: reserved for the Define Standard Library.
- `example`: reserved for use in documentation examples. (Define tooling may
  have a mode that allows this name to be used when validating that
  documentation examples have the correct syntax.)

The following names are also reserved, to avoid confusion:

```
authority
define
fqun
local
multiverse
mv
name
type
universe
```

Finally, a list of small common English words listed in [small_common_words.txt]
are reserved.

Reserved names are reserved case-insensitively; thus `standard`, `Standard`, and
`sTanDarD` are all reserved.

Define tools must refuse to download, create, publish, or interact with
universes that have reserved names, except as specified by this specification.

#### Authority

Proposals:

- [DLP 3: Authorities](../proposals/00003-authorities.md)

Wherever a universe is specified as part of a global name, an authority must be
specified, unless the universe is `standard`.

Authority names have two parts: a domain and a path. The path is optional. The
authority consists of the domain followed by an optional path.

```ebnf
authority = authority_domain [ authority_path ] ;
```

##### Domain

The domain is the portion of an authority before the first `/`. It must be a
valid lowercase domain name (though it does not have to contain a `.`). This
means it allows only lowercase ASCII letters, digits, `.`, and `-`. It may not
start or end with `-` or `.`.

The domain portion of an authority must be at least two characters long.

```ebnf
authority_domain_boundary_char = lowercase_ascii | digit ;
authority_domain_char = authority_domain_boundary_char | "-" | "." ;
authority_domain =
    authority_domain_boundary_char,
    { authority_domain_char },
    authority_domain_boundary_char ;
```

##### Path

The path is the portion after the first `/`. It is composed of one or more
segments separated by `/`. It may contain lowercase ASCII letters, digits, `_`,
`-`, `.`, and `~`. A path segment may not start with `.`.

```ebnf
authority_path_char = lowercase_ascii | digit | "_" | "-" | "." | "~" ;
authority_path_segment_start = lowercase_ascii | digit | "_" | "-" | "~" ;
authority_path_segment = authority_path_segment_start, { authority_path_char } ;
authority_path = "/", authority_path_segment, { "/", authority_path_segment } ;
```

##### Standard Authority

When Define tooling needs to represent the `standard` universe internally, it
considers the authority to be named `define`.

##### Reserved Authority Names

All names reserved for universes are also reserved for authority names.

We additionally reserve `example.com` for use in documentation examples only.

In the `mv` and `local` multiverses, all authorities where the domain does not
contain a `.` are reserved.

Similar to universes, reserved authority names are reserved case-insensitively.

Define tools must refuse to download, create, publish, or interact with
universes where the authority component of the FQUN contains a reserved name,
except as specified by this specification.

#### Multiverse

Proposals:

- [DLP 4: Multiverses](../proposals/00004-multiverses.md)

When a multiverse is not specified in a fully-qualified universe name, it
defaults to `local`. The name `local` may not be explicitly written in a
fully-qualified universe name; it may only be implicitly inferred.

When a multiverse name is specified, an authority and universe must also be
specified.

Multiverse names may only contain lowercase ASCII characters, digits, and `_`.
They must be at least two characters long and may not start or end with `_`.

````ebnf
multiverse_boundary_char = lowercase_ascii | digit ;
multiverse_char = multiverse_boundary_char | "_" ;
multiverse = multiverse_boundary_char, { multiverse_char }, multiverse_boundary_char ;
```

##### Reserved Multiverse Names

All names reserved for universes are also reserved for multiverse names.

In addition, the following multiverse names are reserved:

- `mv`
- Package repository names from other languages: see [package_repositories.txt]
- Programming language names: see [programming_languages.txt]

Reserved multiverse names are reserved case-insensitively.

Define tools must refuse to download, create, publish, or interact with
universes where the multiverse component of the FQUN contains a reserved name,
except as specified by this specification.

##### Special Multiverse Names

`mv` represents the standard multiverse where shared Define code is published
for public consumption. Define tools may accept this multiverse.

`local` represents code that exists only on a single machine. Code in the
`local` multiverse may never be published to any package repository. Define
tools will refuse to download any package from the `local` multiverse, expecting
code in that multiverse to only be on the local machine. However, Define tools
may create and interact with such code locally.
````

## Configuration Directory

Proposals:

- [DLP 10: Configuration Directory](../proposals/00010-configuration-directory.md)

All configuration that affects Define tooling goes into a `.define`
subdirectory. The direct contents of `.define` must only be subdirectories,
never files. These subdirectories are referred to as "configuration
directories," and may themselves contain both subdirectories and files.

Configuration directory names may contain only lowercase ASCII characters and
the underscore character. Define reserves all configuration directory names for
its own use. Third-party libraries and tools may not create any new
configuration directory name.

Files that contain configuration values inside configuration directories have
the extension `.defcl` and are written in the
[Define Configuration Language](dcl/spec.md).

Define tooling favors using configuration in configuration directories over
using command line flags whenever reasonable. Define tooling also strongly
attempts to avoid ever defining or using environment variables for
configuration.

### Third-Party Configurations

`x` is the configuration directory for all third-party configuration.

The `x` directory contains a subdirectory structure that matches the multiverse,
authority, and universe of the tool that wishes to create a configuration file.
For example, the universe `mv:example.com:math_utils` places any configuration
it needs into `.define/x/mv/example.com/math_utils/`.

Third-party configurations may contain anything. If they contain configuration
values, they are strongly encouraged to write them in the Define Configuration
Language.

When Define tooling removes a universe from being a dependency of a codebase, it
may delete that universe's configuration files from the project root. If such
configuration exists, the tool must clearly inform the developer that removing
the library will also remove the configuration. Developers may choose to retain
the configuration when informed it will be deleted.

## Project Roots

Proposals:

- [DLP 6: Project Roots](../proposals/00006-project-roots.md)

All Define codebases that exist on a filesystem have a "project root," which is
the directory that is the super-directory of all the code in the project. This
directory is the directory represented by the first `/` in the path component of
a global name.

Any directory that contains the path `.define/project/config.defcl` is a project
root. The existence of that file creates a project root regardless of its
contents.

Note that this spec section thus defines a new configuration directory called
`project`. At this time, `config.defcl` is its only contents.

Any given universe has a single directory that is its project root.

### Tools Must Be Invoked from the Root

When the compiler or any Define language tool is invoked in a filesystem
context, the current directory must be a project root. Otherwise, the tool must
refuse to execute and return an error.

Tool implementers may provide a command-line flag that discovers a project root
in a directory above the current directory. In that case, the tool discovers
that directory and changes its current working directory to that directory.

The compiler's current working directory must remain the project root for the
lifetime of the compiler (with exceptions as specified elsewhere in this spec).

### Sub-Projects

Define assumes that all code it sees in any subdirectory of a project root is
part of the same project unless the project configuration says otherwise. If
there are project roots in a directory structure below the current root, the
current root's configuration must indicate the existence of those "sub-roots."
The parent configuration must list each sub-root by path relative to this
project root, and must explicitly provide the fully-qualified universe name
expected in that sub-root.

When the compiler reads the configuration in a sub-root, the file
`.define/project/config.defcl` in that sub-root must declare the same
fully-qualified universe name that the parent configuration specified for that
sub-root.

Sub-roots are only compiled when the code indicates that compiling them is
necessary, not simply because they are listed in the configuration. When a
compiler or Define tool compiles a sub-root, it creates a new context, switches
its current working directory to that sub-root, runs a complete compilation on
that sub-root as its own universe, then returns to compiling the parent root.

### Duplicate Universes are Forbidden

No two sub-roots that are actually compiled during a compilation may contain the
same fully-qualified universe name.

### Non-Filesystem Contexts

When code is compiled via a non-filesystem context, the project root only
becomes relevant when the compiler discovers it needs information about the
project root. The compiler does not look for or require a project root until it
needs one. The compiler may accept a command-line flag to indicate a project
root that should be used during non-filesystem compilation.

## Resolving Global Names

Proposals:

- [DLP 7: Global Names Match Filesystem Layouts](../proposals/00007-global-names-match-filesystem-layouts.md)
- [DLP 8: Files Are Loaded By Reference](../proposals/00008-files-are-loaded-by-reference.md)

When the compiler requires the definition of a global name, it must discover
that definition. We call this "resolving" a global name.

Resolution of global names occurs only after after lexing, parsing, and AST
transformation of the current file is complete.

### Loading Source Code Files

Define loads source code files only when it must resolve a global name.

In a filesystem context, the path component of a global name must map directly
to a path on the disk, relative to the project root. However, the source code
file name ends in `.def` (which the global name does not contain).

### Names Must Match Paths

When reading a source code file, any global name(s) defined in that file must
match the file's path relative to the project root.

One file may contain multiple definitions of different types as long as they
share the exact same filesystem path.

### Sub-Root Conflict Detection

The compiler must indicate an error if it discovers that a file is within a
sub-root that was compiled as part of this compilation, but was loaded as though
it belonged to a different root.

### Non-Filesystem Contexts

In non-filesystem contexts, global names must be defined before being
referenced. Otherwise, the compiler has two options that can be controlled by a
command-line flag or configuration:

- Fail with an error indicating the name is undefined.
- Detect a project root in the current working directory and try to resolve the
  global name in a filesystem context.

Any path-based restrictions above apply only when needing to resolve global
names in a filesystem context.
