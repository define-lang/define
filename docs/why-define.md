# Why Define?

Why write a new programming language? Especially now, when AI coding assistants
are getting so good at writing code?

Well, there are a _lot_ of problems that Define solves, and to my knowledge, no
other language solves _all_ of the same problems. But today, the most important
problem that it solves _is_ the problem of AI-assisted software development.

## The Core Problem of AI-Assisted Software Development

Today, we express our intentions to the AI assistant in our native human
language, usually English. However, the constant gap we experience as
programmers is the gap between the intention we expressed and the code that the
AI actually wrote. It often doesn't _quite_ do what we said, but why?

The core problem the AI assistant has is that cannot _know_ that the code that
it wrote matches the intention we expressed. And why is that? Because the **code
itself does not contain the full expression of our intent**. An AI agent cannot
read the code and _guarantee_ that it matches the intent you wrote in your
native language. The compiler cannot tell the agent "this code isn't doing what
you intended."

Interestingly enough, this is the same problem human teams have always had with
software development. Because the compiler can't _enforce_ that the code is
executing our _intentions_, it becomes hard to guarantee that our systems are
actually doing what we intend, especially as they grow beyond the complexity
that any one human being can comprehend. We try to solve this by writing
specifications that say how the system is supposed to behave, writing comments
in the code that say what our intentions are, and writing tests that check that
it has the behavior we expect. This has been a great help to us and to our AI
assistants, but what if there was a better solution, one that could guarantee
_in the code itself_ that the system was behaving as you intended?

Other languages have attempted to solve the problem of intent, and some have
done pretty well, but none have done it and _also_ solved all the other problems
that Define solves---all of which turn out to be very important for both humans
and AI doing software development, as I will explain as we go through this.

## The Trade-Offs

Just like in all languages, there are trade-offs that we have made.

### Verbosity

One of the first ones is that Define is built around this principle:

**You can get every other property you want in a programming language if you
sacrifice _brevity_.**

Define is very, _very_ verbose. But here's the good news: mostly, I don't expect
you to have to type it. I do expect human beings to have to _read_ it, though,
and once you get used to the concepts and you have some decent syntax
highlighting in your editor, it's quite readable. Define also enables editors to
do some tricks that would be very hard in other languages, if they want to make
it even more readable.

### Define is Very Different

Define is a wildly different language than other programming languages that
exist today. It is in fact a new _type_ of programming language that is not a
functional language nor an object oriented language.

The good news so far is that it seems fairly intuitive for AI assistants to
write it (with a few hints) and then the compiler can help them along much more
than it can in most other languages.

## The Guarantees of Define

So how do we do all of this? Well, let's walk through the guarantees that Define
makes, and we will see how we get all the properties we want.

### Perfect Forward Compatibility

In programming, traditionally we talk a lot about "backward compatibility" for
code itself, which is the idea that there are some things in your code you can't
change, because it would break other parts of the code that depend on you. You
write a library, ship it out to the world, and then you're sort of stuck with
the API that you designed for that library, because all the consumers of your
library now depend on that API never changing.

Define attempts to solve this problem a different way. What if you could break
your library's API ten times a day, and all of its consumers would be
automatically changed to use the new API format when they upgraded to the new
version of your library?

Even crazier: what if the programming language's _syntax_ changed, and you could
still upgrade to the new version of the programming language with no effort on
your part, because your code was automatically refactored when you upgraded to
the new language version?

Define attempts to guarantee this through a concept we call "forward
compatibility." We enable this in two ways:

1. Every aspect of Define's syntax and semantics has been designed on principles
   that allow us to change our mind about nearly all of it in the future.
2. Define provides a system that enables deterministic automated refactoring of
   any program, in a form that you can ship with your library and which will be
   automatically applied to a codebase when it upgrades to using a new version
   of your library (with some security controls to help prevent malicious
   refactorings).

Enabling this requires another property, though, which is very powerful in its
own right.

### Near-Perfect Static Analysis

I have spent a lot of my career working on or interested in static
analysis---the ability for an automated tool to look at code as written and know
how it will behave without having to run it. Static analysis is the most
powerful tool we have today for guaranteeing that programs have certain
properties, including security, software design requirements, etc. However, its
power is very limited in almost all programming languages today, because they do
not contain sufficient information for the static analyzer to be able to check
many properties of the language. Thus, we can only use it in limited
circumstances, and when we do use it, a lot of checks have "false
positives"---times when the tool tells you there's an error when really there is
not.

Define, on the other hand, guarantees that the compiler can know nearly
everything about the potential behavior of a program _at compile time_. This
means that all other tooling around Define can do near-perfect static analysis
of Define programs to determine any property they want to know about the
language.

The only reason we have to say "near-perfect" is that there are some situations
where you can prove that static analysis is impossible. So truly "perfect"
static analysis is impossible. However, many of the traditionally difficult
situations you can actually solve quite well, provided the language itself
fundamentally enables it, to the point where essentially all properties of a
program that a programmer actually cares about can be validated _at compile
time_.

When we make this guarantee, it turns out that we also guarantee perfect,
required expression of intent. (Even when we can't do perfect static analysis,
we still require a perfect expression of intent so the compiler can keep
running, as you will see as you dive into the language.)

In other languages, even _trying_ to guarantee this would require extremely
complex whole-program analysis that can grow in computational complexity to the
point that it's impossible for any real computer to solve the problem. Define,
however, is designed for _modular_ analysis, such that the compiler rarely ever
encounters a situation where analysis would take super-linear time.

### Theoretically Perfect Optimization

The trouble that compilers have with optimizing code is that they often cannot
determine the intent of a program. When you write a loop that loops through an
array in order, did you really _need_ it to be in order, or could the
compiler/CPU have parallelized it? Modern compilers do have tricks they can do
to figure some of this out, but other optimizations are severely limited because
the compiler can't figure out what you intended.

If we guarantee near-perfect static analysis and perfect expression of intent,
then _theoretically_ the compiler can perform the maximum possible optimization.

Now, in reality, this requires us as the compiler designers to be pretty clever,
and so this will improve over time. Plus, there are real trade-offs to be made
in optimization, such as binary size vs memory usage vs computation speed.
However, my belief is that with perfect expression of intent in the language, we
can still get further than any other compiler has ever gotten before.

### Automatic Concurrency

The Define compiler can figure out when it is safe to run multiple parts of the
code in parallel and can choose to do so automatically. Developers do not have
to explicitly manage concurrency, but rather express an intent for multiple
things to happen and the compiler then resolves what actually occurs.

As time goes on, we will provide more and more powerful mechanisms for
concurrency, and the compiler will get better and better at managing it
automatically.

### Concurrency Conflict Detection

One of the most difficult parts of managing concurrency in programming languages
is dealing with race conditions, deadlocks, and other bugs that occur as a
result of parallel computation.

Define automatically detects "paradoxes," which are situations where two parts
of the code running in parallel _could_ conflict, and requires the programmer to
resolve them before the program will compile. There are still some aspects of
parallelism that programmers must manage (especially if you are dealing with
resources outside of the program), but most of the traditional problems simply
vanish.

### Reliable Destruction and Memory Management

One of the great problems of programming is managing memory, and especially
dealing with data that the program no longer needs. There are three ways that
programming languages traditionally deal with this:

1. **Explicit**: Requiring the programmer to explicitly free memory that is no
   longer needed.
2. **Automatic Reference Counting (ARC)**: Making the program count the number
   of references to data in the program at runtime and free the memory
   automatically when that data is no longer needed.
3. **Garbage Collection**: Count references to an object at runtime and then
   regularly clean up objects that have no references.

All of these have downsides. Explicit memory management is a constant source of
memory leaks and security bugs. Garbage collection involves "pausing" programs
to clean up objects that are no longer needed. ARC is one of the best modern
options, but it has runtime overhead for counting references, and it has trouble
dealing with circular references (data structures that reference themselves).

Define has a different solution that lets the compiler track the lifetime of
every single piece of data in the program and deterministically know, at compile
time, when it will be destroyed. Because it also knows the behavior of the whole
rest of the program, the compiler can theoretically determine the most optimal
way to execute destruction on the programmer's behalf.

However, when explicit destruction is desired, Define enables explicit
destruction of data on demand, with the compiler guaranteeing that no part of
the program will ever attempt to access uninitialized memory or destroyed data.

All of this has one additional benefit that comes along with it, too:
"destructors" (code that runs automatically before data is destroyed) are much
more reliable and much more powerful in Define than they are in any other
programming language.

### Granular Dependencies

In most programs, you express dependencies in terms of classes or files that
depend on each other. What this often leads to is one part of the code depending
on a lot of things it doesn't actually need, just to get one tiny piece of some
other class or library.

Define, on the other hand, knows explicitly what data in a program depends on
what other data, what functions depend on what other functions, and how data and
functions depend on each other. It expresses dependencies in code _only_ in this
way. There are a few small situations where you will pull in small pieces that
you don't actually use in your program, but those are very minor and rare
compared to how this works in other languages.

This means that the Define compiler can choose to only put code into the
compiled program that your program actually _needs_. No more binaries bloated
with extensive functions and code that you don't need.

It also means that Define can deterministically tell you when there is "dead
code" in your codebase, so you can delete it.

### Dramatically Improved Package Management and Supply-Chain Security

In real codebases and in large companies doing software development, one of the
hardest problems is "package management" or "dependency management": dealing
with all the libraries you depend on in your codebase, or all the tools you use
that are written in that language. I have done more work in dependency/package
management at large companies than most people in the world, and I have
personally experienced almost every form of pain in this area that you can
imagine.

Define has an approach to package management that I believe is significantly
more robust than any other language that exists today. The language inherently
acknowledges that multiple, uncoordinated groups of people will be working on
different codebases that will all have to interact. It even provides mechanisms
for companies to have internal namespaces and standard package management
infrastructure inside of their own companies, separate from (but still
compatible with) the open-source ecosystem.

Define also cares about supply-chain security---the idea that bad actors can
provide you dangerous dependencies---inherently in its design and in the design
of its package ecosystem. Though perfect security is impossible, Define's
theoretical guarantees of supply-chain security should exceed the guarantees
that any other language provides today.

### Granular Access Controls

In most programming languages, the only restrictions you can put on functions or
classes are to say:

- This can be accessed by anybody (public)
- This can only be accessed by code in this file / class (private)
- This can only be accessed by code in the same package (internal)

I cannot count the number of times I have wanted to say something like, "here is
a list of classes in my codebase that are allowed to call this function" or
"only these other codebases can depend on my library."

Define goes even further than that, and allows you to express fully granular
access controls that are enforced at compile time, allowing you to express
exactly how different parts of the program are allowed to interact. You can even
express how specific, named codebases outside of your own codebase are allowed
to interact with any part of your codebase.

### Freedom to Choose Functional, Object-Oriented, or Whatever

As a language, Define can express the concepts of functional programming,
object-oriented programming, and probably other paradigms as well. Unlike other
languages, it has no preference for which paradigm you choose. It even enables
seamless interaction between object-oriented code and functional code.

### Compiling Down to Other Languages

Define can represent all the compiler guarantees that most other languages
provide today. As a result, it can actually represent the programming _idioms_
of other languages, and through deterministic static analysis, we can detect
when those idioms exist in Define code.

Thus, not only can Define compile down to other programming languages, in many
cases it can actually compile down to _idiomatic code_ in the language (code
written the way you would natively want to write it in that language). Also, if
desired, you can use Define's optimizations to write out optimized versions or
versions with dead code removed, as you wish.

### Incremental Rewrites

One of the greatest challenges of adopting a new programming language is that
you have to rewrite your codebase all at once, in a "big bang" that can take
months or years of effort. It's very hard to justify this when you're getting
some marginal benefit for moving to a new language.

Define, on the other hand, attempts to enable incremental rewrites from Define
into other languages. Since you can compile Define down to idiomatic code in
another language, you can have some parts of a codebase be generated by Define
while others are still in the previous programming language.

### Universal Translation Layer

Theoretically, if we have incremental rewrites and the ability to compile down
to multiple programming languages, Define can act as a sort of "universal
translation layer" between programs. In fact, it would even be possible to
analyze patterns in existing languages, convert those patterns into Define with
some level of automation, and then compile Define back down to a different
programming language. Because other languages don't guarantee perfect static
analysis, there will always be some situations that require manual human
intervention, but most concepts that exist in other languages should be
translatable easily into Define.

## Summary

What I've listed above are only the benefits I have discovered so far as I am
developing Define. There are probably more that will come in the future, but for
now, I hope you can see both (a) why a new programming language could be
incredibly valuable to the world right now and (b) how, if we actually
accomplish all of the above (which I am pretty confident we can) we could
skyrocket the capabilities of both humans and AI agents to productively write,
maintain, and manage software systems.
