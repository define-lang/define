# Define Language Proposal 52: Literals

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

### 1: Parsing the Language

Allowing literals means you suddenly have to allow other syntax where you
normally allow variables. In Define, it means you suddenly have to allow some
form of literals to be injected into anything that expects a value.

### 2: Parsing the Literal

You have to know how to parse the literal itself.

A few languages allow custom parsers for literals, like Julia or C++. However,
they both do this through reflection-type mechanisms that Define doesn't have.
Julia does it through macros and C++ does it through `constexpr` functions that
the compiler can evaluate at compilation time. Perhaps when Define is
self-hosting we could have functionality like that, but it's pretty tricky to do
it in any Define compiler implementation and have it be performant. (You'd have
to pre-compile some Define code and then arbitrarily run it during compilation,
likely crossing an OS-level shared library boundary to do it.)

Most languages, though, have fixed, built-in syntax for literal parsing.

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

### 3: Parsing can Fail

Normal converters in Define cannot fail---the compiler proves they will work
before they execute (they know they are getting a valid input and they know that
that input can be successfully converted to their destination output). But
parsing a literal _can_ fail. The programmer can write `12x` for an integer
literal, and that's not parseable. What's the mechanism we use for converters
that can fail?

### 4: Converting the Literal

What does this do?

```C
int value = 'c';
```

In C, it sets `value` to the number 99. Well, provided you're on an
ASCII-compatible system. If you're on some other crazy system, it will probably
be some other value.

In other languages, who knows. In JavaScript (where you would just have
`value = 'c'`) you would just have a string, not a numeric value. What happens
later in JavaScript when you do `value + 1`? You get `c1`. In C you get `100`.
While all of that eventually becomes intuitive to programmers in those
languages, it actually doesn't make a lot of sense when you step back and think
it through. Why can you assign a character or string to a value that you intend
to be an integer?

In general, this is part of a larger class of issues: how do you convert the
written value of a literal into the actual computer representation of that value
in the compiled code?

### 5: Where You Allow Literals

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

### 6: Validity

When discussing parsing literals above, you want something like `12x` to simply
be treated as a malformed integer by the parser.

But what happens if you try to assign the number `300` to a value that's
constrained to be an eight-bit integer? That's not a value that it can store.

### 7: Approximation

Specifying `1.3` as a float value can't be literally represented as a float, so
you're going to get an approximation. Specifying `1.81341872347863521341234` for
some types is likely to get rounded, depending on the available precision.

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

### Escaping

The characters `>`, `:`, and `\` must be escaped by a `\` in literals.

Unlike all other typed names, literals _may_ contain whitespace. However, at
this time, they may not contain raw newlines (LF). Newlines can be specified
with `\n`.

Escaping any other character is not currently supported and will be treated as
an error.

### Valid Locations

Literals may be specified on the right side of the `set the value of`
statements.

Literals may also be placed in any input view of any value operation (any view
that is not written to by the operation).

### Literal Parsers

Literals are always assigned to something that expects a certain value type.
However, implementation-wise, what really happens is that the compiler is
expecting a particular _encoding_ that has to be valid for that type.

This is actually why a literal specifies its encoding, so that we know how to
convert it into something the computer will understand at runtime.

The way this is actually implemented, for now, is that the compiler must have
custom code to parse any encoding specified in a literal. The compiler will have
a map from the input encoding to multiple possible destination encodings that
points to different parsers in some way or another.

If no parser is available that maps from the literal's encoding to the
destination value encoding, the compiler will throw an error at compile time.
This is how we will prevent assigning inappropriate literals to values.

The compiler's parser can fail during compilation time if given invalid input.
When generating code, the compiler generates the literal in the destination
encoding, so that it does not require additional conversion at runtime.

### Constraint Rejection

Just as with all assignments, literals will be rejected for assignment if they
do not match the value's constraints.

### Approximation

Approximation is acceptable for literal parsers that target an encoding that
cannot exactly represent the declared literal. Where approximation is
unavoidable, like specifying `1.3` as a float, the compiler will simply silently
convert the representation according to the documentation of that encoding.

Some approximations are avoidable, however. For example, imagine that we
specified the number `1.000001` as a literal but put it into some encoding or
value type that claims to only have two significant digits of accuracy. That's
the developer making a mistake that they are probably not aware of making, so
the compiler should throw an error in that case.

### Selecting Destination Encodings

Encodings for a value are still inferred the normal way. However, specifying a
literal as something you set a value to can influence the compiler's decision on
what encoding type it will have. In particular, if no other type is available,
the available converters for the literal can influence what encoding the value
gets.

If the destination encoding cannot hold the literal's value, the compiler throws
an error. This will happen most often for particles that have an explicit
encoding specified as part of their assigned qualities.

### Ephemeral Particles

When a literal is specified as an input to an operation, conceptually what
occurs is an ephemeral particle is created just for running that operation,
given that literal as its set value, and assigned the value type the operation
expects with the constraints the operation expects.

You could think of this:

```define
execute the operation<standard:/number/rational/add> {
    with view<a> looking at literal<standard:/number:5>.
    with view<b> looking at position<second_input>.
    with view<result> looking at position<result>.
}
```

As being equivalent to this:

```define
define the position<temporary> {
    it may only contain particles where {
        it has the value<standard:/number/rational>.
    }
}
create a particle in position<temporary>.
set the value of position<temporary> to literal<standard:/number:5>.
execute the operation<standard:/number/rational/add> {
    with view<a> looking at position<temporary>.
    with view<b> looking at position<second_input>.
    with view<result> looking at position<result>.
}
```

In fact, the compiler will enforce this: if all you do is create a particle just
to give it a literal value and pass it to _one_ operation, the compiler will
require you to specify the literal directly as the input (to prevent "there is
more than one way to do it").

Ephemeral particles are automatically destroyed as soon as they are no longer
needed.

## A Real Program

```define
define the potential value<standard:/number/rational>.

define the potential literal<standard:/decimal> {
    it has the encoding<standard:/encoding/string/decimal>.
}

define the potential action<mv:example.com:example:/set_price> {
    define the position<price> {
        it may only contain particles where {
            it has the value<standard:/number/rational>.
        }
    }

    it happens when {
        the position<price> has a particle.
    } and it does {
        set the value of position<price> to literal<standard:/decimal:12.50>.
    }
}
```

```define
define the potential value<standard:/string>.

define the potential literal<standard:/string> {
    it has the encoding<standard:/encoding/string/utf8>.
}

define the potential action<mv:example.com:example:/set_greeting> {
    define the position<greeting> {
        it may only contain particles where {
            it has the value<standard:/string>.
        }
    }

    it happens when {
        the position<greeting> has a particle.
    } and it does {
        set the value of position<greeting> to literal<standard:/string:Hello, world!>.
    }
}
```

## Why This is the Right Solution

The first and most important thing this does is protect our "all words are
reserved" policy for Define and avoid having arbitrary syntax just show up in
some location. Having `literal<>` delimit all literals solves those problems. It
actually simplifies our parser a fair bit in general, because all you're doing
is taking the whole string at the end of the literal expression and passing it
to some other parser, which will decide what to do with it.

Specifying a global name to give a literal a "type" allows us to know how to
parse the literal and get more specific and helpful about errors.

The system of destination encodings prevents "you can assign a string to an
integer" or "this literal is too large for this number type" or other validity
issues.

### Ephemeral Particles

The logic of ephemeral particles is essentially self-explanatory: not allowing
them would be a form of obnoxious code duplication that doesn't get us any
value, because we _can_ just logically construct the relevant particle.

The downside is that it's one of the new places in Define where two different
things can appear in the same location (now either a position or a literal can
be what a view is looking at) which makes dumb static analysis slightly more
annoying, but not in a very particularly difficult way, I think. I think the
trade-off is worth it in this case.

### Literal Parsers

One of the harder decisions here was about how to deal with parsing literals.
Not only can a literal parser fail, there are _conceptual_ conflicts between it
and a normal converter. A literal parser exists in the universe of reflection,
and is basically always some form of string parser. A converter used by
encodings at runtime exists in the universe of the computer.

Originally I had literals use the existing converter system. After all, the
syntax and requirements are basically identical. However, I still had to
actually _implement_ all the parsers in the compiler, in a way that wasn't
different between target platforms particularly, but instead just special to the
compiler itself. I believe in the future there will be an extension mechanism
for adding new literal parsers, but this will also require an extension
mechanism for the compiler itself, which we would have to specify.

## Forward Compatibility

The escaping rules might be a little tricky to change in the future, but not
super hard, since we know we can parse every literal in every valid Define
program.

In general, we are protecting our future syntax with the `literal<>` wrapper,
and all of the semantics are expressed explicitly and not left up to magic,
other than the current system of compiler-defined literal parsers. Those
built-in parsers do represent some risk. If they change in the future, they
could change the behavior of existing programs in somewhat unpredictable ways.
I'm optimistic that the syntax and semantics of Define programs would let us
refactor existing programs to account for those risks, though.

## Refactoring Existing Systems

As far as I know, every other language's literals could be represented in this
system. For systems that allow literal extensions like C++ or Julia, we would
have to allow extensions, which we _could_ allow in the future.
