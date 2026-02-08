# Principles for Define

These are general rules we try to follow that help guide our decisions about
language design. If something is instead an unbreakable rule that must always be
true, it goes into [requirements.md] instead.

## We Only Solve Problems That Exist

Don't design solutions for problems you imagine might occur. Only design
solutions for problems you have actually encountered in the physical universe.
Otherwise, you risk designing the wrong solution for the imaginary problem that
doesn't work well for the real problem when you encounter it.

## Define Should Read Intuitively

Lines of code in define should feel something like English sentences. They don't
need to actually be grammatical English sentences, but they should feel somewhat
intuitive to a reader who is not deeply familiar with programming.

To be clear, define is a programming language and it does require expertise to
really understand what it's doing. We aren't aiming to dumb down the language so
that non-programmers can write programs in it. That's not the purpose of the
language. This principle of readable lines is just a design principle that we
use to think about how we structure keywords and the language's grammar.

## There Is One Right Way

As much as possible, we should strive for there to be only one correct way to
write the language, even down to the style.

Total standardization enables a lot of very powerful abilities with a
programming language, because you can much more easily reason about how the code
is structured, have simpler compilers, easier automated refactoring, etc.

## Previous Languages Do Not Justify Decisions

There are a lot of great lessons we can and should take from previous
programming languages. We should not throw away decades of lessons we have
learned in programming language design. However, one of the goals of define is
to create an ideal programming language regardless of how any other programming
language has worked in the past. So, although we can be _informed_ by past
programming languages, saying "this is how other programming languages have
worked" or "this is what programmers will be familiar with from other
programming languages" is not a sufficient justification _by itself_ for any
language design decision.

We realize that this might make define less popular, because it's different from
how other languages work. It's already so different from how other languages
work that I don't think that's we're adding significantly more barriers by
making different decisions than past languages have made.

## Verbosity Is Okay

Typing is not the hard part of programming. Define is intentionally very verbose
as a language, for a few reasons:

- It helps us guarantee forward compatibility. It is unlikely the string "has a
  Number named start" will conflict with future syntax we want to create,
  compared to the syntax "Number start." (That syntax would greatly limit our
  future choices for how we modify the language.)
- It makes intent clearer to readers.
- It makes the language naturally interpretable by an AI coding assistant.

## Define is Explicit

The language should not make choices for the programmer. The programmer should
always express their intention.

In some languages, when there is a choice of how to behave, the language will
just silently pick an option. For example, in Python, you can have multiple
inheritance, like this:

```Python
class SuperClassOne:
  def cool_function(self):
    print("I'm cool!")

class SuperClassTwo:
  def cool_function(self):
    print("I am also cool!")

class MyClass(SuperClassOne, SuperClassTwo):
  def cool_function(self):
    super().cool_function()
```

That will print `I'm cool!` followed by `I am also cool!`. If the superclasses
also have superclasses themselves that define `cool_function`, the logic gets
even more complex. Python just makes this decision for the programmer. In
Define, if we encountered a situation like that, we would require the programmer
to explicitly indicate what order the superclass functions should run in.

## Define Can Write Bad Programs

One of the goals of Define is to be able to represent any program with any sort
of structure, so that you can incrementally translate existing programs into
Define. That is, we can't specify things like "you must always name variables
lowercase," because other programming languages don't have that constraint, and
we need to be able to represent a program from those programming languages in
Define.

Define isn't just a mechanism to model universes, it's a mechanism to model _any
other model_ of a universe. If you want to create a crazy, illogical universe in
Define, you should be able to.

We should strive to help the programmer write logical universes that are
well-structured, but we should not _totally prevent_ them from creating crazy
universes. We _should_ make it clear that the universe is crazy, though.

For example, imagine that somebody wants to translate this snippet of Python
into Define:

```Python
def do_crazy_stuff(foo, bar, baz):
  qux = foo + bar
  my_value = qux * baz
  return my_value
```

That looks straightforward, but really it's sort of crazy because of the lack of
types. That could take any value for any of those arguments, including `None`,
and could return any value, including `None`. What `+` and `*` mean there would
be different depending on what is inside of `foo`, `bar`, and `baz`.

In Define, you can't do addition and multiplication on dimension points with no
qualities. So either you would have to create a quality called something like
`NumberOrString` (which would be sort of crazy, but still be way better than the
code above), or you would have to define a very complex machine to execute that
code. Or, you could choose to just make it saner while you are translating it,
and specify that all those values have to be integers.

## Provide Clear Errors

One of the most important qualities of any developer tool is that it provides
extremely clear, actionable error messages. Define should strive to always
provide errors that tell the developer exactly what is wrong, with sufficient
information that they can fix it. If we know or suspect what the fix is, we
should say it. If there is longer documentation about the error somewhere, we
should link to it.
