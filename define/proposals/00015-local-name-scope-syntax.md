# Define Language Proposal 15: Local Name Scope Syntax

- **Author:** Max Kanat-Alexander
- **Status:** Draft
- **Date Proposed:** January 9, 2026
- **Date Finalized:**

## Problems

As defined in [DLP 5](00005-global-names-local-names-and-scopes.md), we need
syntax for creating local name scopes.

Scopes need to be visually distinct. Programmers need to be able to clearly see
what code is in what scope. This is especially important when reading through
longer programs or when scopes are deeply nested.

## Solution

We will use curly braces `{` and `}` to delimit local name scopes. Any statement
that can create a local name scope (meaning: any definition where it is possible
to define new things inside of that definition, like a quality that can define
triggers, for example) will create one within those curly braces.

The curly brace that starts a scope must be on the same line as the statement
that creates the scope, exactly one space away from the statement. The ending
curly brace must be on a line that contains only that curly brace and
whitespace, aligned with the start of the statement that opened the scope. This
enables easier parsing even with unofficial parsers (like grep or a regex).

For example:

```
define the quality<mv:example.com:example:/drawings/graph> {
    define the potential_form<coordinate> {
        define the position<x>.
        define the position<y>.
    }
}
```

In this example, `quality<mv:example.com:example:/drawings/graph>` creates a
local name scope that contains `potential_form<coordinate>`, which in turn
creates its own local name scope containing `position<x>` and `position<y>`.

The only part of that syntax that is "real" in this proposal is `{` and `}`.

## A Real Program

See above.

## Why This is the Right Solution

Curly braces provide the clearest visual boundaries that make scope nesting
immediately obvious to programmers.

They are the choice that most modern programming languages have chosen due to
ease of parsing and that they do the best job at creating visually distinct
boundaries for scopes. In this case, we agree with all of those programming
languages: there isn't a better choice.

### Alternatives Discarded

#### Significant Whitespace (Python-style)

The main alternative considered was significant whitespace, similar to Python's
indentation-based blocks. While this syntax is more intuitive to read for simple
cases, it becomes difficult to understand when blocks are deeply nested and very
long. I have written a lot of Python, and even I lose track of which indentation
level corresponds to which scope sometimes.

#### BEGIN / END Keywords

Older programming languages tended to use `BEGIN` and `END`, like
`BEGIN FUNCTION` and `END FUNCTION`. Even though most of define is verbose, I
think that these words actually don't do as good of a job at creating visual
"space" as the curly braces do. I also think they are distracting to a
programmer just trying to read a program.

#### IF / FI

Some languages use the keyword in reverse to close a statement,like closing an
`if` statement with `fi`. Given that our keywords are long, this would be
extremely awkward. Also, all scopes are saying the same thing: here's a new
local name scope. There's no reason to have separate words for each one.

#### Other Symbols: [], (), <>

Angle brackets `<>` are already used for names (e.g., `quality<name>`).

Parentheses `()` tend to be used for grouping logical expressions in programs.
Functional languages do use them for scopes, but I'd like to avoid the same
symbols having multiple meanings as much as possible.

Square brackets `[]` were used to create scopes in Smalltalk, but most
programmers expect them to represent something like array accesses, these days.
The advantage they have is that they don't require pressing Shift on a standard
US keyboard to write them, but I'm not that concerned about that.

## Forward Compatibility

The use of curly braces for scopes is unambiguous and deterministic. Any code
using curly braces for scopes can be deterministically refactored to use
alternative syntax in the future if needed, since the scope boundaries are
explicitly marked. The compiler can always identify exactly where each scope
begins and ends, making any future syntax changes straightforward to implement
through automated refactoring.

## Refactoring Existing Systems

There are no existing systems. If systems did exist without explicit scope
delimiters, it would be pretty hard to refactor them without some sort of scope
delimiter defined. But if they had other scope delimiters, like significant
whitespace, we could deterministically refactor them easily into this syntax.
