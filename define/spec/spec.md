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

Version: 0 (subject to breaking changes at any time)

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
- Unless otherwise specified, a newline or one or more spaces followed by a
  comment must immediately follow a statement terminator, `{`, or `}`.

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
newline = "\n" ;
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

Comments are text that are ignored by Define.

A `#` character starts a comment; everything from that `#` to the end of any
line is ignored by the parser. A comment may be preceded by any number of
spaces. A `#` inside a string literal does not start a comment.

```ebnf
comment      = { " " }, "#", comment_text, newline ;
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
name_content = local_name | global_name ;
```

### Local Name Syntax

In Idiomatic Define, local names only contain lowercase ASCII letters and `_`.
They also may not start with a digit. However, configuration may override this,
changing the parser's restrictions.

If configuration allows `/` in local names, it must be escaped.

```ebnf
local_start_char = lowercase_ascii | "_" ;
local_continue_char = lowercase_ascii | digit | "_" ;
local_name =
    ( local_start_char, { local_continue_char } )
    | ( ? allowed name characters ?, { ? allowed name characters ? } ) ;
typed_local_name = name_type, "<", local_name, ">" ;
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
typed_global_name = name_type, "<", global_name, ">" ;
global_name = ("" | fqun), global_name_path ;
fully_qualified_global_name = fqun, global_name_path ;
fqun =
    ( multiverse, ":", authority, ":", universe, ":"
    | authority, ":", universe, ":"
    | "standard:") ;
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

In Idiomatic Define, a project (defined later in this spec) may not define
global names that contain a universe name with uppercase ASCII letters.

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

Finally, a list of small common English words listed in
[small_common_words.txt](../reserved_words/small_common_words.txt) are reserved.

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
authority = authority_domain, [ authority_path ] ;
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

```ebnf
multiverse_boundary_char = lowercase_ascii | digit ;
multiverse_char = multiverse_boundary_char | "_" ;
multiverse = multiverse_boundary_char, { multiverse_char }, multiverse_boundary_char ;
```

##### Reserved Multiverse Names

All names reserved for universes are also reserved for multiverse names.

In addition, the following multiverse names are reserved:

- `mv`
- Package repository names from other languages: see
  [package_repositories.txt](../reserved_words/package_repositories.txt)
- Programming language names: see
  [programming_languages.txt](../reserved_words/programming_languages.txt)

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
[Define Configuration Language](../../defcl/spec/spec.md).

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

The configuration of a sub-root is only loaded when the compiler needs to load a
file inside of the sub-root. The code of a sub-root is compiled only when it is
referenced from another file being compiled, just like all other files.
(Sub-roots are not automatically compiled just because they are referenced in
parent's configuration.)

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
file name ends in `.dfn` (which the global name does not contain).

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
  global name in a filesystem context. This is the compiler's default behavior.

Any path-based restrictions above apply only when needing to resolve global
names in a filesystem context.

## Statements

Proposals:

- [DLP 16: Statement Terminators](../proposals/00016-statement-terminators.md)

In Define, a statement is either:

- Code that ends in `.` followed by a newline or a comment.
- Code that has `{` followed by a newline or a comment, though `{` is not part
  of the statement.

```ebnf
terminator = ".", ( newline | " ", { " " }, comment ) ;
```

## Blocks

- [DLP 15: Local Name Scope Syntax](../proposals/00015-local-name-scope-syntax.md)

A block is any code enclosed by `{` and `}`. Blocks are always preceded by
statements without a terminating `.`.

The opening `{` must be on the same line as the statement that creates the
block, with exactly one space immediately before `{`.

The closing `}` must be on a line that contains only whitespace and `}`. The
leading whitespace before `}` must be identical to the leading whitespace before
the statement that opened the scope.

If a line is directly contained within a block, its leading whitespace must be
exactly four spaces longer than the leading whitespace of the statement that
opened that block. For nested blocks, this rule applies recursively.

```ebnf
block_open = " ", "{", newline ;
block_close = "}", newline ;
```

### Non-Filesystem Contexts

In a non-filesystem context, all whitespace restrictions (including newline
requirements) on blocks are relaxed.

## Scopes

Proposals:

- [DLP 5: Global Names, Local Names, and Scopes](../proposals/00005-global-names-local-names-and-scopes.md)
- [DLP 15: Local Name Scope Syntax](../proposals/00015-local-name-scope-syntax.md)

Define has two types of scopes: a single scope called the "global scope," and
many scopes called "local scopes."

### Global Scope

Code written outside of any block is in the global scope. Restrictions on the
global scope:

- The global scope may define only global names.
- Global names may be defined only in the global scope.

### Local Scopes

Any block that can directly contain a definition is a local scope. For the sake
of clarity, this spec will specify whenever syntax creates a local scope. Note
that not all blocks create local scopes.

### Parent Scopes

The "current scope" of any code in Define is the scope in which the code is
written.

When this spec refers to a "transitive parent scope," it means the current
scope, the current scope's current scope, and so on, up to and including the
global scope.

"Transitive child scopes" would have the opposite meaning, starting from the
current scope and walking down the scope chain, including all scopes defined
within the current scope.

### No Name Conflicts

A `typed_name` defined in any scope may not be identical to any other
`typed_name` defined in its transitive parent scopes.

### Referring to Names Within Scopes

A reference to a local name is valid only if the name is defined in a transitive
parent scope.

A reference to a local name that is not defined in a transitive parent scope is
an error.

### Referring to Inner Definitions

Names can be chained with `::` to refer to inner definitions. Each subsequent
name in the chain must be a name either defined directly inside the previous
name or assigned to a particle via syntax described later in this spec. The full
name thus created is called a "chained name."

```ebnf
chained_name = typed_name, { "::", typed_name } ;
```

### Local Naming is Enforced

When a local name reference is valid in the current scope (including any
transitive parent scope), it must be written as just a single `typed_name` in
local name format. Global names must not be used where local names are valid.

### No Inner Global Definitions

Definitions inside a local scope must use local names. Defining a global name
inside a local scope is an error.

### Global Name Short Forms

Proposals:

- [DLP 27: Shortening Common Names](../proposals/00027-shortening-common-names.md)

A "short global name" is a global name where the FQUN is omitted (thus only the
path is used).

When a global name definition creates a local scope, references to other global
names may appear in that scope and its transitive child scopes. The following
rules apply to those references:

- If the referenced global name has the same FQUN as the enclosing definition,
  the reference must use the short form. Using the full FQUN is an error.
- If the referenced global name has a different FQUN, the reference must include
  the full FQUN. Using the short form is an error.

## Defining Local Positions

Proposals:

- [DLP 12: Definitions in the Universe of Reflection](../proposals/00012-definitions-in-the-universe-of-reflection.md)
- [DLP 19: Guaranteeing Qualities in Positions](../proposals/00019-guaranteeing-qualities-in-positions.md)

Within a local scope, a position may be defined by `define the position`
followed by a local name in angle brackets. It may be followed by a statement
terminator or a block. This block does not create a local scope.

```ebnf
local_position_name = "position", "<", local_name, ">" ;
local_position_definition = "define the", " ", local_position_name, local_position_definition_end ;
local_position_definition_end = terminator | local_position_definition_block ;
local_position_definition_block = block_open, position_constraint_block, block_close ;
```

### Position Constraint Block

A Position Constraint Block starts with `it may only contain particles where`
and then opens a block. The block must contain one or more Position Requirement
Statements.

```ebnf
position_constraint_block =
    "it may only contain particles where",
    block_open,
    position_requirement_statement,
    { position_requirement_statement },
    block_close ;
```

### Position Requirement Statements

A Local Position Requirement Statement starts with `it has the` followed by a
typed name and a statement terminator.

```ebnf
position_requirement_statement = "it has the", " ", typed_global_name, terminator ;
```

## Position References

Proposals:

- [DLP 23: Particles Define Other Positions](../proposals/00023-particles-define-other-positions.md)

A position reference is a single position name or a chained name that ends with
the name of a position.

Below, when we talk about a "parent name," we mean the name in the chain
immediately before the name we are talking about. In
`position<a>::position</b>`, `position<a>` is the parent name of `position</b>`.

Unless otherwise stated, the rules for all position references are:

- The first name in the chain must have been defined _before_ it is referenced.
- For global position or action names in the chain, those must be specified as a
  constraint on their parent name.
- For local position names, the parent name must be an action and the local
  position must be defined in the Action Definition Block of that action.
- Every position in the chain except the last must already contain a particle.
- The statement that uses the position reference determines whether the last
  position in the chain must contain a particle or be empty.

```ebnf
position_reference =
    local_or_global_position,
    [ "::", { position_reference_middle, "::" }, local_or_global_position ] ;
local_or_global_position = local_position_name | global_position_name ;
position_reference_middle = local_or_global_position | action_name ;
action_name = "action", "<", global_name, ">" ;
global_position_name = "position", "<", global_name, ">" ;
```

## Defining Qualities

Proposals:

- [DLP 12: Definitions in the Universe of Reflection](../proposals/00012-definitions-in-the-universe-of-reflection.md)
- [DLP 22: Atomic Qualities](../proposals/00022-atomic-qualities.md)

Potential positions and potential actions are referred to as "qualities."
Qualities can be assigned to particles using syntax and semantics described
later in this spec.

The syntax for defining qualities is: `define the potential` followed by a space
and a fully-qualified typed global name.

Quality definitions may be followed by a block, in which case that block creates
a local scope. Some quality definitions may end with a statement terminator and
no block.

Quality definitions that end with a terminator are considered to be identical to
quality definitions that have an empty block following them. Explicitly writing
a quality definition with an empty block is forbidden---the statement terminator
syntax must be used to express empty definitions.

```ebnf
quality_definition = ( action_definition | position_definition ) ;
```

The forms of the definitions are defined in later sections.

## Defining Potential Positions

Proposals:

- [DLP 19: Guaranteeing Qualities in Positions](../proposals/00019-guaranteeing-qualities-in-positions.md)
- [DLP 22: Atomic Qualities](../proposals/00022-atomic-qualities.md)
- [DLP 23: Particles Define Other Positions](../proposals/00023-particles-define-other-positions.md)
- [DLP 24: Qualities May Not Define Qualities](../proposals/00024-qualities-may-not-define-qualities.md)

Potential positions are defined with `define the potential` followed by a space
and a global position name.

The syntax inside the block (called a Potential Position Definition Block) is
identical to the syntax for a local position, except that it allows for an extra
member: the Position Initialization Block, which must be the final block or
statement in the Potential Position Definition Block.

```ebnf
fully_qualified_global_position_name = "position", "<", fully_qualified_global_name, ">" ;
position_definition = "define the potential", " ", fully_qualified_global_position_name, position_definition_end ;
position_definition_end = terminator | potential_position_definition_block ;
potential_position_definition_block =
    block_open,
    { quality_implication_statement },
    ( position_constraint_block, [ position_initialization_block ] | position_initialization_block ),
    block_close ;
```

### Position Initialization

Proposals:

- [DLP 32: Position Initialization](../proposals/00032-position-initialization.md)

A Position Initialization Block starts with `after it is assigned` and then
opens a block. The block creates a new local scope.

A Position Initialization Block may contain one or more action statements.
Except as described below, a Position Initialization Block has the same syntax
and semantics as in an Action Statements Block. Every part of this specification
that refers to an Action Statements Block also applies to Position
Initialization Blocks unless explcitly stated.

An empty Position Initialization Block is not allowed.

```ebnf
position_initialization_block =
    "after it is assigned",
    block_open,
    action_statement,
    { action_statement },
    block_close ;
```

#### Referencing the Current Position

Inside a Position Initialization Block, the position being initialized can be
referenced and affected using its global short name.

#### Position Initialization Timing

Position initialization occurs synchronously immediately after the position is
assigned as a quality to a particle. It does not wait for all qualities on the
particle to be assigned, but triggers immediately after assignment.

If the compiler can determine it is safe to do so, it may re-order the execution
of position initialization blocks or move them to a different point of the
program, as long as the program's properties expressed in code are preserved.

#### Actions Triggered by Initialization

Actions triggered by statements in a Position Initialization Block still trigger
asynchronously. A Position Initialization Block that needs such an action to
complete must use `wait until`.

#### Guarantees Generated by Position Initialization

Position Initialization Blocks create
[Automatic Action Guarantees](#automatic-action-guarantees) for the
self-referenced position and any implied positions (including interface
positions of implied actions). These guarantees are applied when the init block
executes.

#### Requirements Generated by Position Initialization

Position Initialization Blocks expose
[Automatic Action Requirements](#automatic-action-requirements) for any implied
positions (including interface positions of implied actions). These requirements
are enforced before the init block executes.

## Defining Potential Actions

Proposals:

- [DLP 21: Defining Machines](../proposals/00021-defining-machines.md)
- [DLP 22: Atomic Qualities](../proposals/00022-atomic-qualities.md)
- [DLP 24: Qualities May Not Define Qualities](../proposals/00024-qualities-may-not-define-qualities.md)
- [DLP 37: Automatic Position Presence Constraints](../proposals/00037-automatic-position-presence-constraints.md)

A potential action is defined by a quality definition statement with the type
`action`, followed by an Action Definition Block.

An Action Definition Block may contain any number of local position definitions
(which are optional) followed by two other blocks: the Trigger Conditions Block
and the Action Statements Block, which are mandatory.

The Action Definition Block creates a new local scope.

```ebnf
fully_qualified_action_name = "action", "<", fully_qualified_global_name, ">" ;
action_definition = "define the potential", " ", fully_qualified_action_name, action_definition_block ;
action_definition_block =
    block_open,
    { quality_implication_statement },
    { local_position_definition },
    trigger_and_action,
    block_close ;
```

### Interface Positions

The local positions defined directly in an Action Definition Block are called
"interface positions."

When an action is assigned to a particle, its interface positions are initially
empty.

### Inner Blocks

The Trigger Conditions Block starts with `it happens when` and then opens a
block. The Trigger Conditions Block does not create a new local scope.

The Action Statements Block starts with `and it does` and then opens a block.
This statement starts on the same line as the closing `}` of the previous block,
which is an exception to the rule that `}` must always be on its own line. The
Action Statements Block creates a new local scope.

```ebnf
trigger_and_action = trigger_conditions_block, " ", action_statements_block ;
trigger_conditions_block = "it happens when", block_open, trigger_conditions, "}" ;
action_statements_block = "and it does", block_open, action_statements_contents, block_close ;
```

### Trigger Conditions Blocks

Proposals:

- [DLP 28: Triggering Actions](../proposals/00028-triggering-actions.md)

A Trigger Conditions Block contains one Trigger Condition Statement.

<!-- TODO: Update for multiple statements. -->

A Trigger Condition Statement is one of two types: a Position Presence Statement
or a Destructor Condition Statement (defined later in this spec).

A Position Presence Statement is `the position<name> has a particle.` It may
only refer to a single local name that is an interface position of the current
action. (The syntax does not accept chained names.)

When compiling an action, the compiler treats the requirements specified by that
action's Trigger Conditions Block as being satisfied.

```ebnf
trigger_conditions = trigger_condition_statement ;
trigger_condition_statement = position_presence_statement | destructor_condition_statement ;
position_presence_statement = "the", " ", typed_local_name, " has a particle", terminator ;
```

### Action Triggering Semantics

Proposals:

- [DLP 28: Triggering Actions](../proposals/00028-triggering-actions.md)

Actions trigger when their Trigger Conditions Block becomes true.

Actions do not continuously trigger while their conditions remain true. After an
action triggers, it only triggers again if its Trigger Conditions Block first
becomes false and then becomes true again.

Trigger conditions are checked only when program state changes in a way that can
affect those conditions, and only after assignment of the action to a particle
is complete. Thus, an action does not trigger on assignment if its trigger
conditions are already true at assignment time.

### Action Statement Blocks

Proposals:

- [DLP 30: Action Statement Blocks](../proposals/00030-action-statement-blocks.md)

An Action Statements Block must contain one or more action statements. An empty
Action Statements Block is not allowed.

Action statements are:

- local position definitions
- create particle statements
- move particle statements
- destroy particle statements
- quality assignment statements
- `wait until` statements

```ebnf
action_statements_contents = action_statement, { action_statement } ;
action_statement =
    local_position_definition
    | create_particle_statement
    | move_particle_statement
    | destroy_particle_statement
    | quality_assignment_statement
    | wait_until_statement ;
```

## Action Contracts

Actions provie a "contract" indicating what state must be true before they are
run and what state will be true when they complete.

For the rest of this section, when we refer to "contracted position" we mean an
interface position, a child name of an interface position, an implied quality,
or a child name of an implied quality. Contracts cover only contracted
positions.

### Automatic Action Requirements

Proposals:

- [DLP 37: Automatic Position Presence Constraints](../proposals/00037-automatic-position-presence-constraints.md)

For each contracted position that is not a trigger position, the compiler
automatically infers occupancy requirements for that position from the first
time an Action Statements Block statement references that position. These
inferred requirements are referred to as Action Requirements.

Callers must satisfy the Action Requirements of an action before triggering it,
or the compiler will throw an error.

These inferred requirements are thus treated as being always satisfied within
the Action Statements Block of an action that defines them.

#### How Requirements Are Inferred

If the first reference to the final position in a chained name of a contracted
position is a Create Particle Statement target or a Move Particle Statement
destination, that position is required to be empty.

If the first reference to the final position in a chain of a contracted position
is a Move Particle Statement source or a Destroy Particle Statement target, that
position is required to contain a particle.

Every intermediate position in a chained name of a contracted position is also
implicitly required to contain a particle, if it is the first time that
intermediate position is referenced in any chain (either within a chain or as
the final position) in the Action Statements Block.

#### Transitive Requirements On Interface Positions Are Preserved

Imagine a call chain where Action A calls Action B, then Action B calls Action
C. Imagine now that all of these calls happen through a chained name that is
visible as an interface position of Action B, like
`position<b_interface>::action</c>::position<c_iface>`, and let's also imagine
that Action C creates a requirement on `position<c_iface>` (either requiring it
to be empty or occupied).

If Action B does not fulfill the requirement on `position<c_iface>`, that
requirement is transitively passed on to Action A, which must fulfill it or pass
it on as appropriate to _its_ caller.

Requirements are only passed on if they can possibly be fulfilled by the caller,
which means this rule only applies to positions accessible via interface
positions of actions (any chained name that is a child of an interface
position).

### Transitive Requirements on Implied Positions

Implied positions always have their requirements transitively propagated up the
call chain of actions. The calling action's requirements override the called
action's requirements on implied positions, if they both impose a requirement on
the same position.

#### Requirements Follow Particles

If an action moves a particle from a contracted position and then takes some
action on a child position of that particle, that still creates a requirement on
the contracted position. Requirements are actually logically about particles the
caller passed in, not fixed positions.

### Automatic Action Guarantees

For each action, the compiler determines a set of "Action Guarantees." These are
facts that are guaranteed to always be true when an action completes.

The compiler determines a set of Action Position Occupancy Guarantees.

- Which contracted positions are always empty at the end of the action
- Which contracted positions are always filled at the end of the action

The compiler also determines a set of Action Particle Identity Guarantees. Upon
completion of an action, each particle in each position is in one of two
possible states:

- It is a particle was in one of the contracted positions at the start of the
  action, and thus has the same qualities as that particle had when it was
  passed in.
- It is a new particle created by this action or one of this action's callees,
  and thus has the qualities defined by the contracted position in which it was
  created.

The compiler uses these guarantees to reason about particle occupancy and
particle qualities in a fully modular way without having to do whole-program
dataflow analysis.

#### Transitive Guarantees on Implied Qualities

Guarantees about interface positions are visible only to an action's direct
caller. However, guarantees about implied positions are propagated transitively
up through an action's callers.

An action can create a different guarantee about an implied position than an
action it called, in which case the calling action's guarantee overrides the
called action's guarantee.

### Depth-First Post-Order Reference Graph Traversal

The Action Requirements and Action Guarantees system implicitly means that
actions must be processed in a post-order depth-first traversal of the
global-name reference graph (a graph of which definitions reference which global
names).

## Quality Implication Statements

Proposals:

- [DLP 22: Atomic Qualities](../proposals/00022-atomic-qualities.md)

A Quality Implication Statement starts with `it also assigns the`, followed by
exactly one space, a typed global name, and a statement terminator.

```ebnf
quality_implication_statement =
    "it also assigns the", " ", typed_global_name, terminator ;
```

### Assignment Semantics

When a quality A contains a Quality Implication Statement naming quality B, then
whenever A is assigned to a particle, B is automatically assigned to that same
particle beforehand. Quality Implication Statements are executed in the order
written in the code when executing their assignment to a particle.

Inside the implying quality's definition, the implied quality is treated as
already present on the particle. The implied quality and its child names may be
referenced directly in the implying quality's definition.

Implying a quality does _not_ expose the transitively implied qualities of that
quality. In order for any code within a global definition to reference a global
name as the first typed name in a chain (other than self-reference in Position
Initialization Blocks) it must be listed in an explicit Quality Implication
Statement at the top of the global definition.

### Duplicate Assignments

If a quality is already present on a particle when a Quality Implication
Statement would otherwise cause it to be assigned, the additional assignment
does not occur. Only the first assignment takes effect; subsequent attempts to
assign the same quality via Quality Implication Statements are silently skipped.

Explicitly implying the same quality within a definition (writing the same
quality implication statement twice) is an error.

### No Dead Dependencies

If an action definition contains a Quality Implication Statement, the implied
quality must be referenced as the first name of a chained name somewhere within
the action's Action Statements Block or Trigger Conditions Block.

If a position definition contains a Quality Implication Statement, the implied
quality must be referenced as the first name of a chained name somewhere within
the position's Position Initialization Block.

If the quaity is not so referenced, the compiler must throw an error.

## Creating Particles

Proposals:

- [DLP 13: Creating Particles](../proposals/00013-creating-particles.md)

A Create Particle Statement starts with `create a particle in`, followed by
exactly one space and a position reference, ending with a statement terminator.

It is an error if the referenced position already contains a particle.

```ebnf
create_particle_statement =
    "create a particle in", " ", position_reference, terminator ;
```

### Atomic Creation

Proposals:

- [DLP 20: Atomic Creation](../proposals/00020-atomic-creation.md)

If a Create Particle Statement targets a position with a Position Constraint
Block, the created particle is automatically assigned all required qualities
from that block as part of the creation.

#### Quality Assignment Sequence For Atomic Creation

During atomic creation, qualities are assigned in the same order as their
Position Requirement Statements appear in the Position Constraint Block.

The semantics of creating a particle in a constrained position are equivalent to
creating the particle in an unconstrained anonymous position, assigning the
required qualities in order, and then moving the particle into the referenced
position. In other words, the destination position's constraints are enforced
only after all required quality assignments for that creation are complete.

The compiler may choose to re-order quality assignments or perform them
concurrently if doing so is guaranteed to produce the same result as assigning
them in sequence.

## Moving Particles

Proposals:

- [DLP 17: Moving Particles](../proposals/00017-moving-particles.md)

A Move Particle Statement starts with `move the particle in`, followed by
exactly one space and a source position reference, then `to`, then a destination
position reference, ending with a statement terminator.

The source position reference must contain a particle.

It is an error if the source and destination position are the same.

It is an error if the destination position reference already contains a
particle.

```ebnf
move_particle_statement =
    "move the particle in", " ", position_reference, " to ", position_reference, terminator ;
```

### Cannot Move a Particle Into a Position It Defines

Proposals:

- [DLP 25: Particles May Not Contain Themselves](../proposals/00025-particles-may-not-contain-themselves.md)

In a Move Particle Statement, it is an error if the `from` position reference is
a prefix of the `to` position reference (also meaning it's an error if they are
identical).

### Destination Position Constraints Are Enforced During Moves

Proposals:

- [DLP 18: Modular Constraints](../proposals/00018-modular-constraints.md)
- [DLP 19: Guaranteeing Qualities in Positions](../proposals/00019-guaranteeing-qualities-in-positions.md)

In a Move Particle Statement, all required qualities from the destination
position's Position Constraint Block must be present on the particle being
moved.

It is an error if the particle being moved does not have one or more required
qualities of the destination position.

This rule must be enforced statically at compile time and must never be a
runtime check.

## Destroying Particles

Proposals:

- [DLP 31: Destroying Particles](../proposals/00031-destroying-particles.md)

A Destroy Particle Statement starts with `destroy the particle in`, followed by
exactly one space and a position reference, ending with a statement terminator.

It is an error to attempt to destroy a particle that does not exist, and the
compiler will forbid it.

```ebnf
destroy_particle_statement =
    "destroy the particle in", " ", position_reference, terminator ;
```

### Cascading Destruction

When a particle is destroyed, all of the particles in the positions it defines
are also destroyed.

Qualities are unassigned from the particle in reverse order to how they were
assigned to it. (Because requirement statements assign qualities topologically
in order according to their dependency tree, qualities are inherently removed in
reverse topological order.)

Before a position quality is unassigned, its particle is destroyed.

All position constraints defined by a position's definition are suspended at the
start of destruction until destruction completes.

Before removing an action from a particle, all particles that are still
contained in interface positions of that action are destroyed in reverse order
of when the positions were defined. Once removal of an action begins (and thus
its defined particles must be destroyed), the action may no longer trigger or
check its conditions.

Destruction completes as though it were a written series of unassignment and
destruction statements. Any action that triggers due to destruction of a child
particle fires immediately after that child's destruction is complete. This
means that a child particle's destruction may trigger an action asynchronously
before the destruction of the parent particle is complete.

Actions that would trigger due to the removal of a quality from a particle do
not fire due to the automatic quality removal process that happens during
destruction.

The compiler may optimize this process and does not have to actually unassign
every quality, as long as it ensures identical behavior occurs as if it had done
so.

### Automatic Destruction

Particles that can no longer possibly be referenced are automatically destroyed.

At the end of an Action Statements Block, any particles still existing in
positions that are only defined locally within that Action Statements Block are
automatically destroyed in reverse order of their position definition
statements.

The compiler behaves as through there were destruction statements at the end of
an Action Statements Block to implement this. If the compiler is uncertain about
whether a position still contains a particle, it only destroys the particle if
one is present.

Hitting a `wait until` statement does not count as exiting the Action Statements
Block, and does not trigger automatic destruction.

### Optimization of Destruction

When the compiler knows that destruction is free of side effects (there are no
action triggers watching for the destruction of that particle, including no
triggers watching any of the other positions that particle transitively
defines), the compiler may automatically destroy local particles within an
Action Statements Block the instant they are no longer relevant.

When safe, the compiler may destroy multiple particles simultaneously (in
parallel).

## Destructors

Proposals:

- [DLP 34: Destructors](../proposals/00034-destructors.md)
- [DLP 41: Modular Destructor Analysis](../proposals/00041-modular-destructor-analysis.md)

The Destructor Condition Statement is `this particle is being destroyed`
followed by a statement terminator. An action whose Trigger Conditions Block
contains a Destructor Condition Statement is called a "destructor."

```ebnf
destructor_condition_statement =
    "this particle is being destroyed", terminator ;
```

<!-- TODO:
A destructor may also check any other trigger conditions alongside the
destructor condition statement, which allows a destructor to fire only when the
particle is in a particular state.
-->

### When Destructors Are Checked

During the destruction cascade described in
[Cascading Destruction](#cascading-destruction), the compiler checks destructor
conditions immediately before the particles in the interface position of the
action would be destroyed. If a destructor would trigger, it runs synchronously
during the cascade and completes before the cascade continues.

This is an exception to the rule that actions may not trigger during the
cascade.

### Actions Triggered by Destructors

Any action triggered by a destructor still runs asynchronously, exactly as
actions triggered during normal execution do. A destructor that depends on such
an action completing must use `wait until`.

### Destructors Produce No Guarantees

Upon completion, a destructor must leave all contracted positions in the state
they were in when the action started.

### Destructor Requirement Verification

A destructor has [Automatic Action Requirements](#automatic-action-requirements)
that work identically to how they work for any other action. This is what the
compiler is verifying when it verifies a destructor.

Each destructor's requirements are verified independently of every other
destructor. It is not possible for one destructor to affect the requirements of
another destructor on the same particle.

### Destruction Contracts

When compiling any individual Action Statements Block, the compiler verifies
only the destructors that the immediate Action Statements Block is aware of
being on the particle at the time of destruction. For contracted positions,
those particles may have more qualities assigned to them than the immediate
Action Statements Block is aware of.

Thus, when an action destroys a particle that (a) the action itself did not
create and (b) is in a contracted position, its
[Action Contract](#action-contracts) records additional information about that
destruction. This additional information is called a Destruction Contract.

Destruction Contracts are used by callers higher in the call stack to validate
destructors that the action did not know were assigned to the particle, but
which those callers _do_ know are assigned to the particle. The intention of
Destruction Contracts is that each caller verifies the additional destructors it
knows about as though they were running at the moment of destruction (not inside
of the caller's code).

#### Destruction Fact

A Destruction Contract records that the specific particle that occupied the
contracted position was destroyed, not merely that the position became empty.
This is called a Destruction Fact.

When an action destroys more than one particle in its contracted positions, the
contract records those destructions in the order they were executed.

#### Child State

Before destroying a particle in a contracted position, the compiler takes a
snapshot of the occupancy state of all of that particle's transitive child
positions. This snapshot is recorded in the Destruction Contract and is called
the Child State.

An action may not know the full state of every transitive child position,
because it may not be aware of every quality on the destroyed particle. Each
action in the call chain therefore maintains its own cumulative Child State,
adding whatever it knows about the state of a child position immediately before
the parent particle was destroyed.

#### When Destructors in Contracts Are Verified

A destructor is verified as soon as the compiler knows the destructor is
assigned to a particle and knows the state of all positions that destructor has
[Automatic Action Requirements](#automatic-action-requirements) on. When the
compiler is missing either of these pieces of information, it passes on any
not-yet-verified destructor to an action's callers for verification, as part of
the Destruction Contract.

## Dead Code

Proposals:

- [DLP 42: Dead Code Is Forbidden](../proposals/00042-dead-code-is-forbidden.md)

Where the compiler is confident that code is dead, it must throw an error. The
below sections define what code is considered to be dead.

### Unreferenced Names

The following are all dead code:

- An action interface position that is never referenced within that action.
- A local position never referenced within the block where it is defined.
- An implied quality that is not referenced within the action or position that
  implies it.

### Dead Child Positions

A position quality assigned to a local or interface position is dead if it is
neither referenced within the same global definition nor required by any Move
Particle Statement.

### Untriggered Actions

If an action is a directly-written constraint on a local or interface position
but is never triggered inside of the same global definition that defines that
position and is not needed to satisfy any Move Particle Statement, that
constraint is dead code. Exception: destructors listed as constraints on a
position are never dead code.

## Starting Define Programs

Proposals:

- [DLP 33: Starting Define Programs](../proposals/00033-starting-define-programs.md)

Any global position definition may be the entry point of a program. Here is what
logically occurs from the compiler's viewpoint when starting a program:

1. An anonymous position is created, called the "view point position."
2. That anonymous position has exactly one constraint: it is assigned the
   potential position that is the program's entry point.
3. A particle is created in the view point position. This particle is called the
   "view point."

The program may not otherwise interact with the view point or view point
position in any way.

This action follows the normal rules of particle creation in constrained
positions. Thus, it triggers the Position Initialization Block of the potential
position, and all code in the program executes from there.

The potential position that is first assigned is called the "entry point
position," and any particle created in it is called the "entry point."

## Ending Define Programs

Define programs terminate when there are no actions running, or when terminated
by the external environment following the conventions of the operating system or
other external controller.
