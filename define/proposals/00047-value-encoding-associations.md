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
single encoding, which is the whole problem the whole system of value qualities
is trying to avoid or (b) allowing multiple potential encodings for a value and
then having to figure out at compile time which one applies. (a) is
unacceptable. (b) might be acceptable, though, provided there's a way for the
compiler to deterministically make that choice. Of course, (b) would still have
the problem specified in the above paragraph.

In the other direction, if encodings say what values they support, then you
_can't_ discover them automatically, because normally the programmer will just
specify the value quality, not the encoding. Also, you can't have new value
qualities that use existing encodings.

### 2: Avoiding Search

If we don't let values say what encodings are supported for that value, and we
have to discover the encoding, we must avoid having to _search_ for the encoding
within a project. Doing so would require arbitrarily searching for files in a
project. There's no way to know that files in a directory belong to a project.
You'd basically have to eagerly parse every `.dfn` file in any transitive
subdirectory just to compile one file, which is obviously stupid.

We also ideally want to avoid excessive "search" logic at runtime, even if we do
have all the encodings in memory, somehow. We can't make every value/encoding
association the compiler does into an `O(n)` operation.

### 3: Avoiding File Existence Checks

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

### 4: Eager Compilation of Encodings

Even if we do have a configuration file for associating things, there is still
one bad path we could go down. Let's imagine that our configuration file just
listed out all the files that contained encoding definitions, and that was it.
What actually happens in that situation, in the compiler?

Well, the compiler would have to actually load and parse every file in that
list, and it would have to do it every time you loaded that library, even if
your program never consumed any of those encodings. This would impose an
automatic startup time penalty on all compilations, which could become huge as
the number of value qualities and encodings grows.

One of the key intentions of the design of Define is that, as much as possible,
you only compile what you actually depend on. (We already violate this a bit by
allowing multiple definitions in a single file, but I didn't see a way around
that unless we went down the path of naming schemes, and naming schemes create
all the brittle problems of reserved words that we avoided via our naming design
and would have imposed a structure on codebases that didn't seem necessary. I'm
not looking to make this problem any worse.)

### 5: Duplication

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

As you might infer from the above example, these use the global name short form
when referring to names in the current project.

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

### Project Root Config

We add a new field in the project root config, like this:

```
    associations: {
        has_encodings: TRUE
    }
```

`has_encodings` defaults to false.

The compiler only _looks_ for a project's `encodings.defcl` if this value is
`TRUE` in that project's root config.

## A Real Program

```bash
# .define/project/config.defcl
project: {
    universe_name: "mv:example.com:numbers"
    associations: {
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

## Forward Compatibility

As far as I can tell, everything about this configuration format could easily be
converted into any other syntax or configuration format that we need.

## Refactoring Existing Systems

This is not quite as capable as MLIR's association mechanisms, but otherwise is
more capable than the mechanisms that other languages have available today, and
so we should be able to refactor them into this language. Otherwise, there are
no existing Define systems that would have to be refactored here.
