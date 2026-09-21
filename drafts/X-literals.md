# Define Language Proposal X: Literals

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** September 21, 2026
- **Date Finalized:**

## Problems

All programs need some way to specify literal values, like numbers or strings
that you want to set variables to. In Define, we need something that can be on
the right side of `set the value of position<foo> to X.` (where X is). Literals
have way more problems than you would imagine, though, given that they look so
simple in most languages.

### Parsing the Language

Allowing literals means you suddenly have to allow other syntax where you
normally allow variables. In Define, it means you suddenly have to allow some
form of literals to be injected into anything that expects a value.

### Parsing the Literal

You have to know how to parse the literal itself. Most languages have fixed,
built-in syntax for this. A few allow custom parsers for literals, like Julia or
C++.

With the fixed syntax, it can be awkward. `0102` means "parse this as octal" but
`102` means "parse this as decimal." Some do `129024328957L` to mean "treat this
as a long int," which the parser doesn't know until it hits the L at the end.
(It also means the parser _always_ has to anticipate letters potentially being
at the end of a numeric literal.)

Not only does this complicate parsers quite a lot (e.g., "is `0L` a variable
name or an integer literal?") it also allows the programmer to typo and not
quite realize it. (For example, in many languages, typing `1.` makes that into a
floating point number, which you probably didn't intend.)

In short, the parser gets complex and it's sometimes hard for the parser to tell
you that you made an error.

### Converting the Literal

What does this do?

```C
int value = 'c';
```

In C, it sets `value` to the number 99. Well, provided you're on an
ASCII-compatible system. If you're on some other crazy system, it will probably
be some other value.

In other languages, who knows. In Python (where you would just have
`value = 'c'`) you would just have a string, not a numeric value. What happens
later in Python when you do `value + 1`? You get `c1`. In C you get `100`. While
all of that eventually becomes intuitive to programmers in those languages, it
actually doesn't make a lot of sense when you step back and think it through.
Why can you assign a character or string to a value that you intend to be an
integer?

In general, this is part of a larger class of issues: how do you convert the
written value of a literal into the actual computer representation of that value
in the compiled code?

### Where You Allow Literals

Do you allow literals only when setting a value on a particle, or do you allow
literals directly written in operations?

If you allow them in operations, you need semantics for what that means (there's
no particle that we are operating on).

If you _don't_ allow them in operations, you're obnoxiously forcing the
programmer to create a particle they will probably only use in this one
operation. Being obnoxious to the programmer is not outside the normal
principles of Define, but it doesn't mean we _want_ to be obnoxious, especially
if the particular form of obnoxiousness also seems irrational or creates
confusing semantics.

### Validity

When discussing parsing literals above, you want something like `12x` to simply
be treated as a malformed integer by the parser.

But what happens if you try to assign the number `300` to a value that's
constrained to be an eight-bit integer? That's not a value that it can store.

## Solution

Literals in Define are written by the programmer like this:

`literal<mv:example.com:example:/some/type:5>`

This creates a new name type, `literal`. The value at the very end, after the
final colon, is the actual literal value.

### Potential Literals

The global name in a literal points to another new concept, a
`potential literal`, which always uses global names and has syntax like this:

```define
define the potential literal<mv:example.com:example:/some/type> {
    it has the encoding<standard:/encoding/string/decimal>.
}
```

That allows developers to specify a literal of that type. The value of the
literal will be treated as having the specified encoding. The encodings will
probably always be some form of string encoding, but theoretically there could
be a future in which non-string encodings are allowed somehow.

### Valid Locations

Literals may be specified on the right side of the `set the value of`
statements.

Literals may also be placed in any input view of any value operation (any view
that is not written to by the operation).

### Converters

Literals are always assigned to something that expects a certain value type.
However, implementation-wise, what really happens is that the system is
expecting a particular _encoding_ that has to be valid for that type.

This is actually why a literal specifies its encoding, so that it can be tied to
a converter. These work just the same as any other converter, except that they
must be available at compile time, not just at runtime.

If no converter is available from the literal's encoding to the destination
value encoding, the compiler will throw an error at compile this. This is how we
will prevent assigning inappropriate literals to values.

The converter is thus both the parser and the validity checker.

### Selecting Destination Encodings

Encodings for a value are still inferred the normal way. However, specifying a
literal as something you set a value to can influence the compiler's decision on
what encoding type it will have. In particular, if no other type is available,
the available converters for the literal can influence what encoding the value
gets.

## A Real Program

## Why This is the Right Solution

## Forward Compatibility

## Refactoring Existing Systems
