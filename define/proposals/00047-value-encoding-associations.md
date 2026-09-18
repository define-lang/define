# Define Language Proposal 47: Value Encoding Associations

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** September 18, 2026
- **Date Finalized:**

## Problems

The compiler needs to somehow know which encoding to use for which value.

### 1: Files Are Loaded By Reference

In Define, files are only loaded by reference. So do values say what their
encodings are, or do encodings say what values they support, or something else
entirely?

If values say what encodings they support, then you can discover the encodings
naturally when a developer references the encoding. However, that means that to
add new valid encodings, you have to modify (and have access to modify) the
value's definition.

Also, if values say what encodings they support, then you're either (a) allowing
only one possible encoding, in which case you're logically tying a value to a
single encoding, which is the whole problem the whole system of value types is
trying to avoid or (b) allowing multiple potential encodings for a value and
then having to figure out at compile time which one applies. (a) is
unacceptable. (b) might be acceptable, though, provided there's a way for the
compiler to deterministically make that choice. Of course, (b) would still have
the problem specified in the above paragraph.

In the other direction, if encodings say what values they support, then you
_can't_ discover them automatically, because normally the programmer will just
specify the value type, not the encoding. Also, you can't have new value types
that use existing encodings.

### 2: Extensibility

As noted above, we have this problem of "value types with new encodings" and
"new encodings for existing value types."

Both of those are _theoretically_ possible.

1. New Encodings for Existing Value Types: A library might want to support new
   hardware for existing programs.
2. New Value Types Re-using Existing Encodings: A new conceptual value type that
   can never be intermixed with another value type, but behind the scenes it
   uses the same encoding.

The first would allow us a useful form of extensibility to support new hardware
without requiring direct modifications of the compiler. That's a somewhat rare
need, but then again, _any_ extension to this system should be a rare need.

I'm more skeptical of the second problem (new value types re-using existing
encodings). It prevents programs translating between values that are in fact
equivalent, which allows programmers to paint themselves into a corner and have
to write explicit conversion operations that are not actually logically
necessary at runtime. Some of those conversions we could detect and eliminate
when compiling, but I would _imagine_ it's possible for a developer to write a
conversion in such a way that we _couldn't_ tractably optimize it away.

More importantly, the second problem creates a whole system of typing somewhat
akin to traditional type systems. The intentional design of Define is that those
problems would be solved by global positions. Whatever we decide, we definitely
don't want to _bake into the language_ two different ways to express the same
logical intention. The whole value type system is intended to represent
primitives and abstract hardware operations only, not complex typing logic. That
logic is supposed to be through constraints or particle structure if it goes
beyond the actual physical representation or the actual fundamental _type_ of
symbol being represented. (Not the program's domain model of the type of symbol,
either, but the irreducible logical type of a primitive value.)

I'm willing to change my mind about that stance, though, if real programs show
us there is utility in this and we have some way to avoid the "two logical
models for the same concept" problem.

### 3: Conflicting Associations from Libraries

So let's say we do allow libraries to add new encodings and new value types,
which we should. (After all, why else have this system?) Now, our naming system
already guarantees there cannot be a _name_ conflict between existing
encodings/values and the library's encodings/values. But what about the
_associations_?

We somehow need to let libraries provide new associations between values and
encodings, either a new encoding to an existing value, or potentially a new
value to an existing encoding.

What happens when that creates a conflict that the compiler can't resolve, where
there are two encodings that the compiler could choose for the same value,
provided by different libraries?

### 4: Consistency

Let's say we do have a conflict, as described above. When we resolve that
conflict, who wins, the application that specified it? One of the libraries? If
we let anything "win" then that creates an inconsistency: the library when
compiled _by itself_ behaves a certain way, but when compiled into an
application, it behaves another way.

Ideally, the guarantees of Define would make that safe, because we would be
promising that the _logical_ behavior of the system is identical no matter what
encoding is chosen.

Also, there might be situations in which a programmer genuinely _does_ want to
change the encoding used across an entire program, or in a particular
compilation. For example, they might be sometimes compiling for a Google TPU and
want to change _all_ floats in the program to use the TPU's `bfloat` encoding,
but other times are compiling for a CPU and want to use IEEE 754 for that CPU,
regardless of what "preference" a library has for how to represent an encoding.

All of that said, it does _feel_ concerning that a library's actual runtime
behavior could change depending on who is consuming it. It also makes it harder
to ship pre-compiled Define libraries and have them behave the way that the
language expects. (We could say that that runtime behavior is past the
guarantees we make about the language, though, because now that's machine code
and not Define anymore, and _caveat emptor_ about what you do with dynamic
library loads or post-compilation linking. There's probably some reasonable
in-between stance, but we don't necessarily have to solve that right now, we
just have to understand whether we are barring the door on _ever_ solving that
problem, with our design.)

It's worth noting that this has always been a problem, in all compiled
languages. A library author could expect their library to be compiled with
particular compiler flags, but the application compiles it with different
compiler flags.

### 5: Avoiding Search

If we don't let values say what encodings are supported for that value, and we
have to discover the encoding, we must avoid having to _search_ for the encoding
within a project. Doing so would require arbitrarily searching for files in a
project. There's no way to know that files in a directory belong to a project.
You'd basically have to eagerly parse every `.dfn` file in any transitive
subdirectory just to compile one file, which is obviously stupid.

We also ideally want to avoid excessive "search" logic at runtime, even if we do
have all the encodings in memory, somehow. We can't make every value/encoding
association the compiler does into an `O(n)` operation.

### 6: Avoiding File Existence Checks

This is more minor, but as I've noted elsewhere, one of the performance problems
that compilers and build systems can get into is "I have to call `stat`
constantly to discover if files exist or not." It's not a major issue, but it is
a real one that I have encountered in real build systems. This is caused by a
design where "magic" happens if a file _happens_ to exist. Every time a
programmer adds one of these, they individually seem innocuous, until you have a
hundred of them that result in a million `stat` calls every time you invoke the
tool. What's worse is that usually these checks happen at startup for the tool,
so the cost is invoked on every single run regardless of what you're doing.

So if we do have some sort of configuration format, it must not rely on the
compiler discovering if a file exists or not. The intentional design of Define
is that we have _one_ of those checks (the check to see if a project config
exists) and we _fail the compiler_ if that one fails. There are no "optional
files that we discover automatically."

### 7: Eager Compilation of Encodings

Even if we do have a configuration file for associating things, there is still
one bad path we could go down. Let's imagine that our configuration file just
listed out all the files that contained encoding definitions, and that was it.
What actually happens in that situation, in the compiler?

Well, the compiler would have to actually load and parse every file in that
list, and it would have to do it every time you loaded that library, even if
your program never consumed any of those encodings. This would impose an
automatic startup time penalty on all compilations, which could become huge as
the number of value types and encodings grows.

One of the key intentions of the design of Define is that, as much as possible,
you only compile what you actually depend on. (We already violate this a bit by
allowing multiple definitions in a single file, but I didn't see a way around
that unless we went down the path of naming schemes, and naming schemes create
all the brittle problems of reserved words that we avoided via our naming design
and would have imposed a structure on codebases that didn't seem necessary. I'm
not looking to make this problem any worse.)

### 8: Duplication

If we did put things into a configuration file, how much do we put into the
configuration file? Do we duplicate essentially all of the information in an
encoding into the config file? If we did that, how do we ensure that what the
config says and what the value and encoding say still match? Does the developer
have to maintain the same thing in two places? What actually has to go in the
config file vs being in the code definition of the encoding?

## Solution

We introduce a new standard configuration that can be part of a Define project.
It goes into `.define/encodings/encodings.defcl`. It has the format:

```protocol-buffer-text-format
encodings: {
    value_encodings: [
        # We define both the value and the encoding, in this project.
        {
            value: "/number/natural"
            encoding: "/number/integer/unsigned"
        },
    ]
}
```

As you might infer from the above example, these use the global name short form,
meaning they only refer to names in the current project.

The same value or the same encoding can be specified multiple times, to provide
multiple different associations for a value or an encoding. However, it is an
error to specify the same value/encoding pair more than once.

The list must be sorted lexicographically by the value name.

What this does is declare that an encoding is _potentially_ available for a
value. The compiler _will_ have to load and parse every encoding available for a
value, but that's not as bad as having to load and parse every encoding in the
whole project. In the future, I may change my mind about this and put more
information into this configuration file so that the compiler always knows what
the right encoding to load is, though. Hopefully we make loading and parsing
Define code so fast that we don't have to worry too much about this.

### Banning Extensions

For now, we ban specifying a value or encoding from another project. That means
that these are banned:

```protocol-buffer-text-format
        # We have a value that uses an existing encoding from another project.
        {
            value: "/number/float"
            encoding: "mv:example.com:example:/number/float/ieee754"
        },
        # We have an encoding that represents an existing value.
        {
            value: "mv:example.com:example:/number/integer/signed"
            encoding: "/number/integer/twos_complement"
        },
```

In other words, `encoding` must always be a global name short form.

This means that a library can declare its own value types and encodings for
those value types, but cannot change the allowed encodings for an existing value
type.

However, it is very likely that we will allow them in the future, so this
proposal does discuss some limitations that would still have to be in place and
solutions for them when they arrive.

### Pure-Association Libraries Will Never Be Allowed

Even if we some day allow `value` or `encoding` to come from a sub-root, one of
`value` or `encoding` must be in the current project. We will never allow
configs that just define how values and encodings relate for other projects.

### Project Root Config

We add a new field in the project root config, like this:

```
    encodings: {
        has_encodings: TRUE
    }
```

`has_encodings` defaults to false.

The compiler only _looks_ for the new `encodings.defcl` if this value is `TRUE`
in the main project root config.

### Conflicts

A future proposal will create the ability to configure _compilation targets_,
which will allow for configuring how Define performs code generation for
particular target architectures, OSes, etc. Any conflict resolution system will
happen in _that_ configuration. That is, any conflicts that occur between
encodings are decided by the target configuration. However, the target
configuration in general should only attempt to resolve conflicts, not allow for
explicit specification of encodings, because explicit specifications override
the compiler's ability to optimize.

The goal here will be to allow libraries to compile according to their own
configurations to the degree possible, but the actual current project being
compiled will determine the overall behavior when there are conflicts.

Note that this plan means that Define's compiled representation when compiling a
library intended for consumption may need to be an IR that has not yet resolved
its encodings, rather than machine code or fully-resolved operations.

If the compiler does not have such a target config and there are conflicting
encodings that would be valid for a concrete value, the compiler will throw an
error at compile time.

Since we currently ban redefining encodings and values in libraries, this would
currently be a rare occurrence (a library author would have to, themselves,
create this conflict) but it could still happen, and the system is worth
recording for posterity if and when we do allow extensions.

Note that a library newly introducing such a conflict would be a
forward-compatibility issue and they would have to provide refactoring tools or
default choices for their consumers when making this change.

## A Real Program

```bash
# .define/project/config.defcl
project: {
    universe_name: "mv:example.com:numbers"
    encodings: {
        has_encodings: TRUE
    }
}
```

```bash
# .define/encodings/encodings.defcl
encodings: {
    value_encodings: [
        {
            value: "/number/natural"
            encoding: "/number/integer/unsigned"
        },
        {
            value: "/number/integer"
            encoding: "/number/integer/twos_complement"
        },
    ]
}
```

```define
define the potential value<mv:example.com:numbers:/number/natural>.

define the potential value<mv:example.com:numbers:/number/integer>.

define the constraint<mv:example.com:numbers:/bits/8to128> {
    its minimum value is 8.
    its maximum value is 128.
}

define the encoding<mv:example.com:numbers:/number/integer/unsigned> {
    define the encoding_option<bits> {
        it has the constraint</bits/8to128>.
    }
}

define the encoding<mv:example.com:numbers:/number/integer/twos_complement> {
    define the encoding_option<bits> {
        it has the constraint</bits/8to128>.
    }
}
```

## Why This is the Right Solution

Figuring out the details here was a lot of back and forth with GPT-6 Astra doing
research on existing languages, working through possible solutions, and
eventually me settling on this design.

The biggest compromise I'm making right now (a thing we don't normally do in
Define, so I may change my mind later) is requiring the parsing of every
encoding. Right now, encodings are very easy to represent just as a config file.
It would just be inconsistent with the rest of Define's model where you expect
to find the thing in a file. Since encodings are so tiny (at least for now) they
should be pretty fast to load and parse.

In general, this design seems to address all of the Problems. It avoids having
to `stat` for a config file, it provides us the flexibility to map values to
encodings however is necessary (both now and in the future), it avoids circular
references, and it avoids arbitrary searches or arbitrary eager loading.

### Banning Extensions

Originally when I drafted this proposal, I allowed "my encoding, their value."
However, when writing the Forward Compatibility section I realized I was
introducing a one-way door. Once I allowed libraries to provide new encodings
for existing value types, I could never walk back that decision. Also, there was
no actual mechanism proposed for the compiler to actually _implement_ those new
encodings, and I was wary of proposing a mechanism that had no actual
implementation (as one so often discovers one has done the wrong design during
implementation).

I did always ban "my value, their encoding." However, one of my concerns with
that ban (and our current one) is that people will just work around it by
copying out giant encoding and/or value definitions from one project into
another, including a giant set of converters, and just rename them. So we may
have to relent and allow extensibility in both directions. If we did that, we
would seek to find some other way to stop bad practices from occurring.

One thing we could do as enforcement is require that all encodings be
_semantically_ different from each other. However, encodings would have to get
more functionality than they currently have in order for that to be meaningful.

## Forward Compatibility

As far as I can tell, everything about this configuration format could easily be
converted into any other syntax or configuration format that we need. It is both
the most potentially flexible format, while also banning the specific _forms_ of
flexibility that would be hard to change our minds about in the future.

## Refactoring Existing Systems

This is not quite as capable as MLIR's association mechanisms, but otherwise is
more capable than the mechanisms that other languages have available today, and
so we should be able to refactor them into this language. Otherwise, there are
no existing Define systems that would have to be refactored here.
