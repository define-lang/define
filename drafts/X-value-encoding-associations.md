# Define Language Proposal 47: Value Encoding Associations

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** September 18, 2026
- **Date Finalized:**

## Problems

The compiler needs to somehow know which encoding to use for which value, and
which encoding operations are available to be called for those encodings.

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
to have write explicit conversion operations that are not actually logically
necessary at runtime. Some of those conversions we could detect and eliminate
when compiling, but I would _imagine_ it's possible for a developer to write a
conversion in such a way that we _couldn't_ tractably optimize it away.

More importantly, the second problem creates a whole system of typing somewhat
akin to traditional type systems. The intentional design of Define is that those
problems would be solved by global positions. Whatever we decide, we definitely
don't want to _bake into the language_ two different ways to express the same
logical intention. Whe whole walue type system is intended to represent
primitives and abstract hardware operations only, not complex typing logic. That
logic is supposed to be through constraints or particle structure if it goes
beyond the actual physical representation or the actual fundamental _type_ of
symbol being represented. (Not the program's domain model of the type of
syymbol, either, but the irreducible logical type of a primitive value.)

I'm willing to change my mind about that stance, though, if real programs show
us there is utility in this and we have some way to avoid the "two logical
models for the same concept" problem.

### 3: Conficting Associations from Libraries

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

### 5: Avoiding Search

If we don't let values say what encodings are supported for that value, and we
have to discover the encoding, we must avoid having to _search_ for the encoding
within a project. Doing so would require arbitarily searching for files in a
project. There's no way to know that files in a directory belong to a project.
You'd basically have to eagerly parse every `.dfn` file in any transitive
subdirectory just to compile one file, which is obviously stupid.

We also ideally want to avoid excessive "search" logic at runtime, even if we do
have all the encodings in memory, somwhow. We can't make every value/encoding
assocation the compiler does into an `O(n)` operation.

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
