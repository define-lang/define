# Define Configuration Language Proposal 3: Each Field Is Written Once

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** November 3, 2026
- **Date Finalized:**

## Problems

Protocol Buffer Text Format lets a repeated field appear more than once in the
same message, and it joins the values into one list. defcl inherits that, so
these two files mean exactly the same thing:

```
deps: {
    local: [
        { universe_name: "a" path: "x" },
        { universe_name: "b" path: "y" }
    ]
}
```

```
deps: {
    local: [{ universe_name: "a" path: "x" }]
    local: [{ universe_name: "b" path: "y" }]
}
```

That is two ways to do the same thing, which defcl intends to forbid. A reader
of the second file also has to search the whole message to know what a list
holds.

Also, sometimes in error messages you might want to be able to say "this field
that is set at this line and column." If a field can appear in more than one
location, you can't say that. It's a minor issue, but it could come up.

## Solution

A field name may appear at most once in a message, whether or not the field is
repeated. All the values of a repeated field go in its one list.

This already holds for fields that are not repeated, because the textproto
parser rejects them when they appear twice. This proposal extends the rule to
repeated fields, so it has no exceptions.

The second file above is a syntax error at the second `local`, saying that the
field was already written in this message.

## A Real Program

```
deps: {
    local: [
        { universe_name: "mv:alice.com:math_utils" path: "math_utils" },
        { universe_name: "mv:bob.com:networking" path: "networking" }
    ]
}
```

## Why This is the Right Solution

It follows defcl's "one way" philosophy from
[DCLP 1](00001-the-define-configuration-language.md): every list has one
spelling, and every field has one location in the file.

## Forward Compatibility

If we later want a field to appear more than once, allowing it makes no existing
file invalid, and the meaning of every existing file stays the same.

## Refactoring Existing Systems

To fix a file that writes a repeated field more than once, concatenate the lists
in the order they appear and write them as one list at the first occurrence. The
result is the same message.
