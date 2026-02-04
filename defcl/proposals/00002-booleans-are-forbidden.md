# Define Configuration Language Proposal 2: Booleans Are Forbidden

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** January 6, 2026
- **Date Finalized:**

## Problems

### 1: Bool → Enum Migration

It's very easy to start off thinking that some configuration value is binary and
so only has two states, and only discover later that you need more than one
state. However, changing a field from `bool` to an enum breaks existing configs
and code, requiring a migration (including a sometimes-complex migration of
code).

For example, you can start off with a schema and config like this:

```proto
edition = "2024";

message Settings {
    bool use_color = 1;
}
```

```proto
settings: { use_color: true }
```

But then later you discover that you need more states:

```proto
edition = "2024";

message Settings {
    enum UseColor {
        UNSPECIFIED = 0;
        TRUE = 1;
        FALSE = 2;
        ONLY_IN_TERMINAL = 3;
    }

    UseColor use_color = 1;
}
```

One of the biggest problems with that, is that now it's actually `UNSPECIFIED`
that reads as false (because it's 0) in most programming languages, not `FALSE`.

### 2: `bool` Cannot Represent "Unset"

Many configurations need to differentiate between `false` and "not set." With a
bool there is no way to do this reliably. Yes, protos have the `has_` methods,
but realistically most configuration consumers just check the field and get the
default (which is probably `false`).

For example, what's the intended value of `use_color` here?

```proto
edition = "2024";

message Settings {
    bool use_color = 1;
}
```

```proto
settings: { }
```

The intended value is "no value." So that needs to be an explicit option for all
bools.

## Solution

DCL does not allow `bool` fields in schemas.

Instead, any "boolean-like" setting must be represented as an enum with an
explicit `UNSPECIFIED` value.

For convenience and consistency, DCL provides a standard enum `Dcl::Boolean`
with these values:

- `UNSPECIFIED`
- `TRUE`
- `FALSE`

All textproto parsers today can correctly parse these, even though their names
overlap with booleans, because the parsers know they are parsing an enum field.

Schemas are also encouraged to define their own enums when that provides a
clearer expression of intent. However, configuration authors should keep in mind
that enum values need to be intuitive and memorable for developers who have to
write config files.

## A Real Program

Schema:

```proto
edition = "2024";

message Settings {
    Dcl::Boolean use_color = 1;
}

message Project {
    Settings settings = 1;
}

message ProjectConfigFile {
    Project project = 1;
}
```

Config:

```
project: {
    settings: {
        use_color: UNSPECIFIED
    }
}
```

## Why This is the Right Solution

This solves both problems above:

- It creates forward compatibilty for config files by eliminating the "bool to
  enum" migration entirely.
- Because of how textproto parsing works, if you need to move from
  `Dcl::Boolean` to another enum type, it's still possible as long as you need
  `TRUE`, `FALSE`, and `UNSPECIFIED` as values in your enum.
- It makes "unset" explicit via `UNSPECIFIED`.

Now, also because of how the textproto parser works, it _is_ possible to migrate
from a `bool` field to an enum with the values `TRUE` and `FALSE`. So we could
have done that instead. However, that leaves behind a trap in code for things
that are checking false values---in the enum it's a `2` but in the bool it's
`false`. Best to simply avoid that trap for configuration consumers.

We also could have relied on the `has_` methods, but in my experience relying on
those in unreliable. Developers forget to check presence and then you're
treating "unset" as `false` in unexpected locations.

## Forward Compatibility

Enums can add values without changing the field type. Values are explicit
tokens, so tools can refactor deterministically.

## Refactoring Existing Systems

If any existing schemas _had_ used bool, we could simply change the type in the
schema to `Dcl::Boolean`. However, we would have to then go fix all the code
that consumed the config. Since the compiler is not yet self-hosting, the thing
that consumes the config does not guarantee perfect refactorability and likely
would require manual adjustments.
