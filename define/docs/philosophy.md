# The Philosophy of Define

Max Kanat-Alexander, January 2016

## Programming is Applied Epistemology (the study of how knowledge is known)

Most programming languages are made primarily by induction and minimally by
deduction. In particular, they start with the way that a machine works, or its
assembly language. Then they attempt to abstract that away or accommodate the
architecture of the machine in some fashion. Then higher-level languages are
built on top of that. Most languages are built on or inspired by previous
languages, so the _nature of the machine they are running on_ fundamentally
“infects” their design. A simple example of this historical transition or
influence is Machine Language -> Assembly -> C -> C++ -> Java. Plus there’s a
branch in there where Smalltalk affects both C++ and Java--that’s partially
where the deduction side comes in, because Smalltalk is closer to being a
philosophical language that was deduced from general principles than other
languages are, perhaps. (The same could perhaps be said for Lisp, perhaps.) I
honestly haven’t studied the history of those two languages in great depth at
the moment, but that’s the impression that I have so far.

In essence, the computing industry has taken a Turing machine (or really, a Von
Neumann machine) and then made a language to fit the machine, rather than
_fundamentally starting_ with the concept of a language to fit the programmer.

Part of the philosophy of define is that we shouldn’t care how the machine works
underneath us. Obviously when we are implementing the compiler we care, but not
when we are designing the syntax, APIs, etc--the “language” parts that the
programmer interacts with.

The intention of define is to be a language that is designed from first
principles. These principles are fundamentally the principles of epistemology,
because the first principle of define is:

Programming is not math, it is applied epistemology.

So traditional mathematical constructs in Computer Science, in terms of language
design, are not useful to us. We can definitely use algorithms in our
implementations and we definitely care about programmers being able to do math
using define. We want to understand and learn the lessons that past language
designers have learned and understand, though we don’t take everything there as
dogma. What we don’t care about is adhering to an arbitrary mathematical
standard for what a language or a computer is supposed to be, or evolving the
language from mathematical principles. We care about the program itself, the
programmer, and their ability to understand and maintain their software. If
Computer Science constructs help us with this, great! If they don’t, we don’t
have to adhere to them or to any tradition.

This applies to define itself. For example, one of the rules for implementing
new features in define is that you have to prove that your new feature could be
automatically refactored to some other syntax in the future in a completely
deterministic fashion. That is, we want to be able to change the language, and
we will be shipping a tool that can convert a define program from any previous
version of the language to any new version of the language.

## Everything is Expressed in the Language

Some people think that a Turing Machine is the holy source of all computing.
This isn’t true. There are numerous models that you could use to describe a
computer. We don’t care about any of them. We don’t care about the computer. We
care about the language, the concept that the person is describing.

Surely, some people will say that this is foolish, because the performance
characteristics of a programming language depend heavily on the language
adhering to certain aspects of how a computer works. I think that _that_ concept
is foolish. The place to optimize these things is in the compiler, not in the
language. We _do_ want a language that compiles or interprets quickly. None of
define’s goals are fundamentally in conflict with that, though. In fact, a
well-designed programming language should be able to express things so well that
near-perfect optimization becomes possible.

The reason that this is possible with define is that a core principle of define
is that _everything_ is expressed in the _language, in syntax_. Comments should
almost never be necessary, except on the very core fundamental components of the
system that are designed by the language designers. Anything that is expressed
in a comment that has to do with the _program itself_ should instead be part of
the syntax of the program. All constraints, all contracts, all limits should be
expressed in syntax. Comments like “Bob will delete this in March” might be
okay, because they are about things that are entirely outside of the program.
But even that might want to be in syntax so that it can be _automatically_
deleted in March by some automated tool. This enables not just automated
analysis, but also very thorough optimization. Our philosophy is that perfect
optimization is enabled by perfect information about the program, its purpose,
its behavior, the developer’s intentions, etc.

Ideally, contracts should be so completely specified that it should be possible
to swap out any two pieces of code for each other that implement identical
contracts without the developer having to inspect the code of either piece. This
enables the define “marketplace” where different implementations of the same
concept can “compete” and maybe even be chosen automatically by the compiler
based on the developer simply specifying what they want in code and the compiler
picking the ideal implementation based on the developer’s criteria. (Of course,
there could be security concerns there. One way to get around that would be to
have some sort of automated tool that assures the behavior of a piece of code is
indeed completely specified so there are no surprises.)

## Perfect Refactoring and Exceptional Collaboration

As much as possible, we are going for a perfect ability to do automated
refactoring in the language. I suspect that this is accomplished by making it as
easy as possible to verify behavior in the language (that is, formal
verification, perhaps).

We care more about being able to write large applications with many
collaborators than we care about being able to write rapid scripts. It will
probably still be possible (and maybe even desirable) to write scripts in
define, but it’s not our primary focus.

## The Two Universes of a Program

One concept that drives define is that a program is essentially a universe. It
has its own set of laws, its own matter, its own space (differentiation between
things), its own energy (interchanges between things), and its own rate of
change or persistence (time). There may actually be _two_ universes to all
computer programs:

1. The conceptual universe, where the “ideas” of the program exist. For example,
   if you have a video game that involves a dog catching a frisbee, “a dog” and
   “a frisbee” are abstract concepts in that universe. So is “catching.”

2. The physical universe, where the person using the program interacts with it.
   Using our above example, there is a _rendering_ of a dog on a _actual
   physical screen_\--the pixels that light up, the commands that get sent to
   the video card, etc. The dog running and catching _means_ something in this
   universe that is _not_ purely conceptual--it means that image of the dog will
   be animated, it will respond to the user’s input, etc.

## Define is a Logical Superset of All Languages

If we do our job well, it should be possible to implement all other valid
programming paradigms _using_ define, should one wish to. That is, one could
write a functional system, an object-oriented system, etc. should one want to.
However, I suspect that that will be perceived as foolish by define developers,
as one would be adding unnecessary concepts into the universe. That is, “a
function” is not a concept that needs to exist in a universe where the only
thing that’s happening is a dog is chasing a frisbee.

The advantage of this “epistemological completeness” (the ability to implement
all other paradigms because we are theoretically more fundamental, on a
philosophical level, than they are) is that we can describe existing programs
using define. One concept of define is that it should be possible to rewrite
other languages into define incrementally--something that, to my knowledge, has
never been accomplished well by a programming language and which actually makes
possible transitioning other programs into define and making define a primary
language in use in the software industry. These incremental rewrites would add
value as they go. They would essentially start specifying parts of the existing
program more fully than they are currently specified. That would start to get
static analysis benefits for the program: better correctness checking, data flow
analysis, simpler testing, etc. Now, there are already formal verification
languages that people can use to annotate their systems or otherwise describe
their systems. The disadvantage of using those is that all you get out of them
is a proof, which is usually more work than a team of programmers wants to do
just to get that result. (It’s usually a _lot_ of work, from my current
understanding of the process.) I’m not knocking the ability to formally prove a
program--that’s great. I’m saying that most teams aren’t going to go through the
effort to write way more code in a second language _on top of_ their current
program _just_ to get formal verification. However, with define you’re actually
incrementally rewriting into another language--a whole different kind of benefit
that is tangible, concrete, and more demonstrably valuable to developers.

Of course, this means that define will have to have excellent tooling,
documentation, support, community, and all those things so that it’s an
attractive target for developers to rewrite into. But since rewrites can be
incremental, the amount of tooling, documentation, etc. required to get people
to switch should be (theoretically) lower than it is in other languages. Still,
we care about developers. They should in general be able to work in the way that
they want. They should be able to use the editor that they want, the types of
command lines that they want, whatever, without us getting into too huge a
proliferation of “more than one way to do it” maintained by the core team. There
should be some constraints, primarily the design of the language itself. But the
tools surrounding the language should cater to the developer’s desires and needs
(without going overboard with scope creep that is harder to maintain than it is
worth having).

## Preventing Complexity

One of the purposes of define is to make it difficult to create complexity that
is hard to maintain. Primarily, we enable this by making it difficult to lie.
Lies are a primary source (or perhaps _the_ primary source) of complexity. (For
example, an object says that it is a dog but actually it is sometimes a horse
and sometimes a dog. There are many other examples of many different types.) It
will likely still be _possible_ to lie in define--it will just be _difficult_.
It should also be _obvious_. That is, complex things should look obviously bad.
It should be easy to spot “bad” code and easy to fix it.
