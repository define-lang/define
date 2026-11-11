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

This specification uses standard terms used when discussing protocol buffers and
their schemas, and expects the reader to be familiar with those terms.

### Relationship to Textproto

DCL is based on textproto, but with the following key differences:

- DCL is more restrictive: many valid textproto constructs are errors in DCL
- DCL enforces stricter formatting rules for consistency
- DCL requires schema validation: unknown field names are errors
- DCL enforces that every field of the top-level message type is a non-repeated
  message field.
- DCL allows a field name only once in a message, even for repeated fields.
- DCL allows only one way to write a file: its layout and the order of its
  fields are fixed, so that two files with the same fields, values and comments
  are the same bytes, except that the characters of a string can be written in
  more than one way.

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
char    = ? Any Unicode character that the Invisible Characters rule allows ? ;
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

### Invisible Characters

A character is invisible if its Unicode General_Category is Cc, Cf, Cs, Co, Cn,
Zs, Zl, or Zp, or if it has the Default_Ignorable_Code_Point property. All other
characters are visible. Tabs, carriage returns, NUL, and the byte order mark are
all invisible.

The only invisible characters allowed in a DCL file are:

- Space (`U+0020`)
- Line feed (`U+000A`)
- Variation selectors 15 and 16 (`U+FE0E` and `U+FE0F`), when the character
  before them is visible and in the same comment or string.
- Zero width non-joiner and zero width joiner (`U+200C` and `U+200D`), when the
  character after them is visible, the character before them is visible or is
  `U+FE0E` or `U+FE0F`, and both are in the same comment or string.
- Left-to-right mark, right-to-left mark, and Arabic letter mark (`U+200E`,
  `U+200F`, and `U+061C`), in comments only.

This rule applies everywhere in a file, including comments and strings, so that
a file always looks the way it is read. A string can still hold any character
through an escape, such as `\t` or `\u202E`.

### Whitespace

DCL restricts whitespace to only space characters and newlines. Tabs, carriage
returns, and other whitespace characters are not allowed anywhere.

### Comments

Comments are shell-style line comments using `#`. Everything from `#` to the end
of the line is treated as a comment. A comment is a `#`, then a space, then its
text, which does not end with a space. A comment may also be just a `#` alone.

```ebnf
COMMENT      = "#", [ " ", comment_text ] ;
comment_text = { char - newline }, ( char - " " - newline ) ;
```

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

- `host_name`
- `max_connections`

Examples of invalid field names:

- `HostName` (contains uppercase)
- `host-name` (contains hyphen)
- `host.name` (contains period)
- `_host_name` (starts with underscore)
- `host_name_` (ends with underscore)
- `123field` (starts with digit)
- `config_value_1` (underscore followed by digit)
- `config__value` (double underscore)

### Numeric Literals

DCL has strict rules for numeric literals:

1. No space is allowed between a sign and the number
2. The `+` sign is not allowed (only `-` for negative numbers)
3. Floating point numbers must be exactly `INT.INT` format (no leading or
   trailing decimal points, no scientific notation, no type suffixes)
4. The fractional part of a floating point number must not end with `0`, unless
   it is exactly `0`
5. Zero cannot be negative: `-0` and `-0.0` are not allowed

```ebnf
dec_lit   = "0"
          | ( dec - "0" ), { dec } ;
INTEGER = ( [ "-" ], dec_lit ) - "-0" ;
fraction  = "0"
          | { dec }, ( dec - "0" ) ;
FLOAT = ( [ "-" ], dec_lit, ".", fraction ) - "-0.0" ;
```

Valid numeric literals:

- `10`
- `-5`
- `3.14`
- `-2.0`
- `1.05`

Invalid numeric literals:

- `+10` (no `+` sign allowed)
- `- 5` (space between sign and number)
- `.5` (must have integer part)
- `10.` (must have fractional part)
- `1.50` or `2.00` (fractional part ends with `0`)
- `10f` or `10F` (no type suffixes)
- `1e5` (no scientific notation)
- `1.5e-2` (no scientific notation)
- `-0` or `-0.0` (negative zero)

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

Restrictions on string literals:

- An octal escape's value must fit in a byte, so it is at most `\377`.
- A `\u` escape cannot be a surrogate (`\uD800` to `\uDFFF`), even as half of a
  surrogate pair; write a code point above `0xffff` with `\U` instead.
- A string must be valid UTF-8 once its escapes are replaced by what they stand
  for. Octal and hexadecimal escapes stand for single bytes, so a run of them
  must together form valid UTF-8.

Valid string literals:

- `"hello"`
- `"hello world"`
- `"say \"hello\""`
- `"caf\xc3\xa9"` (the bytes of `é` in UTF-8)
- `"caf\303\251"` (the same bytes, as octal escapes)
- `"\U0001F600"` (a code point above `0xffff`)

Invalid string literals:

- `'hello'` (single quotes not allowed)
- `"\400"` (octal escape past `\377`)
- `"\uD83D\uDE00"` (surrogate pair; write `"\U0001F600"` instead)
- `"\xff"` (not valid UTF-8)
- `"\xc3"` (an incomplete UTF-8 sequence)
- `"\xc3\n\xa9"` (an escape splits the UTF-8 sequence)

## Layout

A DCL file has exactly one correct layout, so two files with the same contents
are the same bytes.

### Lines

Each line holds one field, one element of a repeated value, one comment, or one
closing `}` or `]`. Two fields never share a line.

A message value's `{` goes at the end of its field's line. Its fields go on the
lines below, and its `}` goes on a line of its own. A repeated value works the
same way with `[` and `]`.

There are no blank lines, and the file ends with exactly one newline. Trailing
whitespace is forbidden on all lines.

### Indentation

Each level of indentation is 2 spaces. Everything inside a `{ }` or `[ ]` is
indented one level more than the line with its `{` or `[`. A closing `}` or `]`
is indented the same as the line with its opening `{` or `[`. Top-level messages
are not indented.

For example:

```
server: {
  host: "localhost"
  tags: [
    "web"
  ]
}
```

`server` and its `}` are at level 0. `host`, `tags`, and the `]` that closes
`tags` are at level 1. `"web"` is at level 2.

```ebnf
indentation = { "  " } ;
```

The number of times `indentation` repeats is the level of its line.

### Spacing

A field's name is followed directly by its colon, then exactly one space, then
its value. Each element of a repeated value except the last is followed directly
by a comma.

### Comments

A comment goes on a line of its own, indented the same as the field or element
after it. A comment after the last field or element of a message value, a
repeated value, or the file is indented the same as that field or element.

The whitespace and comments between two lines' contents are a `line_break`:

```ebnf
line_break   = newline, { comment_line }, indentation ;
comment_line = indentation, COMMENT, newline ;
```

### Examples

Valid:

```
# The database that the service uses.
database: {
  host: "db.example.com"
  replicas: [
    {
      host: "replica1.example.com"
    },
    # More replicas go here.
    {
      host: "replica2.example.com"
    }
  ]
}
```

Invalid:

```
database: { host: "db.example.com" }
database: {
 host: "db.example.com"
}
database: {
  host: "db.example.com" # The primary.

}
```

## Syntax Elements

### Top-Level Syntax

A DCL file consists of one or more top-level messages. Each top-level message
has a field name followed by a colon, exactly one space, and a message value.

```ebnf
file = { comment_line }, top_level_message, { line_break, top_level_message },
       newline, { comment_line } ;

top_level_message = FIELD_NAME, ":", " ", message_value ;
```

Note that `message_value` is defined below.

Valid:

```
server: {
  host: "localhost"
}
```

Multiple top-level messages are allowed:

```
server: {
  host: "localhost"
}
database: {
  host: "db.example.com"
}
```

### Field Syntax

In DCL, field names must be followed by a colon. The syntax for fields is:

```ebnf
field = FIELD_NAME, ":", " ", value ;
```

Note that `value` is defined below.

Valid:

```
host: "localhost"
```

Invalid:

```
host "localhost"
host:"localhost"
host : "localhost"
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

### Numeric Values

A value must be the kind of value that its field's type takes, as in textproto.
DCL is stricter for floating-point fields (`float` and `double`): their values
must be floating-point literals, never integer literals. For a repeated field,
this applies to each element.

Valid (assuming `timeout_seconds` is a `float` field):

```
timeout_seconds: 3.0
```

Invalid:

```
timeout_seconds: 3
```

Numbers must also be within the range allowed by their field's type:

- An integer must fit in the field's type, so a negative integer is not allowed
  in an unsigned field (`uint32`, `uint64`, `fixed32` and `fixed64`).
- A floating-point number must not be so large in magnitude that it rounds to
  infinity in the field's type.

Valid (assuming `port` is a `uint32` field, `offset` is an `int32` field and
`ratio` is a `float` field):

```
port: 4294967295
offset: -2147483648
ratio: 340282346638528859811704183484516925440.0
```

`ratio`'s value is the largest finite `float`.

Invalid:

```
port: -1
port: 4294967296
offset: 2147483648
ratio: 1000000000000000000000000000000000000000.0
```

`ratio`'s value, 10³⁹, rounds to infinity as a `float`.

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
message_value = "{", line_break, field, { line_break, field }, line_break, "}" ;
```

A message value must have at least one field. Empty message values `{}` are not
allowed.

Valid:

```
server: {
  host: "localhost"
}
```

Invalid:

```
server: <
  host: "localhost"
>
```

A message value can have at most one field of each oneof, as in textproto.

Valid (assuming `path` and `url` are the fields of a oneof):

```
source: {
  url: "https://example.com"
}
```

Invalid:

```
source: {
  path: "config.txt"
  url: "https://example.com"
}
```

### Field Order

The fields of a message value, and the top-level messages of a file, must be
written in the order of their field numbers in the schema.

Valid (assuming `host` is field 1 and `port` is field 2):

```
server: {
  host: "localhost"
  port: 8080
}
```

Invalid:

```
server: {
  port: 8080
  host: "localhost"
}
```

### Repeated Field Syntax

Repeated fields must be written as a single list using square brackets `[]`.
This applies both to repeated message fields and to repeated fields of scalars.

```ebnf
repeated_value = "[", line_break, element, { ",", line_break, element }, line_break, "]" ;

element = STRING | INTEGER | FLOAT | enum_value | message_value ;
```

An element of a repeated value cannot itself be a repeated value. A repeated
value has at least one element: empty repeated values `[]` are not allowed.

Valid (repeated message values):

```
replicas: [
  {
    host: "replica1.example.com"
  },
  {
    host: "replica2.example.com"
  }
]
```

Valid (repeated scalars):

```
tags: [
  "tag1",
  "tag2",
  "tag3"
]
```

Valid (one scalar in a repeated field):

```
tags: [
  "tag1"
]
```

Invalid (empty repeated value):

```
tags: []
```

Invalid (elements on one line):

```
tags: ["tag1", "tag2", "tag3"]
```

Invalid (single scalar in a repeated field with no brackets):

```
tags: "tag1"
```

Invalid (repeated message fields without brackets):

```
replicas: {
  host: "replica1.example.com"
}
replicas: {
  host: "replica2.example.com"
}
```

Invalid (repeated scalar without brackets):

```
tags: "tag1"
tags: "tag2"
tags: "tag3"
```

Invalid (repeated field written more than once, even with brackets):

```
tags: [
  "tag1",
  "tag2"
]
tags: [
  "tag3"
]
```

Write it as one list instead:

```
tags: [
  "tag1",
  "tag2",
  "tag3"
]
```

Invalid (repeated value as an element of a repeated value):

```
tags: [
  "tag1",
  [
    "tag2"
  ]
]
```

## Schema Restrictions

Because DCL is intended to be parsed by a textproto parser, it is expected that
its schema will be defined via protocol buffers. However, we place some
restrictions on that schema.

These restrictions apply to the top-level message type of a DCL file and to
every message type that its fields lead to. Other message types in the same
`.proto` files, or in the files they import, such as the definitions of field
options, are not restricted.

### Top-Level Structure

Literal values at the top level of a DCL file are not allowed. The top-level
message may only contain non-repeated message fields.

### Prohibited Field Types

The following field types are not allowed in DCL:

- `bool` (DCL instead provides a standard enum `defcl.schema.core.Defcl.Boolean`
  which has the values `UNSPECIFIED`, `TRUE`, and `FALSE`, though schemas are
  encouraged to define their own enums with more appropriate names)
- `bytes`
- `Any` (`google.protobuf.Any`)
- Extension annotations (using `[package.field]` syntax) are not allowed
- Proto2 `group` fields are not allowed

<!-- TODO: Decide whether map fields are allowed, and if so, how their entries
are written and whether duplicate keys are errors. -->

### Message Types Without Fields

A field's type must not be a message type that has no fields, since its value
could only be written as an empty message value. Use an enum field instead.

### Required Fields

Fields must not set `features.field_presence = LEGACY_REQUIRED`.

### UTF-8 Validation

String fields must not have `features.utf8_validation = NONE`, whether it is set
on the field or as the default of its file.

### Edition Requirement

All schema files must use edition 2024 or later.

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

### Syntax Errors

A parser reports every error in a file's layout and keeps parsing, so that it
can report every such error at once and also check the file against its schema.
Any other syntax error stops the parse. A file with any error is not valid.

### Unknown Fields

When parsing a DCL file, unknown field names (fields not present in the schema)
are errors. The parser must validate that all field names exist in the schema
and reject the file if any unknown fields are encountered.

## Example of a Valid DCL File

```
server: {
  host: "localhost"
  port: 8080
  debug_mode: FALSE
  timeout_seconds: 30.5
  tags: [
    "web",
    "public"
  ]
}
database: {
  host: "db.example.com"
  max_connections: 20
  replicas: [
    {
      host: "replica1.example.com"
    },
    {
      host: "replica2.example.com"
    }
  ]
}
```

### Example of Valid Schema Files

Defining the schema for the above DCL file requires multiple schema files.

Root schema file (defines the top-level message type):

```proto
edition = "2024";

import "server.proto";
import "database.proto";

message ServiceConfigFile {
    Server server = 1;
    Database database = 2;
}
```

`server.proto`:

```proto
edition = "2024";

import "defcl/schema/core/boolean.proto";

message Server {
    string host = 1;
    uint32 port = 2;
    defcl.schema.core.Defcl.Boolean debug_mode = 3;
    float timeout_seconds = 4;
    repeated string tags = 5;
}
```

`database.proto`:

```proto
edition = "2024";

message Database {
    string host = 1;
    int32 max_connections = 2;
    repeated Replica replicas = 3;
}

message Replica {
    string host = 1;
}
```
