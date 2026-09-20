# Define Language Proposal 50: Encoding Converter Associations

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** September 19, 2026
- **Date Finalized:**

## Problems

Just like with
[DLP 47 (Value Encoding Associations)](00047-value-encoding-associations.md) and
[DLP 48 (Encoding Operation Associations)](00048-encoding-operation-associations.md),
we need to be able to associate converters with the encodings they support.

Mostly this has the same problems as the other two proposals, with one
additional issue: direction.

Converters go from one encoding, and to another one. Do you associate them with
the input encoding, the output encoding, or both?

## Solution

Unless otherwise specified, this has an identical solution to
[DLP 47 (Value Encoding Associations)](00047-value-encoding-associations.md),
with some of the names changed.

Config goes into `.define/encodings/converters.defcl`. It has the format:

```protocol-buffer-text-format
converters: {
    encoding_converters: [
        {
            input: "/number/integer/unsigned/big_endian"
            output: "/number/integer/unsigned/little_endian"
            converter: "/number/integer/unsigned/big_endian_to_little_endian"
        },
    ]
}
```

The compiler validates that any loaded converter is a valid match for the input
and output it's supposed to convert, but attempts to do this lazily while still
guaranteeing correctness of the configuration file.

Note that this format currently means that the compiler could load more
converters than it actually needs, because actual converters can be
option-specific.

In any given `converters.defcl`, any given value of `converter` must appear only
once. However, a given input/output tuple can appear multiple times, because of
options. Also note that it is legal for input and output to be identical,
because of options.

### Project Root Config

The new field in the project root config is `has_converters`, like this:

```protocol-buffer-text-format
    encodings: {
        has_converters: TRUE
    }
```

`has_converters` defaults to false.

## A Real Program

```bash
# .define/project/config.defcl
project: {
    universe_name: "mv:example.com:numbers"
    encodings: {
        has_encodings: TRUE
        has_converters: TRUE
    }
}
```

```bash
# .define/encodings/encodings.defcl
encodings: {
    value_encodings: [
        {
            value: "/number/natural"
            encoding: "/number/integer/unsigned/big_endian"
        },
        {
            value: "/number/natural"
            encoding: "/number/integer/unsigned/little_endian"
        },
    ]
}
```

```bash
# .define/encodings/converters.defcl
converters: {
    encoding_converters: [
        {
            input: "/number/integer/unsigned/big_endian"
            output: "/number/integer/unsigned/little_endian"
            converter: "/number/integer/unsigned/big_endian_to_little_endian"
        },
    ]
}
```

```define
define the potential value<mv:example.com:numbers:/number/natural>.

define the constraint<mv:example.com:numbers:/bits/8to128> {
    its minimum value is 8.
    its maximum value is 128.
}

define the constraint<mv:example.com:numbers:/bits/32> {
    its minimum value is 32.
    its maximum value is 32.
}

define the encoding<mv:example.com:numbers:/number/integer/unsigned/big_endian> {
    define the encoding_option<bits> {
        it has the constraint</bits/8to128>.
    }
}

define the encoding<mv:example.com:numbers:/number/integer/unsigned/little_endian> {
    define the encoding_option<bits> {
        it has the constraint</bits/8to128>.
    }
}

define the converter<mv:example.com:numbers:/number/integer/unsigned/big_endian_to_little_endian> {
    it has the input encoding</number/integer/unsigned/big_endian> {
        it has the encoding_option<bits> {
            it has the constraint</bits/32>.
        }
    }

    it has the output encoding</number/integer/unsigned/little_endian> {
        it has the encoding_option<bits> {
            it has the constraint</bits/32>.
        }
    }

    it does {
        execute the computer converter.
    }
}
```

## Why This is the Right Solution

Identical to DLP 47 and 49, mostly.

On the direction, originally I actually had encodings specify their converters,
and allowed them to either specify a converter "FROM" themselves, or "TO"
themselves. This was very confusing, design-wise, though. Where do the
converters go, on what encoding, to avoid circular references (since the
converters have to reference the other encoding)? Is there any
actually-enforceable rule for that? If we allow extensions, are they supposed to
specify FROM for existing encodings, or TO? I couldn't just have FROM or just
TO, I _had_ to allow both.

Having the separate configuration file resolves that question entirely.
Code-level references don't even exist. Encodings don't know their converters
exist, and we can extend and add converters without having to add encodings.

## Forward Compatibility

Identical to DLP 47.

## Refactoring Existing Systems

Identical to DLP 47.
