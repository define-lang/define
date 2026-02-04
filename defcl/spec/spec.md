# The Define Configuration Language Specification

Version: 0 (Subject to unpredictable breaking changes)

## Introduction

The Define Configuration Language (DCL) is a strict subset of the
[Protocol Buffers Text Format Language](https://protobuf.dev/reference/protobuf/textformat-spec/)
(textproto). DCL is used for configuration files in the `.define` directory of
Define projects, with the file extension `.defcl`.

This specification defines the syntax and restrictions of DCL. Any valid DCL
file must be parseable by a textproto parser, but DCL rejects many constructs
that are valid in textproto in order to enforce stricter rules and improve
consistency.

### Relationship to Textproto

DCL is based on textproto, but with the following key differences:

- DCL is more restrictive: many valid textproto constructs are errors in DCL
- DCL enforces stricter formatting rules for consistency
- DCL requires schema validation: unknown field names are errors
- DCL enforces that all top-level fields must be of type Message.

Any valid DCL file is also a valid textproto file, and can be parsed by standard
textproto parsers. However, a textproto parser will accept many files that DCL
rejects.

## Strictness

DCL is intended to be a very strict language. Any syntax or behavior not
specified in this spec is an error.

The language has no "undefined behavior." If a parser encounters a situation not
described in this spec, it must provide an error and refuse to parse the file.

Because DCL is derived from the textproto format, parts of this spec explicitly
note that some textproto syntax is not supported. However, that is just advisory
text---what matters are the statements of what we _do_ parse.

## File Format

DCL files use the `.defcl` filename extension. They are UTF-8 encoded with no
BOM.

DCL files must end with a newline character.

## Lexical Elements

The lexical elements described below are based on textproto, but with specific
restrictions. Lexical elements must match the input text exactly as described.

### Characters

```ebnf
char    = ? Any non-NUL unicode character ? ;
newline = ? ASCII #10 (line feed) ? ;

lowercase_letter = "a" | "b" | "c" | "d" | "e" | "f" | "g" | "h" | "i" | "j" | "k" | "l" | "m"
                 | "n" | "o" | "p" | "q" | "r" | "s" | "t" | "u" | "v" | "w" | "x" | "y" | "z" ;

uppercase_letter = "A" | "B" | "C" | "D" | "E" | "F" | "G" | "H" | "I" | "J" | "K" | "L" | "M"
                 | "N" | "O" | "P" | "Q" | "R" | "S" | "T" | "U" | "V" | "W" | "X" | "Y" | "Z" ;

dec = "0" | "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9" ;

hex = "0" | "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9"
    | "A" | "B" | "C" | "D" | "E" | "F"
    | "a" | "b" | "c" | "d" | "e" | "f" ;
```

### Whitespace and Comments

DCL restricts whitespace to only space characters and newlines. Tabs, carriage
returns, and other whitespace characters are not allowed except in comments.

```ebnf
COMMENT    = "#", { char - newline }, [ newline ] ;
WHITESPACE = " " | newline ;
```

Comments are shell-style line comments using `#`. Everything from `#` to the end
of the line is treated as a comment.

### Field Names

Field names in DCL are restricted to lowercase ASCII letters, digits, and
underscores only. Field names must conform to Proto Edition 2024 naming style
requirements:

1. Field names must start with a lowercase letter (cannot start with a digit or
   underscore)
2. Field names cannot end with an underscore
3. Any underscore must be followed by a letter (not a digit or another
   underscore)

```ebnf
FIELD_NAME = lowercase_letter, { lowercase_letter | dec | ( "_", lowercase_letter ) } ;
```

Examples of valid field names:

- `universe_name`
- `project_id`

Examples of invalid field names:

- `UniverseName` (contains uppercase)
- `universe-name` (contains hyphen)
- `universe.name` (contains period)
- `_universe_name` (starts with underscore)
- `universe_name_` (ends with underscore)
- `123field` (starts with digit)
- `config_value_1` (underscore followed by digit)
- `config__value` (double underscore)

### Numeric Literals

DCL has strict rules for numeric literals:

1. No space is allowed between a sign and the number
2. The `+` sign is not allowed (only `-` for negative numbers)
3. Floating point numbers must be exactly `INT.INT` format (no leading or
   trailing decimal points, no scientific notation, no type suffixes)

```ebnf
dec_lit   = "0"
          | ( dec - "0" ), { dec } ;
INTEGER = [ "-" ], dec_lit ;
FLOAT = [ "-" ], dec_lit, ".", dec, { dec } ;
```

Valid numeric literals:

- `10`
- `-5`
- `3.14`
- `-2.0`

Invalid numeric literals:

- `+10` (no `+` sign allowed)
- `- 5` (space between sign and number)
- `.5` (must have integer part)
- `10.` (must have fractional part)
- `10f` or `10F` (no type suffixes)
- `1e5` (no scientific notation)
- `1.5e-2` (no scientific notation)

### String Literals

DCL only allows double-quoted strings. Single-quoted strings are not allowed.

```ebnf
STRING = '"', { escape | char - '"' - newline - "\" }, '"' ;

escape = "\a"                        (* ASCII #7  (bell)                 *)
       | "\b"                        (* ASCII #8  (backspace)            *)
       | "\f"                        (* ASCII #12 (form feed)            *)
       | "\n"                        (* ASCII #10 (line feed)            *)
       | "\r"                        (* ASCII #13 (carriage return)      *)
       | "\t"                        (* ASCII #9  (horizontal tab)       *)
       | "\v"                        (* ASCII #11 (vertical tab)         *)
       | "\?"                        (* ASCII #63 (question mark)        *)
       | "\\"                        (* ASCII #92 (backslash)            *)
       | "\'"                        (* ASCII #39 (apostrophe)           *)
       | '\"'                        (* ASCII #34 (quote)                *)
       | "\", oct, [ oct, [ oct ] ]  (* octal escaped byte value         *)
       | "\x", hex, [ hex ]          (* hexadecimal escaped byte value   *)
       | "\u", hex, hex, hex, hex    (* Unicode code point up to 0xffff  *)
       | "\U000",
         hex, hex, hex, hex, hex     (* Unicode code point up to 0xfffff *)
       | "\U0010",
         hex, hex, hex, hex ;        (* Unicode code point between 0x100000 and 0x10ffff *)
```

Valid string literals:

- `"hello"`
- `"hello world"`
- `"say \"hello\""`

Invalid string literals:

- `'hello'` (single quotes not allowed)

## Syntax Elements

### Top-Level Syntax

A DCL file consists of one or more top-level messages. Each top-level message
has a field name followed by a colon and a message value.

```ebnf
file = { WHITESPACE }, top_level_message, { WHITESPACE, top_level_message }, { WHITESPACE } ;

top_level_message = FIELD_NAME, ":", message_value ;
```

Note that `message_value` is defined below.

Valid:

```
project: {
    universe_name: "example"
}
```

Multiple top-level messages are allowed:

```
project: {
    universe_name: "example"
}
settings: {
    debug_mode: false
}
```

### Field Syntax

In DCL, field names must be followed by a colon. The syntax for fields is:

```ebnf
field = FIELD_NAME, ":", [ WHITESPACE ], value ;
```

Note that `value` is defined below.

Valid:

```
universe_name: "example"
```

Invalid:

```
universe_name "example"
```

### Values

A value in DCL can be a string literal, numeric literal enum value, message
value, or repeated value:

```ebnf
value = STRING
     | INTEGER
     | FLOAT
     | enum_value
     | message_value
     | repeated_value ;
```

### Enum Values

Enum values may only be specified using the name from the enum definition.
Integer enum values are not allowed. Enum value names must start with an
uppercase letter and may only contain uppercase letters, digits, and
underscores.

```ebnf
enum_value = uppercase_letter, { uppercase_letter | dec | "_" } ;
```

Note that `enum_value` uses `uppercase_letter` and `dec` from the lexical
elements, but must be validated against the schema to ensure it is a valid enum
name for the field's type.

Valid (assuming `Status` enum has `ACTIVE` and `INACTIVE` values):

```
status: ACTIVE
status: INACTIVE
status: STATUS_ACTIVE
```

Invalid:

```
status: 0
status: 1
status: active
status: Active
```

### Message Values

Message fields in DCL must always use curly braces `{}`, never angle brackets
`<>`.

```ebnf
message_value = "{", [ WHITESPACE ], [ field_list ], [ WHITESPACE ], "}" ;

field_list = field, { WHITESPACE, field } ;
```

Empty message values `{}` are allowed. Whitespace (spaces and newlines) is
allowed before and after the field list within the braces.

Valid:

```
project: {
    universe_name: "example"
}
```

Invalid:

```
project: <
    universe_name: "example"
>
```

### Repeated Field Syntax

Repeated fields must always use the list syntax with square brackets `[]`. This
applies to both repeated message values and repeated scalar literals (strings,
numbers, enums).

```ebnf
repeated_value = "[", [ WHITESPACE ], [ value_list ], [ WHITESPACE ], "]" ;

value_list = value, { ",", [ WHITESPACE ], value } ;
```

Note that `value` is defined in the Value Types section below.

Valid (repeated message values):

```
dependencies: [
    { universe: "mv:example.com:lib1" },
    { universe: "mv:example.com:lib2" }
]
```

Valid (repeated literals):

```
tags: ["tag1", "tag2", "tag3"]
```

Valid (single literal in a repeated field):

```
tags: ["tag1"]
```

Invalid (single scalar in a repeated field with no brackets):

```
tags: "tag1"
```

Invalid (repeated message fields without brackets):

```
dependencies: { universe: "mv:example.com:lib1" }
dependencies: { universe: "mv:example.com:lib2" }
```

Invalid (repeated scalar without brackets):

```
tags: "tag1"
tags: "tag2"
tags: "tag3"
```

## Schema Restrictions

Because DCL is intended to be parsed by a textproto parser, it is expected that
its schema will be defined via protocol buffers. However, we place some
restrictions on that schema.

### Top-Level Structure

Literal values at the top level of a DCL file are not allowed. The top-level
message may only contain message fields.

### Prohibited Field Types

The following field types are not allowed in DCL:

- `bool` (DCL instead provides a standard enum `Dcl::Boolean` which has the
  values `UNSPECIFIED`, `TRUE`, and `FALSE`, though schemas are encouraged to
  define their own enums with more appropriate names)
- `bytes`
- `Any` (`google.protobuf.Any`)
- Extension annotations (using `[package.field]` syntax) are not allowed
- Proto2 `group` fields are not allowed

### Edition Requirement

All schema files must use edition 2024 or later. The `edition = "2024";`
declaration must appear at the top of every `.proto` file.

### Enums Must Be Defined Inside of Messages

For historical reasons based on the C++ implementation of protocol buffers,
proto enums defined outside of messages must have their values prefixed like
this:

```proto
enum Status {
    STATUS_UNSPECIFIED = 0;
    STATUS_ACTIVE = 1;
    STATUS_INACTIVE = 2;
}
```

However, enums defined inside of messages can use simpler names:

```proto
message User {
    enum Status {
        UNSPECIFIED = 0;
        ACTIVE = 1;
        INACTIVE = 2;
    }
}
```

### Proto Best Practices

For DCL schemas, the
[Proto Best Practices](https://protobuf.dev/best-practices/dos-donts/) are
mandatory, with the following modifications:

- Old enum names may never be removed.
- The name required for the 0 value on enums is `UNSPECIFIED`.
- The validator should look at field names and attempt to enforce the rule about
  using well-known types based on the field name.
- Don't move between repeated and scalar on a field at all (in either direction)
- The point about keywords should strive to protect keywords in all common
  programming languages, so that tools can be built in all languages to parse
  DCL.

Also, although DCL is a strictly-specified text format, do not use the Define
Configuration Language for interchange between systems, do not send it across
the wire, do not use it as a permanent storage format in a database, etc. This
is a point already made in the Best Practices, but it is clarified that it does
apply to DCL.

Other systems are free to use DCL for their own configuration needs, but it is
not intended to be a wire format, an API format, etc.

### Time Fields

In the [Proto Best Practices](https://protobuf.dev/best-practices/dos-donts/),
there are many different types of well-known types for various forms of time.
These must be named in the following fashion:

- `duration` fields must end in `_duration`
- `timestamp` fields must end in `_timestamp`
- `interval` fields must end in `_interval`
- `date` fields must end in `_date`
- `month` fields must end in `_month`
- `dayofweek` fields must end in `_weekday`
- `timeofday` fields must end in `_clocktime`

Fields ending with those suffixes must also always have those well-known types.

## Parser Behavior

### Unknown Fields

When parsing a DCL file, unknown field names (fields not present in the schema)
are errors. The parser must validate that all field names exist in the schema
and reject the file if any unknown fields are encountered.

## Example of a Valid DCL File

```
project: {
    universe_name: "mv:example.com:my_project"
    author: "Max Developer"
    dependencies: [
        { universe: "mv:alice.com:math_utils" },
        { universe: "mv:bob.com:networking" }
    ]
    settings: {
        debug_mode: FALSE
        log_level: 3
        timeout_seconds: 30.5
    }
}
```

### Example of Valid Schema Files

Defining the schema for the above DCL file requires multiple schema files.

Root schema file (defines the top-level structure):

```proto
edition = "2024";

import "project.proto"

message ProjectConfigFile {
    Project project = 1;
}
```

`project.proto`:

```proto
edition = "2024";

import "dependency.proto";
import "settings.proto";

message Project {
    string universe_name = 1;
    string author = 2;
    repeated Dependency dependencies = 3;
    Settings settings = 4;
}
```

`dependency.proto`

```proto
edition = "2024";

message Dependency {
    string universe = 1;
}
```

`settings.proto`:

```proto
edition = "2024";

message Settings {
    Dcl::Boolean debug_mode = 1;
    int32 log_level = 2;
    float timeout_seconds = 3;
}
```
