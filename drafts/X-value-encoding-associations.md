### 4: Association with Values and Encoding Operations

How does the compiler know which encoding to use for which value? Does it have
to search through every possible encoding and guess? That's not computationally
tractable to do for every single value declaration in a program. Do we need some
sort of separate configuration file? Do we have to make the programmer
explicitly specify which encoding will be used somehow? (No, because that would
bring us back to the whole problem we are trying to solve in the first place.)

As part of this, we have to avoid circular dependencies. Do values say what
their encodings are, or do encodings say what values they support, or something
else entirely? What if you have a library that has a new value type that it
wants to use an existing encoding? What if you want to ship a library that
provides a new encoding for an existing value?

Both of those are theoretically possible. A library might want to support new
hardware for existing programs. A library also might want to have a new
conceptual value type that can never be intermixed with another value type, but
behind the scenes it uses the same encoding.

I'm more skeptical of the latter problem (new value types using existing
encodings) though, because it prevents programs translating between values that
are in fact equivalent, and allows programmers to paint themselves into a corner
and have to have write explicit conversion operations that could be wasteful at
runtime.

### 5: Discovery of Association

Another key problem of association is the actual _discovery_ that an encoding
and an operation are related. The Define compiler normally only loads files when
they are referenced, but value definitions don't reference encodings (and
shouldn't, because values are logically independent of encodings). So how does
the compiler know an encoding is _available_?

### 6: Association Conflicts
