# The Conceptual Basis of Define

This document describes the concepts that Define is based around. It is senior
to the [spec](spec.md)---it guides how we design the spec.

## A Program is a Universe

A universe is defined as "a whole system of created things."

A computer is a _universe simulator_.

A program is a universe that exists and is operating on that simulator.

The code of the program describes that universe.

A programming language exists to define universes.

## The Basic Components of a Universe

Warning: we are about to get very abstract, but I will try to make it more
concrete shortly after that.

Our concepts of a universe are based around
[The Factors](https://www.scientologyreligion.org/background-and-beliefs/the-factors.html)
because they are the only form of epistemology I am familiar with that is
sufficient to fully describe all universes, their creation, and how they
operate. However, our description here is a description of the concepts that
exist in Define, and should not be taken as an interpretation of The Factors,
but rather just a description of how we think about universes in Define. I just
wanted to credit the source that inspired these ideas.

A universe is composed of essentially two things: view points and dimension
points.

A **dimension point** is a creation.

A **view point** is a creator and knower of dimension points. It is capable of
creating dimension points, knowing dimension points exist (perceiving them),
differentiating dimension points from each other (knowing that they are separate
or different from each other), considering that dimension points have certain
qualities, knowing the qualities of dimension points, and destroying their own
dimension points (actually, ceasing to continuously create that dimension
point).

A dimension point has whatever qualities the view point considers it to have at
the moment. It has a defined relationship to other dimension points (defined by
some view point).

A concrete example of this in real life is that you are reading this text right
now. You are a viewpoint, and the machine you are reading this text on is a
dimension point. You can change the machine's position (one of its qualities).
You could turn it on or off (another quality). You can tell the difference
between this machine and another machine (you have the ability to differentiate
between dimension points).

Note that a view point can know (perceive) dimension points created by other
view points. You probably didn't create the machine you're reading this on, but
you know it exists.

This helps us clarify what a universe is: it's all the dimension points that a
view point considers could possibly interact with each other. You can experience
a difference between two universes right now. If you look at the machine you are
reading this on, you can imagine the machine changing in some way. However, your
imagination (a different universe) did not cause a change to occur in the
physical universe, because your imagination and the physical universe were not
_capable_ of interacting. They are two separate universes.

Okay, so this helps us understand what "a universe" is and its fundamental
components. But how does this help us design a programming language? Well, there
are some additional concepts we need. (We'll get there, I promise!)

## Qualities

I mentioned above that a view point can consider a dimension point to have
certain qualities. Right now in the physical universe you can look around you
and see all sorts of objects that have different qualities: color, shape,
weight, etc. They also have qualities that only you or some small group know
about: owned by you, liked by you, planned to be thrown away, etc.

Some of the things around you might also be machines: objects that _do_
something when interacted with. A sink is a machine: I turn the faucet and water
comes out. I didn't go manually pull the water from its source and make it come
here. I just took one small action and some other action occurred. So "this
performs some action when interacted with" is also a quality that a dimension
point can have.

### Qualities in Programming

This is almost the entire basis of a computer program. A computer program is
mostly a description of qualities that dimension points have, including a
description of how they behave when certain other things happen.

For example, let's say I write out the following in a traditional programming
language:

```Python
x = 2
y = 5
z = x + y
```

We have said that dimension point `x` now has the quality of being the number 2,
dimension point `y` now has the quality of being the number 5, and after we do
addition, `z` has the quality of being the number 7. But what is "addition?"
Well, in the universe of that program, numbers have a quality called "addition"
where if you give the number (`2` in this case) a special dimension point (the
`+` symbol) then it will combine with a second dimension point (`5`) following
particular rules.

There are actually multiple ways we could define that quality, by the way. We
could also say that it's the `+` dimension point that has the quality, not the
numbers. We could say "all dimension points in this universe can be added
together" or "all dimension points in this part of the code can be added
together." There are many ways to accomplish the same result. Some are simpler
and easier to reason about, but all of them _could_ happen.

## Space

A view point needs some universal mechanism to differentiate all dimension
points from each other. In the physical universe, this mechanism is _space_. You
say "dimension point 1 has this location, and dimension point 2 has a different
location." The view point can change the position of the dimension points, and
the view point can change its own position in relation to the dimension points.

Think of eight points that make up the eight corners of a cube. Those eight
points have a very particular relationship to each other ---that's why we see a
cube. You could move those points around to change how the cube looks to you.
You could move those points further away from you or closer to you. You could
move yourself so you're looking at different parts of the cube. The cube takes
up space, and there's space between you and the cube. You can tell that each
corner of the cube is a different point; they're not all the same point. That's
space.

Two dimension points cannot occupy the same space. That's a fundamental rule.

Dimension points have many other qualities that _assist_ us in differentiating
them. For example, the trunk of a tree is usually brown, and its leaves are
often green. Color helps us differentiate dimension points. However, space is
the only _guaranteed_ way to differentiate all dimension points from all other
dimension points.

### Space in Programming

When a computer runs a computer program, it actually puts different objects into
different _physical locations_. It locates them somewhere in memory, inside of
the CPU, etc. They are represented by electricity, and that electricity has a
real location in the physical universe. Space _is_ the mechanism a computer is
using to keep things separate.

However, the code of a computer program is only a description of a potential
universe. It's basically a description of the qualities that certain dimension
points would have if they existed, including actions those dimension points
would take in various circumstances. It is, in essence, a set of ideas about
qualities a universe _would_ have if that universe existed.

Code consists only of a set of symbols in order (including symbols like the
space character that displays as empty space on our monitor). These symbols are
the only tool we have to describe anything in code. We need some way to:

1. Indicate that dimension points are different from each other.
2. Indicate that the qualities we define in the program are different from other
   qualities we have defined.

We accomplish points 1 and 2 with **names**. Names are how we create space in
our programs: we give dimension points names. We also give names to various
qualities that dimension points can have, and then we assign those to dimension
points. Thus, in our programs, the rule has to be:

**No two dimension points or qualities may have the same name.**

### A Note About Reflection

Many programming languages have a concept of "reflection" where you can, while
running the program, ask questions about the program itself. For example,
imagine you have Python code that looks like this:

```Python
class Adder:
    def add(x, y):
        return x + y

my_adder = Adder()
print(myAdder.__class__)
```

That creates a dimension point called `my_adder` that is an `Adder`. Then it
prints out the word "Adder." This is reflection---we somehow looked at the
program code and took some action about it (in this case, just getting the name
of a class).

But here's the thing: the only real dimension point created in that program is
`my_adder`. `Adder` does not actually exist in the universe of the program; it's
just a quality that a dimension point can have. So what's happening here,
conceptually?

Well, conceptually, what reflection is doing is operating in _another universe_.
It basically makes a whole new universe that is a model of _the code_. It's
taking the code and creating a whole other universe---one that isn't the program
that's running. Instead, it's a universe that models out how _code_ looks and
relates to other pieces of code.

In that universe (the universe of "reflection," the model of the code) we create
dimension points that represent qualities. For example, what Python is really
doing when you call `myAdder.__class__` looks something like this (though I'm
dramatically oversimplifying):

```Python
myClassName = object_class_name[myAdder]
```

Where `object_class_name` is a special, internal dictionary that Python
maintains that maps objects to the name of their class. That special internal
dictionary is, in essence, part of a _different universe_ than the universe of
your program.

This fools programmers into believing that qualities have concrete existence in
the universe of their programs, because they can do things like "tell me the
name of this class" inside of their code. However, and this is very important,
conceptually:

**Qualities do not have real existence. Only dimension points exist.**

Qualities only manifest when they are assigned to a dimension point that
actually exists. Even then, it's only the dimension point that really exists. It
just now a dimension point with a quality.

This is why programmers get themselves into endless trouble when they use or
rely on reflection in their programs: they get confused about the difference
between the two universes (the universe of their program and the universe of
reflection). They make the behavior of the reflection universe affect the
behavior of the program's universe (or worse, vice-versa, where they make logic
in the program's universe change the fundamental structure of the program). This
becomes very hard to reason about and tends to cause all sorts of trouble.

## Types of Names

Taking into account all of the above, we can see that we have at least two
different "things" that can be named: dimension points and qualities. (There are
actually more things that require names, which we will talk about later in this
document.)

Qualities, though, only exist in the universe of reflection before they are made
"real" by being assigned to dimension points. So in a sense, the names of
qualities are actually in a _different universe_ from the names of dimension
points.

Most programming languages have conventions about how you _ought_ to name both
of those things, to keep them separate. These conventions help the programmer
understand, when reading code, whether you are referring to a dimension point or
a quality. For example, in Python, variables (dimension points) are _supposed_
to be named like `some_name` and classes (qualities) are _supposed_ to be named
like `SomeName`. However, there's nothing that enforces that. Sometimes you get
variables named like `ThisVariable` or `thisVariable` and sometimes you get
classes named like `this_is_a_class` and the programmer can't differentiate them
just by looking at them, anymore.

One actually could (and probably should) make a programming language inherently
enforce that by requiring some name format that always differentiates them. For
example, you could say that dimension points must always be named like
`dp<some_name>` and qualities must always be named like `q<some_name>`. Most of
the rest of this document does _not_ do that (this document is meant to be read
by people who are not already familiar with Define, as I am writing the document
before the language even exists) but the language we actually design _should_
have some way of keeping the names of different types of things inherently
separate.

## Universes: Making Names Unique

If we conceive that a program is a universe, then a library is also its own
little universe. That means there are many universes, which can interact in
defined ways.

From any individual program's perspective, it is its own universe, and then
there are universes created by other view points. These would be other programs
or even external libraries that the program uses as part of its own operations.

The names in each universe are only relative to that universe. For example, a
`dog` in one universe is not the same as a `dog` in another universe. Thus,
programs would need some way to indicate what universe they are talking about
when they refer to names. A potential syntax for this could be something like:

```
define the quality<@my_program/dog> {
   # Lots of code here
}
```

And then in some other program (perhaps a library):

```
define the quality<@some_library/dog> {
    # Lots of different code here
}
```

Alternately, this could be done with another **type of name**, like
`universe<program>::quality<dog>`. The problem is, every single name might need
some sort of universe attached to it. So it seems better to perhaps make it a
part of the names.

### Universe Conflicts

Universes have to have some sort of name. There has to be something that
prevents two Define programs from having the same name, if those two programs
need to refer to each other (or if one program needs to be referred to in some
common fashion by many other Define programs).

Thus, there has to be some sort of system that prevents these conflicts. Java
uses domain names, like `com.somecompany.package.name.ClassName`, though in
reality packages are disambiguated through Maven Central, which is not
universally enforced. Almost all languages have similar mechanisms: Python has
PyPi, Ruby has RubyGems, Rust has Cargo, and so on. However, internally in
companies, the companies have their own package management system, often
different for every company, and potentially with name conflicts with the
external repositories.

So this creates different "multiverses," where the name of two _universes_ don't
mean the same thing.

This means that likely, define programs will need two concepts:

1. The **multiverse** in which the program lives. Essentially this is some
   reference to a system that can arbitrate universe names. Some sort of
   namespacing system for universes, or some repository for universe names. You
   can think of this as the name of the package repository, in other programming
   languages.
2. The **universe** name within that multiverse.

Theoretically, name conflicts would still be possible between multiverses, but
that is much less likely, especially if we establish some convention for
multiverse names.

## Describing Qualities and Dimension Points

There are a few more problems we have to solve with just symbols:

1. How do we describe qualities?
2. How do we indicate what dimension points exist (how do we create them)?
3. How do we assign a quality to a dimension point?

This is what **syntax** is for in programming languages. Let's look at some
examples to help understand this.

### Describing Qualities

Here's a description of a negative integer in an imaginary programming language:

```bash
quality NegativeInteger {
  it starts with Hyphen.
  it then has many Digit.
}
```

We see three names in that code: `NegativeInteger` (the name of the quality),
`Hyphen` (presumably a name for the character `-`), and `Digit` (a quality
representing a single number from 0 to 9).

Everything else is part of the syntax:

- `quality` says "we are about to define a quality."
- `{` says "we are about to describe the quality we just named"
- `it starts with` indicates we require that the dimension point starts with
  this character.
- `.` indicates "we are done with describing that aspect of this quality"
- `it then has many` indicates that we expect many characters of a particular
  type.
- `.` again indicates we are done with that statement.
- `}` indicates we are done describing that quality.

And of course, the order that all the symbols go in is part of the syntax, too.

### Creating Dimension Points

Another imaginary programming language:

```
create negative_number
```

`create` is syntax, and `negative_number` is a name.

In our imaginary syntax, this would simply create a dimension point with no
quality other than having a name.

### Assigning Qualities to Dimension Points

Yet another made-up language:

```
negative_number has the quality NegativeInteger
```

`negative_number` is a name of the dimension point we created, `has the quality`
is syntax, and `NegativeInteger` is the name of the quality we defined above.

This _syntax_ is how we would indicate we are assigning a quality to a dimension
point.

## Locations in Space

So we see that names create space in a program. The most important names we use
are the names of dimension points (the things that really _exist_ in a program).
For example, in a traditional programming language, we say:

```Python
x = 5
```

That means we have created a dimension point named `x` that is a number with the
value 5.

However, what is happening when we do this?

```Python
x = 5
z = x
```

What is `z` there? Well, it could actually be three different things, depending
on the programming language:

1. We have moved the dimension point `x` into a new **position** named `z`, and
   `x` is now empty space.
2. `z` is a different **view** of `x`. That is, `x` didn't change positions.
   Instead, we are just somehow talking about `x` with an additional name that
   now _also_ means `x`. (This is a little confusing, but will become clearer
   later.)
3. We have created a new dimension point named `z` that is a **duplicate** of
   `x`.

Let's talk about each of these options.

### Positions

If a dimension point is moved to a new position, it no longer occupies its old
position. In a program, this would mean that you actually _change the name_ of a
dimension point. For example, look at this imaginary syntax:

```
    define a position named ball.
    create a dimension point in position ball.
    define a position named goal.
    move the dimension point in position ball to position goal.
```

In that form, it's pretty straightforward what is happening. We had a dimension
point named "ball" and we actually _renamed_ it (moved it) to "goal."

In a programming language, moving a dimension point would mean that its old name
no longer refers to the dimension point. In fact, its old name is now empty
space. The dimension point has a totally new name. Referring to the old name at
any point after that in the program would be an error. For example, in the above
code, the program must not refer to the name "ball" after that dimension point
is moved into the name "goal."

In the physical universe, it is quite common to move an existing dimension point
into a new position. However, this concept in programming languages is quite
rare. The only programming language I have used that implements this concept is
Rust, and even there, it's done in a way that is very hard for programmers to
understand.

Programming languages often need a way of indicating there is an empty space
that _could_ be occupied by a dimension point. (This will become clearer as we
describe more concepts further on in this document.)

We need a new **type of name** to indicate empty positions in space that a
dimension point could occupy. These would look something like `position<goal>`,
`position<ball>`, etc. Only one dimension point may occupy a position. So in
fact, we may not need the syntax for referring to dimension points (the earlier
naming concept of `dp<some_name>`) and possibly we only need the syntax for
indicating there is a position a dimension point could occupy.

### Views

Sometimes in a programming language, we need some way to indicate that we are
simply viewing a dimension point where it is, without moving it. For example,
let's take this function in C:

```C
    void add(int x, int y, int* result) {
        *result = x + y;
    }
```

That modifies the dimension point `result` in place without moving it to a new
location. (More specifically, it changes the quality of `result` to being a
number that is the sum of `x` and `y`).

We need some way to indicate that a name is just a _view_ of some
already-existing dimension point. This would require a new **type of name**. If
you wanted to keep these separate from other names, you might require they be
named something like `view<result>`.

### Duplicates

In some programming languages, doing `z = x` might actually create a _copy_ of
the data that is in `x`. In other words, it creates a new dimension point with
the same qualities as `x`, but in a different position.

This does not require a new type of name. Instead, it should be represented as
explicit syntax anywhere it happens. We could imagine syntax like this:

```
create a dimension point in position<apple1>.
assign the dimension point in position<apple1> the quality IsAnApple.
create a duplicate of position<apple1> in position<apple2>.
```

Basically, we have an apple, and then we make a copy of that apple in another
position.

## What About View Points?

There are only two _real_ view points involved in a computer program: the
programmer(s) and the user(s). All dimension points inside of the program are
"created" by the programmer. The user creates input in the physical universe,
and sees output in the physical universe. However, the program only knows about
that because it gets a symbolic _representation_ of the input and sends symbols
out that _represent_ the output.

If we want to get more specific, the program doesn't actually know that its
inputs are coming from a user, or that its outputs are going to a user. It only
knows that they are going to and from the physical universe.

For example, when I hit the "a" key on my keyboard, the computer gets an
electrical signal. The program then interprets this electrical signal as the
number 97, which represents the letter "a" in ASCII. The electrical signal is a
representation of me pressing "a", and then the number 97 in the program is a
representation of that electrical signal. The program only knows that it got the
number 97 from outside of itself.

The same thing happens for output. When the program wants to show me the letter
"a", it sends an electrical signal to the video card, which sends it to the
monitor, which translates that signal into the character "a".

So essentially, we can consider that a program interacts with two universes: its
own universe (the one defined by the programmer(s)), and the physical universe.

### Interfaces Between the Program and the Physical Universe

The universe of the program has a certain limit to its complexity---it is
defined by the programmer, and it has certain rules based on the qualities that
have been assigned to dimension points. The physical universe also has rules,
but has nearly infinite potential complexity. Thus, it is important for programs
to clearly define and limit how they interact with the physical universe, to
limit how the physical universe's complexity can affect the program.

How to design this interaction between the physical universe and the program is
often thought about only minimally by programmers. Programmers often spend quite
a bit of time making sure that the program's own universe behaves correctly
(that is, that it's internally consistent) but don't ensure that it continues to
behave correctly when the physical universe intervenes in unexpected ways.
However, unexpected behavior on the part of the physical universe is a very
common source of error in real software systems.

You as a programmer could, theoretically, know every possible behavior of a
program that you wrote. It is unlikely that you could know every possible
behavior of the physical universe.

It is worthwhile for a programming language to make it very clear when this
boundary is being crossed, provide ways to strictly limit how that interaction
works, and provide mechanisms for programmers to help ensure their program
behaves correctly in unexpected scenarios. The best solution is to constrain the
program's interface with the physical universe so much that you can essentially
guarantee the program's correct behavior.

It is also important to think about this in the design of the language itself.
Code lives in files on a filesystem. Files and directories are abstract
concepts, but bits on a disk are real physical universe things. The language
itself (or its implementation) has to interact with those, and should constrain
its interactions to limit how much the complexity of the physical universe can
affect the general success of all programs in Define in unexpected ways.

## Forms

A form is:

**A set of dimension points with a defined relationship to each other in
space.**

In the physical universe, the simplest form is two dimension points that always
stay the same distance apart from each other. For example, here's two points
that are exactly eight spaces away from each other in this text:

```
.        .
```

Conceptually, what really happens there is we tell the point on the left "you
are eight spaces away from the point on the right," or we tell the point on the
right "you are eight spaces away from the point on the left," or we tell that to
both of them.

If you made it four points with defined relationships between them, you could
have a rectangle:

```
.        .

.        .
```

We tend to then just think of this as "a rectangle," but in reality "a
rectangle" doesn't exist, and only the four dimension points exist. Each of the
four dimension points has a quality that causes it to stay in position relative
to the other four dimension points.

### Forms in Programming Languages

Remember, the way that we make space in programming languages is by names. A
"form" in a programming language is a set of dimension points whose _names_ have
a fixed relationship to each other.

Let's look at how the concept of "a form" is defined in traditional programming
languages.

For example, let's imagine we wanted to represent a seat in a theater, in our
program. Theater seats are usually split into sections: "Orchestra" for the
seats on the ground level closest to the stage, "Balcony" for the second story
seats, and so forth. Within those sections, rows of seats are usually given a
letter, like Row A, Row B. And then seats in a row are given a number: 1, 2, 3.
All combined, those three points (section, row, seat) uniquely identify a seat.

Here's the simplest version of how we would represent that concept (a theater
seat) in Python:

```Python
class TheaterSeat:
    section: str
    row: str
    number: int
```

Then when we want to actually create a TheaterSeat and print out where it is,
the code might look like:

```Python
front_seat = TheaterSeat(section="Orchestra", row="A", number=1)
print(front_seat.section + " Row " + front_seat.row + " Seat " + front_row.number)
```

That prints out: `Orchestra Row A Seat 1`.

Conceptually, the way a Python programmer thinks about this is that they have
defined a concept called TheaterSeat. Then they have created a TheaterSeat named
`front_seat` with certain fields set to certain values. Finally they have
requested the `section`, `row`, and `number` fields from `front_seat`.

However, that example only actually _requires_ three dimension points: a
section, a row, and a seat. `front_seat.section` is simply the name of one of
those dimension points. In how we think about defining universes, `front_seat`
_does not exist_. It is simply a name that creates a defined relationship
between `section`, `row`, and `orchestra` in this program. Remember that in a
program, names are space, so `front_seat` is actually _empty space_. It's not
even a position---it's a name we are using for a particular arrangement of
dimension points.

### Talking About Forms

Forms are another **type of name** that a program must know about: the name of a
_form_. To keep those totally separate from other names, you would need to
always name them something like `form<some_form_name>`.

You also have to be able to refer to the dimension points inside of the form,
somehow. There are multiple ways a programming language can do this. Most
programming languages do something like "a name, followed by a separator,
followed by another name." So you see `front_seat.section` or
`front_seat->section` or `front_seat::section`. Since we must use symbols and
names to solve this problem, when we refer to a form, it is going to have to be
via some sort of mechanism like this.

Given our system of making names fully unique, syntax like this might be
acceptable: `form<front_seat>dp<section>`. And then forms that contain other
forms would look like: `form<theater>form<front_seat>dp<section>`. That might
not be the most readable syntax, though, so perhaps other syntaxes would be
preferable.

### Defining Forms

Let's now take into account a few things:

1. We have a rule that no two things may have the same name.
2. Syntax creates dimension points and defines qualities.
3. Forms are purely about how dimension points are named, and referring to them
   requires special syntax.

What this means is that how we define forms (and in fact, **anything to do with
spatial relationships between dimension points**) has to be a defined part of
the _language syntax_. You can think through alternatives (some way where we
just say "in a form" is just like any other Quality), but they all result in
some sort of logical contradiction or some impossible situation.

There are various syntaxes one could imagine for indicating that dimension
points are in a named form. For example:

```
front_seat {
    section
    row
    number
}
```

Or:

```
put {section, row, number} into a form named front_seat
```

Both of those simply provide a form to section, row, and number, without giving
them any other qualities.

The point is simply that a programming language must have a syntax for defining
forms.

### Forms Can Overlap

There is an interesting point about forms that is easy to miss. Let's look at
this form:

```
a       b


    c
```

Most simply, that looks like a single form: a triangle made by points `a`, `b`,
and `c`. However, we could also consider that `a` and `b` are in a form by
themselves (a line). The same for the pairs `(b, c)` and `(c, a)`.

The instant you create the triangle, those other forms also exist. We might not
think about them, we might not need a name for them, and we might have no use
for them, but they are there.

Programming languages need some way to account for all of this. There have to be
ways to make new forms that include all (or some) of the points of an existing
form (plus possibly new points). Those dimension points don't _move_ when placed
into forms. We just consider they have some form, now.

If you have a form like `front_seat {section, row, number}` then you also have
un-named forms made out of section/row, row/number, and number/section.

In fact, merely by defining positions, forms exist. So even if we just had
`position<section>`, `position<row>`, and `position<number>`, there would be
four un-named forms in existence.

### Uniqueness of Forms

There is an important rule about forms:

**Any form that has the same dimension points is the same form.**

That means that programming languages must treat any form that contains the same
set of dimension points as being identical objects. In fact, languages should
likely forbid the creation of two separate forms that contain identical points.

## Types of Forms

There are, fundamentally, only three types of forms that can logically exist.

### Bags

A bag is a collection of dimension points with no defined relationships. You
just have a quantity of dimension points, and that's all you know.

Most programming languages actually don't let you express this as an intention,
that you just want a bag, but it's actually a very common need. "I have a list
of numbers and I don't care what order they go in as long as we do something to
all of them," for example.

It is worthwhile for a programming language to allow a developer to explicitly
indicate they intend to create a bag, so the compiler can optimize it as it sees
fit.

### Graphs

A graph is a bag of dimension points that are connected to each other. You don't
know or care what shape the dimension points make, you just know that point A is
connected to point B, or point C is connected to points D and E.

There are certain special forms of graphs that are very common. The most common
is a _sequence_: A set of dimension points that have an ordering. A comes before
B and C comes after B, and so on. Programs traditionally model these as arrays
or linked lists.

Programming languages often create convenient syntax for specifying sequences
and other specialized graphs, but fail to provide graphs as a basic concept
(even though they are the underlying concept for most data structures).

### Shapes

A shape is a set of dimension points with defined relationships to each other in
space. In a graph, if the points move, you don't care---they still have the same
connections. In a shape, if the points move, you have a different shape.

This is what people traditionally think of as an "object" or "form" in the
physical universe.

In a programming language, shapes are represented by structs or similar pieces
of syntax. Basically, a set of names for certain positions in space that are all
defined together, which gives them a relationship to each other ("we are all in
this struct together").

For the sake of simplicity, almost every example of a form in this document
tends to use a shape, because they are the simplest to write out and understand
in syntax.

### Combinations

As mentioned above, forms can contain other forms. A car is made up of a body,
seats, wheels, etc. Bags can contain graphs, shapes, and other bags. Graphs can
contain bags, shapes, and other graphs. Shapes can contain bags, graphs, and
other shapes.

This is particularly important for graphs, because you could have a graph where
the relationship is "these three points in this form have a relationship to
these five points in a different form." But it's still relevant for bags and
shapes, too.

This is how you get the advanced forms of data and data structures that most
programs depend on. For example, you could implement a dictionary as a bag of
graphs (a set of key/value pairs) or more complex combinations.

### Constraints

Programs can place constraints on forms. You can have "a bag of green balls" and
know that every ball inside is green even though you haven't looked at each
ball. You can:

1. Say what qualities are allowed in a form. ("May only contain green balls.")
2. Enforce relationships between points in the form. (This covers almost
   unlimited potential constraints, such as "all dimension points in the form
   must match some constraint," "there can be no duplicates," "X can never have
   the same value as Y", and so forth.)
3. Control the quantity of dimension points (minimum, maximum, exact), including
   statements of the other constraints on those quantities. (For example, "at
   least two dimension points in this form must be a `string`).
4. Control changes to the form:
   - Addition/Change/Removal of dimension points
   - Addition/Change/Removal of constraints.
   - Addition/Change/Removal of connections in a graph.
   - Addition/Change/Removal of positions in a shape.
5. Define access controls (who can do what with what points).

And you can combine all of these into complex logical requirements. Constraints
can be quite advanced.

### Syntax

Programming languages need syntax to be able to express bags, graphs, and
shapes. There needs to be syntax both to define the forms and to refer to
dimension points within them. There also has to be syntax to express constraints
on the forms.

For example, one could imagine a bag being created like:

```
create a form named balls that is a bag {
    it may only contain dimension points with the quality Ball.
    it has a dimension point with the quality Ball {
        color: "green"
    }
    it has a dimension point with the quality Ball {
        color: "red"
    }
}
```

That is an extremely simple example; implementing the concept of Types of Forms
would take a lot more syntax than that.

## Machines

Let's get into a bit more detail about what a machine really is and how we would
think about it in a programming language.

The technical definition of a machine is:

**A dimension point that changes the qualities of certain dimension points in a
defined way when the qualities of certain dimension points change in defined
ways.**

So basically, one thing changes and thus another thing changes. A machine is a
dimension point that reacts to the changes of itself or other dimension points
somehow.

For example, when I press a key on my keyboard, a letter appears on my screen.
The key on my keyboard developed a particular quality (it was pressed down) and
so the screen changed its quality (it displayed a letter).

A machine can change just itself, or it can change other things, too. For
example, if I turn on a blender, it turns starts spinning its own blade (it
changes itself). But when I put a carrot into a blender, the blender cuts up the
carrot into very small pieces (it changes something else).

### Machines in Programming Languages

A program is, in some sense, one giant machine. You tell it to start (for
example, you type `ls` at the command line---you typing and hitting enter are
the dimension points you sent) and then it does stuff.

However, within the universe of the program itself, conceptually there are many,
many machines. These are the machines we care about, when we are talking about a
programming language.

For example, a program might have a concept of a toaster: a machine that heats
bread. In Python, you might define and use a toaster like:

```Python
class Toaster:
    def toast(self, bread_type: str) -> str:
        return "toasted " + bread_type

my_toaster = Toaster()
my_bread = "white bread"
result = my_toaster.toast(my_bread)
print(result)
```

That would print out `toasted white bread`.

The way a Python programmer thinks about that is that they have created a
Toaster named my_toaster. A toaster has the ability to toast bread. You give it
some bread, and gives us some toasted bread.

In the way that we think about universes, here is the sequence of events that
actually occurred:

1. We created a dimension point named `my_toaster`.
2. We assigned that dimension point the quality of `Toaster`.
3. We created a dimension point named `my_bread`.
4. We assigned `my_bread` the quality of being the string "white bread."
5. We created a dimension point named `result`.
6. We moved `my_bread` in space so that it had a defined relationship to
   `my_toaster`. (This was the call to `my_toaster.toast(my_bread)`.)
7. `my_toaster` has the quality that if it sees a string in that specific
   location in relationship to itself, it will modify a second dimension point
   (`result`) to have the quality of being the string string `"toasted "`
   followed by the input string.
8. Those conditions are met so `my_toaster` modifies `result` accordingly.

There are only three dimension points: `my_toaster`, `my_bread`, and `result`.
The function `toast` doesn't exist---it is simply a quality that `my_toaster`
has.

### Triggering Machines

Machines can take action based on any quality of any dimension point or set of
dimension points. For example, one could imagine a syntax to trigger a machine
that looks like:

```
when room.light_switch has the quality of being the string "on":
    assign the quality TurnedOn to room.light_bulb

when room.light_switch has the quality of being the string "off":
    remove the quality TurnedOn from room.light_bulb
```

And then it would trigger whenever you did something like:

```
assign the quality String to room.light_switch {
    value: "on"
}
```

There we imagine two dimension points: `room.light_switch` and `room.light_bulb`
(two dimension points in a form named `room`), and flipping the switch changes
the quality of the lightbulb. That would be a trigger on a quality.

However, the most common triggering mechanism in a program is that dimension
points have entered a particular space in a particular form. For example, in the
physical universe, you might have a light bulb that turns on just because a
person (a particular form) has walked into a room (a space). In a program, a
function call would be an example of this, like the call to
`my_toaster.toast(my_bread)` in the Python example further up: the dimension
point `my_bread` has entered the space `toast`.

Because this has to do with space, it requires syntax for this particular form
of trigger. For example, the syntax for triggering a machine that toasts a piece
of bread might look like:

```
    create a dimension point named my_toaster.
    assign the quality Toaster to my_toaster.
    create a dimension point named my_bread.
    assign the quality String to my_bread {
        value: "white bread"
    }
    make my_toaster toast my_bread
```

`make X ________ with Y` would be the special syntax there for triggering the
machine's action (the toasting of the bread, in this case). It moves `my_bread`
and `my_toaster` into a particular spatial relationship named `toast`.

### Defining Machines

Machines essentially need to be able to define two things:

1. The conditions under which they trigger.
2. What they do when they are triggered.

#### Trigger Conditions

There are three events that can cause a machine to trigger:

1. A new dimension point is created.
2. Something about a dimension point changes.
3. A dimension point is destroyed.

So this gives us three things we need to cover with syntax. Here's some
imaginary examples:

```
    when (a dimension point is crated)
    when (a dimension point changes)
    when (a dimension point is destroyed)
```

However, most machines want to be more specific than that---they don't want to
trigger on every single creation, change, or destruction. Instead, they want to
limit what kinds of creations, changes, or destruction they trigger on. They can
do this in three ways:

1. By the quality of the relevant dimension point.
2. By specifically naming which dimension points they act on.
3. By some spatial relationship between this dimension point and others.

For qualities, the potential syntax is relatively straightforward:

```
    when (a dimension point is created with the quality IsGreen)
    when (a dimension point changes to having the quality IsRed)
    when (a dimension point changes from having the quality IsPurple)
    when (a dimension point changes from having the quality IsBlack to having the quality IsWhite)
    when (a dimension point is destroyed with the quality IsBlue)
```

Note also that we need some way to indicate what happens when _this_ quality is
assigned to a dimension point (like, does something happen immediately after we
assign the quality "LightSwitch" to a dimension point?):

```
    when (this dimension point is assigned this quality)
```

Referring to dimension points by name is actually pretty straightforward:

```
    create a dimension point named traffic_light.
    when (traffic light is destroyed)
```

Though (as you might have already realized above) we need special syntax for
talking about "this" dimension point (the one that _is_ the machine):

```
    when (this dimension point is destroyed)
```

There are various ways to talk about spatial relationships in a trigger:

```
    when (a dimension point in the form front_seat is destroyed)
    when (a dimension point in the form front_seat changes)
```

We don't even have to refer to a specific form, we could do something like:

```
    when (a form like {String, Number, String} is created)
```

Which would trigger whenever a new form with a String, Number, and String in it
was made.

However, we can also define special spatial relationships between dimension
points and trigger on those special relationships. This needs its own section to
talk about it.

#### Functions

There is a special sort of trigger condition called a "function." Machines in
the physical universe have certain abilities: different things a single machine
can do. For example, a car can start, stop, move forward, move backwards, turn,
etc. In the physical universe these things are triggered by moving objects---in
other words, changing the spatial relationship of dimension points. For example,
if you want to turn a car to the right, you turn the steering wheel to the
right. You moved the steering wheel's position in space.

In a program, you need to be able to somehow tell a machine "specifically
execute this function." Above in the "Triggering Machines" section we talked
about how you might express a trigger like this when you want to execute it:
`make my_toaster toast my_bread`. But when you're defining a function, how do
you indicate this trigger exists? That is, how do you say "toast is a function
this machine can do?"

Basically you need to define a special spatial _relationship_ that will occur
between dimension points. As we have noted a few times before, syntax in other
programming languages for this looks something like:
`my_toaster.toast(my_bread)`. That puts `my_bread` into a relationship with
`my_toaster`. The relationship is called `toast`.

But what is a "function" really, on a pure conceptual level? Well:

**A function is the statement that a machine will behave a certain way when
dimension points with certain qualities occupy certain positions.**

For example, let's take an actual toaster in the physical universe. When you
push the handle down (a dimension point with the quality of being the handle) it
heats up. If there is bread _inside_ the machine (a position) that bread gets
toasted. In order to describe this toaster conceptually, before we even _have_ a
toaster, we have to say things like "there is a handle" and "there is a space
for bread." That's what we are doing when we define a machine, in programming.

Most languages solve all of this by creating named functions, like our `Toaster`
example from earlier, where there is a function named `toast`. The "space for
bread" is the `bread_type` argument to `toast`, and `toast` is the "handle."

But let's think about what we actually need, minimally, in order to describe a
function:

- A dimension point that represents a trigger (like a steering wheel on a car,
  or the handle on a toaster)
- A set of possible positions for the trigger, where different actions will
  happen depending on where that trigger is located.
- A set of positions that represent locations for dimension points we might take
  action on

We also often require that the dimension points in all those positions also have
certain qualities.

Note that the position for the trigger can be the same as one of the positions
the function takes action on. That is, the function can modify or "look at" the
trigger itself, if needed.

Theoretically, you could even require multiple dimension points in multiple
different locations, for the trigger. On my keyboard right now, I have to press
Shift and press the letter "a" if I want to get a capital A. That required two
dimension points to be in particular locations---simply pressing Shift by itself
did nothing.

#### Functions Are Potential Forms

In the way that we think about universes, we notice something interesting here:
everything about a function sounds an awful lot like a _form_---a defined
spatial relationship between dimension points. It's like saying, "when the
trigger is here and some other dimension points are in these other positions,
then take an action." The one addition is that we can require certain qualities
be assigned to the dimension points in that form.

We could, in fact, describe a function like this, in an imaginary language:

```
potential form toast {
    position<handle_down> is a ToasterHandle
    position<bread_space> is a Bread
}
```

And then the trigger would just look like:

```
when (potential_form<toast> exists)
```

Meaning "when dimension points are in that form."

You'll notice we need a new **type of name** for a potential form. (It's not
even a form, it's just a description of a form that _could_ exist.) Since
potential forms have theoretical uses outside of functions, we would probably
want to name them something like `potential_form<some_name>`. Or we might use
the term "shape," (so `shape<some_name>`) because they sort of indicate how
dimension points are _shaped_ (as opposed to a form, which is a concrete
object).

In most languages, there is only one type of trigger. The `Toaster` example
above would look something like:

```
potential form toast_function {
    position<self> is a Toaster
    position<toast> is a Function
    position<bread_type> is a String
    view<result> is a String
}
```

There's just a generic quality called "Function" that dimension points can have.
You can think of it as "when I shoot this magic dimension point at my Toaster,
it toasts the bread." If the Toaster's function was very limited, you actually
could simplify that to:

```
potential form toast {
    position<self> is a Toaster
    position<bread_type> is a String
}
```

We would think of that as a sort of automatic Toaster---whenever a Toaster
exists and bread is inside of it, it will simply toast the bread.

Interestingly, I suspect this also solves many of the problems of parallelism
(doing multiple things simultaneously) in programs. If you want to toast
multiple pieces of bread, you clearly need to either have multiple toasters, or
a toaster with multiple bread slots, or something, and it seems easier to detect
if you're trying to simultaneously put the same piece of bread into multiple
toasters. (The one thing it doesn't inherently solve is: what if multiple
toasters just _view_ the same piece of bread?)

### Defining a Machine's Action

Now we understand how machines can be triggered, how do we say what they will
_do_ after they are triggered? Well, the basics of that are pretty simple. You
would have a trigger and then you would say what happens:

```
    when (a dimension point has the quality Number with the value 5)
    then (change that dimension point to having the value 4)
```

And then what goes into the "then" block is the actual _action_ of a program.
That's not too hard to understand: we have some syntax for describing action
that occurs, which involves the creation of dimension points, the assignment of
qualities to dimension points, and the triggering of other machines.

However, there are two tricky things we have to deal with:

1. How do we talk about the dimension points we are changing, especially when
   there is more than one? Above we said `change that dimension point`. That's
   not going to work when a machine operates on more than one dimension point.
2. Can machines create new dimension points, and if so, what happens to those?

Let's address both of those.

#### Talking About the Dimension Points a Machine Cares About

One of the tricky points about defining a machine is that we have to assign
names to things that don't yet actually exist---the dimension points outside of
the machine that the machine triggers on or modifies. For example, imagine this
syntax:

```
    quality Adder {
        it can add {
            with a Number named x
            with a Number named y
            with a Number named result
            by doing {
                result = x + y
            }
        }
    }
```

That's just a machine that takes two numbers, adds them, and returns the result.
In that example, `x`, `y`, and `result` don't actually _exist_ when we are
defining the machine. They are just theoretical dimension points that we would
operate on if they were given to the `add` function.

Here we are using names simply to differentiate concepts---the idea that
`x`,`y`, and `result` _could_ exist and we need some way to talk about them when
describing the machine's action.

This is where the concepts of _views_ and _positions_ become the most useful.

#### Views in Machine Definitions

When defining a machine, we could consider we are simply viewing a dimension
point where it is, without moving it. The machine simply "knows" the dimension
point exists and it's going to inspect or modify that dimension point. We could
think of this as the machine is simply _viewing_ the dimension point where it
sits. We tell the machine "operate on that dimension point, over there."

For example, `result` in the `Adder` code above would be a view: we want to
change what's sitting in the space named `result` without moving the thing
that's there.

#### Positions in Machine Definitions

Very often, a machine triggers when you move dimension points from their current
location into a new location. They stop occupying their current space, and they
start occupying a new space---a new position. Our steering wheel example above
was an example of this, in the physical universe: the steering wheel turns to
the position called "right" so the wheels of the car turn right.

In our Adder example, we might say "you have to actually move dimension points
into the positions `x` and `y` in order for the Adder to function." They would
cease to occupy their existing space.

Let's make up some imaginary syntax to demonstrate this concept:

```
    my_Adder is an Adder.
    input_one is a Number with the value 5.
    input_two is a Number with the value 4.
    result is a Number.
    make my_adder add with move(input_one), move(input_two), view(result).
```

In that example, `input_one` gets _moved_ into `x` and `input_two` gets _moved_
into `y`. The names `input_one` and `input_two` now refer to empty space, and it
would be an error for the program to refer to them again later.

#### Creating Dimension Points

When we write code, it looks like we tell machines to create dimension points,
destroy dimension points, and assign them qualities. That's not _exactly_ what's
happening, though.

In the conceptual universe of the program, the _programmer_ creates all
dimension points, assigns all qualities, and causes dimension points to be
destroyed.

In order for a dimension point to exist, the programmer must write some sort of
code. Mostly this is simple to see. For example, in a Python program, a
developer might write:

```Python
x = 2 + 3
```

The programmer defined the dimension points `2`, `3`, and `x`. However, it gets
a little more complex when the programmer describes logic that creates some
uncertain number of dimension points. Let's take another Python example:

```Python
    def say_hello(times: int) -> str:
        list_of_hellos = []
        for n in range(times):
            list_of_hellos.append("hello")
```

That creates a varying number of strings depending on the value you pass in for
`times`. The programmer is still creating those dimension points, they just are
doing it in a more complex way. They are saying: "I decide to create dimension
points according to the logic this machine dictates." But it's still the
programmer's decision. Dimension points are not actually created by "the
program" or "the machine." They are created by you, the definer of the universe.

#### Users

What about the user? The user is also a view point, right? Totally true. The
user provides input to the program, which we _could_ conceptually think of as
dimension points they created. However, you can't actually represent the user's
dimension points in the program without the programmer creating a dimension
point inside of the program that _represents_ the user's input. For example, in
Python:

```Python
name = input("Please enter your name: ")
```

The user typed their name, but we represent that as our own dimension point
called `name`. So we see once again that it's actually the _programmer_ that
creates all dimension points.

As an interesting side note, what we are seeing here is that we are doing our
best to _duplicate_ the user's dimension point into a dimension point in the
program. This means that _communication_ is occurring between the program and
the outside world. This deserves special attention in a program, as noted before
when we talked about the boundary between a program and the physical universe.
How to handle communication effectively in a program is a topic for another
section or another document, but it struck me as interesting so I thought I'd
call it out here.

#### In the Physical Universe

In the physical universe, what's really happening when you run a program is that
the computer is grabbing existing dimension points (electrons) and making them
_represent_ the program's dimension points. Qualities from the program's
universe don't exist (so there is no assignment of qualities). Destruction is
just represented by turning off the machine, the absence of electrons, or a
particular configuration of electrons that the computer designers agreed means
"nothing here."

## Composition of Qualities

Some qualities are actually a combination of a set of other qualities. For
example, when we perceive the color of an object, we are actually perceiving a
few different qualities of that object:

- **Hue**: When light reflects off an object, it actually reflects lots of
  different waves. We see one color from that, based on the average wavelength
  of all the reflected light. We call this the "hue."
- **Saturation**: The "purity" of the color. How similar are all the different
  wavelengths that are being reflected off the object? If they are all red, it
  looks like a very _pure_ red.
- **Luminance**: The "brightness" of the color. Essentially, how powerful are
  the light waves that are hitting your eye?

So if we had a quality called `PerceivedColor` it would really be three
different qualities all in one.

### Syntax for Composition

A programming language would need syntax to indicate that one quality is
composed of other qualities. Traditional programming languages would just make
this into something like a form:

```Python
class Color:
    hue : int
    saturation : int
    luminance : int
```

In the way that we think about universes, there are a few different ways we
could think about composition. The first is that we could just say you always
have to apply all there qualities separately to any dimension point that you
want to have a color:

```
create a dimension point named ball
assign the quality Hue to ball with value: Red
assign the quality Saturation to ball with value: Pure
assign the quality Luminance to ball with value: Bright
```

However, it's impossible for an object to have a Hue without a Saturation or
Luminance. Like, those three things aren't separable. (Even if they have a
Luminance of 0, they still _have_ the quality of luminance.) There must be some
way to indicate that some qualities are composed of other qualities.

A syntax could look like this:

```
quality PerceivedColor {
    it is composed of {
        Hue
        Saturation
        Luminance
    }
}
```

A language then needs mechanisms to deal with composition. For example, what
happens when a function triggers on one of those qualities? Do they all execute
independently, or in some order, or does only one of them run? Is there some way
for PerceivedColor to override the behavior of any of the qualities it's
composed of, or do they all operate independently? How do I indicate if I want
to set the Hue on a dimension point?

Let's talk about how we would handle various possibilities.

### Independent Composition

The simplest case is like the `PerceivedColor` case above. Hue, Saturation, and
Luminance are three independent properties. I can change any one of them and it
doesn't affect the others. I would at least need a syntax to indicate that I'm
changing the Hue, though:

```
create a dimension point named ball
assign the quality PerceivedColor to ball with the value Red
change ball.Hue to Green
```

We could imagine that Luminance and Saturation both defined some function, like:

```
quality Saturation {
    when (this dimension point enters form<dark_room>) {
        set this dimension point's Saturation to 0.
    }
}

quality Luminance {
    when (this dimension point enters form<dark_room>) {
        set this dimension point's Luminance to 0.
    }
}
```

Those would both just execute independently when `ball` "entered"
`form<dark_room>` (whatever "enter" means in our programming language). This is
the ideal case and the simplest. Ideally, machines are designed so that their
functions can always execute independently.

### Conflicting Composition

Imagine a program that looks something like this:

```
quality IceCream {
    when (this dimension point enters form<lava_pool>) {
        destroy this dimension point
    }
}

quality Bomb {
    when (this dimension point enters form<lava_pool>) {
        make this dimension point explode
    }
}

quality IceCreamBomb {
    composed of {
        IceCream
        Bomb
    }
}
```

When I put an `IceCreamBomb` in a `form<lava_pool>`, what happens, in what
order? In most programming languages, the answer is "something confusing
happens," and the advice from experienced programmers in those programming
languages is "don't use this programming language's composition mechanisms."

Some languages ask you to take a particular viewpoint of the object. For
example, in C#, you might solve this problem like:

```C#
IceCreamBomb myBomb = new IceCreamBomb();
// Make it explode.
((Bomb) myBomb).intoLava();
// Destroy it
((IceCream) myBomb).intoLava();
```

Other languages just throw an error and say you can't have two functions with
the same name in the things you are trying to compose together.

Probably the best solution to this problem is to let the composer declare how
the composed pieces should behave. In our example, we probably want to make the
bomb explode and _then_ destroy itself. We would need some way to indicate this.
This is the first time that we seem to actually need names for machine triggers
that exist within a quality, so we can indicate what we're talking about when we
say what should run when. (This would be a new **type of name**, something like
`trigger<when_in_lava>`.)

So we would need some syntax like:

```
quality IceCreamBomb {
    composed of {
        IceCream
        Bomb
        resolve conflict for trigger<when_in_lava> by running in order: Bomb, IceCream
    }
}
```

The important point here is that the composer says explicitly what's going to
happen.

### Complex Resolution

One of the most difficult situations to resolve is: what if the right resolution
order is for one of the composed functions to happen _inside_ of the other
composed function? This gets us into a new subject: functional composition.

## Functional Composition

Imagine we have a dimension point that represents a camera with a flash, and
they both respond to the photographer pressing a button on the camera. The
sequence has to be: open the camera's shutter, display the flash, close the
shutter. Here's an example of the problem, in imaginary syntax:

```
quality Flash {
    trigger<on_button_press>: when (camera button is pressed) {
        make light
    }
}

quality Shutter {
    trigger<on_button_press>: when (camera button is pressed) {
        open shutter
        wait 10 milliseconds
        close shutter
    }
}

quality Camera {
    composed of {
        Flash
        Shutter
    }
}
```

The `Camera` object needs to somehow resolve what happens when the camera button
is pressed so that everything happens in the right order. There are multiple
potential solutions to this.

### Decompose the Problematic Functions

We could change the code of Shutter to look like:

```
quality Shutter {
    trigger<on_button_press>: when (camera button is pressed) {
        open shutter
        start a timer in position<camera_timer> for 10 ms
    }

    when (position<camera_timer> finishes) {
        close shutter
    }
}
```

Then we just have to say "run the Shutter's `trigger<on_button_press>` before
the Flash `trigger<on_button_press>`." If you have access to the code of the
qualities you're composing, this is often the simplest and best solution. Note
that in order for this to work properly, the programming language would have to
guarantee that in a `Camera`, the code of `Flash` runs directly after the code
of `Shutter`, without any other trigger occurring.

You could even move the shutter open and close functions into separate qualities
so that you can reference the functions separately in all places in the code. In
some cases, that's the simplest thing to do.

### Change the Trigger

The `Camera` quality could explicitly change when the `Flash` trigger executes:

```
quality Camera {
    composed of {
        Flash
        Shutter
    }

    resolve conflict of trigger<on_button_press> {
        redefine Flash's trigger<on_button_press>: when (shutter opens)
    }
}
```

That requires that `Camera` be able to reach into the internal concepts of
`Shutter` to see that the shutter opened.

### Entirely Replace the Trigger

The `Camera` could decide to throw away the code that `Flash` and `Shutter` have
implemented and just re-write all of it:

```
quality Camera {
    composed of {
        Flash
        Shutter
    }
    resolve conflict of trigger<on_button_press> by full redefinition {
        when (camera button is pressed) {
            open shutter
            make light
            wait 10 milliseconds
            close shutter
        }
    }
}
```

This is the worst option. Why are we even composing those two qualities if we
are just going to rewrite everything they do?

### Make the Composed Pieces Handle Composition

Some qualities might be designed entirely and only to be composed into other
qualities. In our `Camera` example, we could rewrite the `Shutter` quality like
this:

```
quality Shutter {
    around when (camera button is pressed) {
        open shutter
        run original trigger
        wait 10 milliseconds
        close shutter
    }
}
```

You'll see two new things there: the word `around` and the statement
`run original trigger`. What's happening here is that the Shutter quality does
_nothing_ by itself. It only does something if _another_ quality defines a
trigger on when the camera button is pressed. In this case, when `Flash`'s
trigger fires, what will happen is that `Shutter`'s trigger will fire first, and
essentially "wrap" Flash's trigger. Shutter's trigger can then modify anything
about the environment, run Flash's trigger, and then do any sort of "cleanup" it
wants to after Flash's trigger completes.

If multiple qualities define an `around` trigger, you do need some way to say
which order they will run in, but that's a much more powerful conflict
resolution mechanism than just ordering normal functions, because you're instead
ordering how functions will wrap each other (more like "which box contains which
other box" instead of "which order do we put these boxes in on this conveyor
belt?")

This is my personal favorite form of composition. I have designed significant
programs using this method and never discovered a concept I could not represent
appropriately. Much credit to
[Moose](https://metacpan.org/dist/Moose/view/lib/Moose/Manual/MethodModifiers.pod#Around-modifiers)
for this concept.

## Fundamental Functions

As noted at the very start of this document, programs are simulations of a
universe, and they are running on a simulation machine we call a "computer."

The simulation machine has fundamental things it can do. For example, the most
basic functions of computers today are all about numbers. They can store numbers
in certain locations, move those numbers to other locations, and manipulate
those numbers (for example, by doing math with them).

At some point, when designing a language, you have to have a way to indicate you
are instructing a computer to execute one of its fundamental functions. While
you could write out a long logical description of addition using only dimension
points, that doesn't really make sense if addition is a fundamental function of
the computer. Just have a way of expressing that you're executing a fundamental
function, so you can say "now the computer adds these numbers."

## Optimization

One of the ideas behind Define is that if we provide the compiler enough
information about the intent of the program, the compiler can do most of our
optimizations for us.

The programmer should focus on writing their program logically in the way that
makes sense to them, and the compiler should figure out how to optimize that to
run best on the simulator (the computer).

Let's look at some concepts that are important for that sort of optimization.

### Sequences

When we write programs, we tend to think of them as executing a series of steps
in a sequence. For example, let's imagine a program that looks like:

```
create a dimension point named ball
assign the quality Basketball to ball
define a dimension point named basket
assign the quality BasketballHoop to basket
# Imagine that Basketball has a function named "shoot" that goes to a BasketballHoop
make ball shoot basket
```

That looks like we do five things in a sequence. However, we can also see that
some of them don't need to be sequential. For example, `ball` and `basket` could
have been created in the same instant. Assigning them their qualities could then
also have been done simultaneously, afterward. The creation of the basket
doesn't _depend_ on the creation of the ball. Thus, when compiling that
imaginary language, a compiler could create both `ball` and `basket` at once.

In fact, if what was above was our whole program, a compiler could essentially
create the ball as having already shot into the basket. The compiler doesn't
need to simulate exactly the _logic_ that the programmer wrote. It just needs to
produce the result the programmer intended.

### Dependencies

As we start to see above, a lot of optimization in a programming language is
based on the compiler's ability to determine which actions are dependent upon
which other actions, and _how_ they are dependent. Here's an example that shows
what we mean by "how they are dependent":

```
create a form named soccer_field {
    position<left_goal> is a Goal
    position<right_goal> is a Goal
}
create a dimension point named ball
assign the quality SoccerBall to ball

make ball kick with soccer_field.left_goal
make ball kick with soccer_field.right_goal
```

Can we execute those two `kick` functions simultaneously? All of that depends on
what happens inside of the `kick` function. Logically based on our understanding
of the physical universe, we have to do those in sequence; we can't kick the
same ball to two different goals at the same time. But in a computer program,
the only way we could know that is by looking at what the `kick` function
actually does.

A programming language should make it possible for the compiler to know exactly
which actions _must_ happen in sequence and which can be optimized or moved
around.

### Constraints

A powerful way to both improve the quality of our programs and help the compiler
optimize them is to express _constraints_ on how the program may function.

For example, take this Python program:

```Python
def add(first, second):
    return first + second
```

The variables `first` and `second` there could contain anything: integers,
floating point numbers, strings, objects, whatever. A compiler has a pretty hard
time optimizing that function. So we can make it a bit more specific:

```Python
def add(first: int, second: int) -> int:
    return first + second
```

Now we know that the two values being passed in are always integers! That's much
more constrained. However, in a theoretical programming language, we could go
much farther:

```
define a quality named tiny_integer {
    it is a Integer.
    it is greater than 0 or equal to 0.
    it is less than 7 or equal to 7.
}
```

A `tiny_integer` fits inside a single byte. If we implemented our "add" function
using `tiny_integer`, the compiler could optimize all uses of it much more,
provided the computer had some way of efficiently dealing with single bytes. It
also gives us a program that is easier to debug and more likely to be correct,
as the compiler will tell us if we ever try to set a `tiny_integer` to a value
that could be greater than 7 or less than 0.

These constraints are most important at the boundary between the program and the
physical universe. A programming language should make it possible and desirable
to set constraints on the exact form of data that is received from the physical
universe, as well as methods to cope with data that comes in that does not meet
those constraints.

Most programs express these constraints as logic that can only be validated
while the program is running. One of the goals of Define is to be able to
express many of these constraints in a way that the compiler can know, while
compiling, whether the program is actually correct.

Note that these constraints sound very similar to the potential conditions for a
machine trigger, and in fact, constraints and trigger conditions would likely
re-use some of the same syntax.

## Similarities and Differences

The principles we have described so far give us some very powerful mechanisms
for determining if dimension points and forms are similar to each other.

Most programming languages are very strict about this and fairly limited in how
they understand similarity. For example, in a traditional language, you might
say that there is the concept of an `Animal`, and then define that a `Dog` is an
`Animal` and a `Cat` is an `Animal`. You could then have a function called
`make_sound` that an `Animal` can do, and require that any `Animal` implements
its own ability to make sound.

That is a fairly limited similarity mechanism. It requires that a `Dog` be
exactly an `Animal`. It requires that `Dog` have a function named exactly
`make_sound`. It also will require that `make_sound` return the same type and
take the same type of arguments for all implementations for all `Animal`
subclasses.

We have already defined more powerful similarity mechanisms in this document. We
could look for anything that has any particular potential form, and say that all
of those things can be used as arguments, trigger functions based on those
potential forms, etc. The language that I'm familiar with that does the closest
to this is Go, with its interfaces, but the mechanisms described above in this
document are more powerful than Go's interfaces.

So we have already gone well beyond what traditional programming languages can
do. However, there is one additional concept that does not exist in any language
today, as far as I am aware: the concept of spatial _distance_ between dimension
points.

---

> Above this point, we have laid out the concepts for a language we could call
> "Define Exactly." It is based around exact positions in space that have exact
> qualities.
>
> From this point forward, we are going quite far beyond what traditional
> programming languages handle. There may or may not be utility in implementing
> this in a programming language, today. However, describing it is necessary in
> order to fully define all the concepts required to simulate a universe, and it
> does solve some real problems in computing that are otherwise very hard to
> solve.
>
> Real universes are often not exact, but "fuzzy." When we look at something and
> call it "red," there are many wavelengths of light that would all be
> considered "red." In fact, there might be an infinite number of those
> wavelengths, all within some fuzzily-defined range that we would all agree
> "look red to me." Programming languages have traditionally been quite bad at
> expressing that concept.
>
> You may consider what is below an enhancement to Define Exactly called Define
> Approximately.

## Distance

Two things in the physical universe can be "near" (close in space) or "far"
(distant in space). This is a universal comparison mechanism that can be applied
to all objects in the physical universe. Programming languages have almost no
way of expressing this concept. Computers have a way of representing it (numbers
are close or far from each other) but there's never been a way to express this
in pure symbols in a language.

The closest concept to this that I am aware of in computing is the concept of
vector embeddings, as used in machine learning. These are lists of numbers that
represent some concept. For example, you might have a long list of numbers that
represent the concept "Queen" and another long list of numbers that represent
the concept "Woman." The numbers are designed such that if you do some special
math with them, you can "subtract" the concept "Woman" from the concept "Queen"
and get the exact numbers (or close to them) for the concept "Monarch."
Embeddings will tell you that the concept "apple" is very similar to the concept
"pear," similar (but not _as_ similar) to the concept "strawberry," and very
different from the concept "blender." Doing math on the embeddings tells you the
"distance" between all of those concepts.

Now, you can accomplish a lot of differentiation purely by looking at what
qualities a dimension point has. A red dimension point and a green dimension
point are different, we know that. The hard part is telling _how_ different they
are. A red dimension point and a pink dimension point are _similar_, but their
qualities are not identical. Pink is more like red than it is like blue.

The same issue appears with forms: you can accomplish a lot of differentiation
by saying "only look at dimension points that are shaped in a circle." But what
if you only want a _large_ circle or only a _small_ circle? Well, you could just
apply a quality that says "large" or "small." For most of the computer programs
we write today, that's actually fine. However, you have gotten away from having
a universal comparison mechanism, and perhaps there is some utility in being
able to truly model how universes actually work.

### Inventing Distance

In order to understand what distance is and how we might represent it in a
programming language, we have to first imagine a universe with no space and no
dimension points, and then build up the concept of distance from scratch. (We
can file that under "things I never thought I would have to figure out in order
to design a programming language.")

First you have a viewpoint. You can just consider that's you, looking at this
document. Then you have a single dimension point. We will call it A:

```
A
```

Then you have another one. We will call it B. All we know is that this one is
different from the other one:

```
A B
```

Now we are going to make a third one, named C. Without distance, we now just
know we have three points, all totally different from each other:

```
A B
 C
```

(It's hard to represent there in text, but imagine they all are clumped together
in a very tiny triangle---all equally distant from each other.)

Now, without assigning any qualities to A, B, or C, we want to be able to say
that A and B are more closely related than B and C. So we need some way to
express that. _Now_ we need the concept of distance (and it requires at least
three points to express it):

```
A-----1 meter-----B-----------2 meters----------C
```

Here we can now see that B and C are twice as far away from each other as A and
B are. (We use "meters" there just to make this understandable to us, the
readers, but it's really just "A and B's relationship represents the standard
unit of distance, and we define all other distances based on how far apart A and
B are.") We also can see that A and C are very different (very far away) from
each other.

Note that we could also imagine a point D between A and B and just say that that
distance is less than the distance between A and B (and somehow describe _how
much_ less):

```
A-1/3 meter-D----2/3 meter----B--------------2 meters-----------------C
```

I'm just making the point that distances can be shorter than the unit distance
between A and B, too.

That is the very simplest definition of distance: define a set of two dimension
points, and then say whether other things are closer together or further apart
than those two points, and by how much.

If distance was our _only_ mechanism of determining similarity, we could now
rank how similar each pair is, like this, from most similar to least:

1. A and D
2. D and B
3. A and B
4. B and C

And so on.

Although we had to do math to express this, it is possible that this is actually
the _basis_ of mathematics: comparing the distance between dimension points.
(Distance from A to B is 1, and then the distance from B to C has a degree of
difference compared to A and B that we can think of as "2," and so forth.
However, distances are only relevant compared to each other and can be
infinitely smaller or larger than each other.) The concept of absolute
quantities would be represented by numbers of dimension points. So we have both
finite math (dimension points) and infinite math (space).

### Spectrums

Very often, concepts exist along some sort of spectrum. Essentially, you define
two end points of a scale, and then you have potentially infinite positions
between those two points. For example, the colors black and white form a
spectrum, where black is the total absence of light, and theoretically at the
top you have total white, which is all the light there can possibly be:

```
Black------------------------------------White
```

Right in the middle, you have a theoretical perfect gray, like this:

```
Black--------------------Gray--------------------White
```

But then there are infinite "shades of gray" that could theoretically exist all
along that scale. You could pick out a point anywhere between Black and White
and say "there's a shade of gray here."

Spectrums are the primary tool we have for determining _how similar_ two
concepts are. "Dark Gray" is more like Black than it is like White, for example.
"Off White" is very similar to white, because it's very close to White on that
spectrum.

#### Total and Partial Spectrums

You could have a _total spectrum_, which would be a spectrum that has two
absolutes that represent complete opposites on either end, where there is no
further concept that could exist that's further on either side. Black and White
would be points like that. There's nothing blacker than absolute black, and
there's nothing whiter than absolute white. Total spectrums are the most
versatile and useful spectrums when you want to compare how similar two things
are to each other.

You could also have a _partial spectrum_. For example, if we just had a spectrum
that looked like:

```
Dark Gray---------Medium Gray---------Light Gray
```

There are still potentially infinite points on that spectrum, but there are
things darker than dark gray, and there are things lighter than light gray. The
danger of a partial spectrum is that you might have a concept that seems like
you _ought_ to be able to compare it to something on the partial spectrum, but
you can't. For example, we couldn't compare the color "off white" to "Light
Gray" there, because "Light Gray" is the top of that spectrum and nothing exists
beyond it. In general, it's best to avoid partial spectrums unless you don't
know or can't figure out how to define the total spectrum.

#### Spectrums as Syntax

We can imagine a syntax in a programming language to define a spectrum:

```
define a quality named Black
define a quality named White
create a spectrum<brightness> that goes from Black to White
```

And then you could add things to it:

```
define a quality named Gray
put Gray onto spectrum<brightness> between Black and White
define a quality named OffWhite
put OffWhite onto spectrum<brightness> between Gray and White, 10% away from White
define a quality named AlmostWhite
put AlmostWhite onto spectrum<brightness> between OffWhite and White, 10% away from White
```

Every distance specified is only relative to the two end points named. So the
code above would get us a scale that looked something like:

```
Black----------------------------------------------Gray---------------------------------OffWhite-------AlmostWhite-White
```

We used numbers like "10%" above, but that's just a shorthand for indicating a
position on the infinite scale between Gray and White, or another infinite scale
between OffWhite and White.

In a real computer, the number of possible positions would be limited, but not
very limited. In most computers, we could easily represent 2^64 positions
between each named concept on a scale, and then every time we add a new concept,
there's another 2^64 new potential positions between that point and the point on
its left, plus 2^64 potential positions to its right. That seems effectively
infinite for most purposes.

When we wanted to check values, instead of asking if something was exactly
OffWhite, we could specify something like:

```
position<ball> has a spectrum<brightness> between quality<Gray> and quality<AlmostWhite>
```

or perhaps:

```
position<ball> has a spectrum<brightness> within 10% of quality<OffWhite>
```

In a program, though, the syntax using named bounds is more understandable. It's
sort of hard for a programmer to reason through "within 10% of off white." So
probably you would require always defining left and right bounds on the spectrum
before checking if a value was in range.

And yes, we also need some way to indicate if we are including or excluding the
named bounds. (Like, if I pass exactly `quality<Gray>` does it count for our
earlier example?)

### Spectrums Exist in the Universe of Reflection

You will notice that above we used a new **type of name** for spectrums. Why did
we need a new type of name? Well, spectrums are used only for qualities, and
qualities live only in the universe of reflection. Thus, spectrums are a _form_
that also lives only in that universe. They aren't potential forms---they are
defined forms, but they only exist in the universe of reflection.

Even if one was going to take real objects (dimension points) and try to "rank"
them, you'd have to have some quality or set of qualities to rank them by. If I
just told you "rank pets," with no further instruction, you would simply invent
a set of qualities that you were using to rank them by (probably "how much I
like each pet").

### Types of Comparisons

Two spectrums cannot be compared to each other unless they overlap somehow.

For a specific example, let's look at a partial spectrum that we call the "color
spectrum" in the physical universe:

```
Red --- Orange --- Yellow --- Green --- Blue --- Indigo --- Violet
```

We can consider (for the sake of simplicity here) that each of those colors has
a particular "distance" between them, when we think about how similar they are
to each other, and it looks roughly like the drawing above.

That spectrum overlaps with the electromagnetic spectrum. (That is, visible
light colors are actually just a part of the electromagnetic spectrum.) So you
can compare X-rays to the wavelength of light that represents "red," because
really they are on the same larger spectrum.

But what about something like sizes? We might have a spectrum of sizes that
looks like:

```
Tiny --- Small --- Medium --- Large --- Huge --- Gargantuan
```

Color and size are not comparable to each other. I cannot tell you how similar
"Red" and "Tiny" are. We can't even say that "red is further from orange than
tiny is from small." They are not comparable. They are about as totally
different as two concepts can be.

### Dimensions

While we cannot compare "color" to "size," we can consider that one real
dimension point has both qualities: you might have a small yellow ball or a
large blue ball. You could then sort of plot how similar or different two balls
are on a graph:

```
            Gargantuan
                |
                |   B
                |
Red ------------------------ Violet
                |
                |
           Y    |
               Tiny
```

Where B is the large blue ball, and Y is the small yellow ball. That gives us an
interesting idea of how similar the two balls are. As long as the vertical axis
is always size and the horizontal axis is always color, we can compare all
objects in existence in terms of color and size.

If we had another quality, we could add another axis. And if we had a fourth
quality, we could add a fourth axis. We can't demonstrate a four-dimensional
space in the physical universe, but we can absolutely represent it
mathematically. (Vector embeddings for machine learning systems often have
thousands of dimensions.)

This is hard to think about in terms of space, but it's actually pretty easy to
think about intuitively. Imagine these objects:

- A small brown furry cat.
- A medium-sized brown hairy dog.
- A huge gray hairless elephant.

The dog and the cat there "feel" more similar to each other than they are to the
elephant, yeah? That wasn't hard to think about, and that's four dimensions. In
fact, when you thought about them, you probably thought instantaneously about
their forms and then likely many more qualities than are listed above.

#### This Might Be Wrong

Most comparisons are done simply on a single spectrum, as described earlier. In
fact, single-spectrum comparisons are the only ones we can state with certainty:
this dimension point is more or less white than another one.

I'm honestly not certain whether multi-dimensional comparisons have any real
utility in a programming language, other than in specialized applications like
vector embeddings. However, it is true that dimension points have multiple
qualities, and there does seem to be some sort of instantaneous mechanism that a
person's mind is using to determine the similarity of two objects. Maybe it's
this, and thus maybe it will end up having some use in programming.

### Associations

Now, you might imagine another spectrum for mass, like:

```
0 grams----------------------------------------------Infinite grams
```

And then you can say, "well, people tend to associate weight and size, so maybe
those two spectrums _can_ be compared to each other?" No, people only associate
weight and size because they think of objects that were a certain size and had a
certain weight. All comparisons between two spectrums occur only through
objects.

As nearly as I can determine, all logical comparisons are in fact
one-dimensional, and only manifest in multiple dimensions when applied to a real
dimension point that has multiple qualities.

They only vaguest association they have is that they are both attributes that
can be applied to a physical object (compared to something like "love" that is
just a feeling that somebody has).
