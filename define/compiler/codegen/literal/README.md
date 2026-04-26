# The Define Literal Transpiler

This directory contains the code that we use to do literal transpilation of
Define into other languages.

It is not recommended to use this for any actually-shipped binary. It is wildly
slow, memory inefficient, includes extensive dead code (such as checks that will
never be false as long as the compiler actually verified the code correctly), is
hard to read, etc.

It exists for a few reasons:

1. To let us test the compiler itself. It outputs code that "looks" exactly like
   Define's semantics as written in Define. When we want to understand how code
   generation is working for our syntactical and semantic constructs, the
   literal codegen is a great way to do that.
2. It's the easiest code generation system to write. It takes just a few days to
   create a literal transpiler into almost any other language.
3. It's educational for us in understanding how to write more optimized codegen.
   We start off by writing the literal transpiler and then we can work from
   there to understand how we would do something more efficient in a language.
4. It can be educational for a person learning Define who is familiar only with
   some other language. They can see what Define "looks like" in the language
   they are more familiar with.
5. It can be helpful for debugging code. For example, you might have a debugging
   tool available for some language that you don't have for Define, but you want
   to use it to look at something Define-like. Or there's a compiler bug and we
   want to see it written out as code in another language to understand the bug.
   Or you are making a library that interacts with some other code somewhere
   else and you want to see what's wrong with your Define implementation.

Note also that there is a literal runtime in define/runtime/. Literal
transpilations require this runtime library in order to run.

In general, we make no guarantees about the stability of the runtime library.
Literal transpilation is a debugging and education tool, not a system for
shipping code that may evolve over time.
