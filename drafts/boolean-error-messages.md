# Boolean Error Messages

Example error messages for the rules of DLP 56 (Logical Operations for Boolean
Values), DLP 59 (No Redundant Boolean Values), DLP 60 (One Order for Boolean
Logic), DLP 61 (Standard Boolean Operations), and DLP 62 (Limits on Boolean
Logic), to see what they'd be like in practice. What the compiler computes for
each one is in
[Boolean Logic in the Compiler](boolean-logic-in-the-compiler.md).

The least a message has to do is say "you wrote ___, but it should be ___
instead." Each example below has a short program, the message, and a note on
what's hard about it. The hard cases also say how the message could make the fix
obvious.

Where an example's logic could be run through the research repository's checker
(`beq program`, in `boolean_equality_checking`), the error it reports and the
program it fixes to are the ones shown here.

## Conventions

- Messages use the compiler's current format: `File "...", line N, column M`,
  the line with its indentation removed, and carets under the part that's wrong.
- Snippets show only the Operation Statements Block, and leave out the
  definition before each local view, which is always:

  ```define
  define the view<name> {
      it may only contain particles where {
          it has the value<standard:/boolean>.
      }
  }
  ```

  Line numbers in messages are for the whole file, where each interface view
  takes six lines and each local view's definition takes five, right before the
  statement that writes it. When a fix has more than one edit, every line number
  in it is for the file as it is now, before any of them.

- The standard library registers `operation<standard:/boolean/or>`,
  `operation<standard:/boolean/implies>`, `operation<standard:/boolean/equal>`,
  and `operation<standard:/boolean/majority>`. The project
  `mv:example.com:logic` registers `/boolean/xor`, the value operation in DLP
  60's examples.

## What Makes a Fix Obvious

These are the proposals that came out of writing the examples. Each one is shown
in the examples that need it.

1. **Name values by their views.** Every Boolean Statement writes a view, so
   every value has a name the programmer chose. Messages talk about
   `view<both_on>`, never about statements or positions in the logic.
2. **Say the fix as an edit.** "Replace lines A–B with", "Remove lines A–B", or
   "Move lines A–B to before line C", with the Define to write. Ranges include
   the definitions of local views that the fix removes, since a local view that
   nothing writes is an error too.
3. **Show the finished fix.** The DLPs say which error is reported, but fixing
   only that one often leaves a new error: the value operation becomes a
   wrapper, the values given to an `and` have to swap, or an input view stops
   mattering. The refactoring tool already knows where fixing ends, so the
   message reports the error the DLPs define and shows the edit that ends where
   the tool ends.
4. **Say why, with how the given values are related.** "`view<x>` is only true
   when `view<y>` is," "they're never both true," and "it's the opposite of"
   come cheaply from the truth tables the compiler already has, and they explain
   every surprising example below.
5. **Show small truth tables for matches.** A registered operation reads at most
   three views, so its table over the match's arguments has at most 8 rows. Put
   the value's table next to it, and mark the combinations that never happen.
6. **Lead with what suggests a bug.** A value that's always false, or an input
   view that stops mattering, usually means the logic is wrong, not just written
   the long way.
7. **One message for a chain.** When one error causes others, in this value
   operation or in the ones that execute it, report it where it starts, and list
   the rest of the edits under it.

## Limits

### Too Complex to Check (ROBDD Node Limit)

A mixed value operation (or action) with 21 to 512 boolean inputs whose
canonical shared ROBDD exceeds 65,536 (`2^16`) reachable non-terminal nodes. A
pure boolean value operation can never hit this error because it has at most 20
boolean input interface views and 256 boolean statements, so it always fits
inside the guaranteed truth-table floor.

This example is real: `visit_comparison_expr` in `mypy` (`mypy/checkexpr.py`,
line 3754) when its helper calls are combined into a single entangled boolean
expression, or a raw bit-level multiplier over > 20 boolean inputs where distant
inputs stay simultaneously entangled across the statements. The Define file and
its line numbers are made up. The statement where the shared decision diagram
crosses 65,536 nodes:

```define
        execute the operation<standard:/boolean/or> {
            with view<a> looking at view<left_branch_ok>.
            with view<b> looking at view<right_branch_ok>.
            with view<result> looking at view<comparison_valid>.
        }
```

```text
File "mypy/check_expr.dfn", line 412, column 21
    execute the operation<standard:/boolean/or> {
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The boolean logic of 'operation<mv:example.com:mypy:/check/visit_comparison_expr>'
exceeds the compiler's complexity limit: by this statement, the shared decision
diagram needs more than 65,536 distinct decision states.
Too many distant boolean inputs interact at once in this expression. Group
conditions that test the same inputs closer together, or split the computation
across a non-boolean boundary (such as a lookup table or separate action).
```

Hard: unlike the structural limits (more than 20 boolean input interface views,
256 boolean statements, or 512 boolean inputs), no single statement is the sole
cause, so the message points at the statement where the shared decision diagram
crossed 65,536 nodes. When an operation exceeds **256 boolean statements**
instead, splitting part of the logic into a helper value operation _does_ fix it
(each execution collapses into a single statement in the caller), whereas
hitting the 65,536-node ROBDD limit requires either grouping related conditions
closer together or breaking the entanglement across a non-boolean boundary.

### One Output View

DLP 59's sum and carry of adding two bits, in one value operation:

```define
define the operation<mv:example.com:logic:/math/half_add> {
    define the view<a> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }
    define the view<b> {
        it is read.
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }
    define the view<sum> {
        it is written.
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }
    define the view<carry> {
        it is written.
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }
    it does {
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<a>.
            with view<b> looking at view<b>.
            with view<result> looking at view<carry>.
        }
        execute the operation<mv:example.com:logic:/boolean/xor> {
            with view<a> looking at view<a>.
            with view<b> looking at view<b>.
            with view<result> looking at view<sum>.
        }
    }
}
```

```text
File "math/half_add.dfn", line 20, column 16
    define the view<carry> {
               ^^^^^^^^^^^
'operation<mv:example.com:logic:/math/half_add>' is a boolean value operation,
so it can write only one view, but it writes 'view<sum>' and 'view<carry>'.
Each of them is one execution of a registered operation, so a value operation
for each one would only be a wrapper. Remove
'operation<mv:example.com:logic:/math/half_add>', and execute them directly
where it's executed:
File "math/adder.dfn", line 40, column 21
    execute the operation<mv:example.com:logic:/math/half_add> {
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Replace lines 40-45 with:
    execute the operation<mv:example.com:logic:/boolean/xor> {
        with view<a> looking at position<x>.
        with view<b> looking at position<y>.
        with view<result> looking at position<low>.
    }
    execute the operation<standard:/boolean/and> {
        with view<a> looking at position<x>.
        with view<b> looking at position<y>.
        with view<result> looking at position<high>.
    }
```

Hard: DLP 59's own fix, one value operation for each result, leads straight to
DLP 61's wrapper error here, so the finished fix is different from the one the
rule suggests. `math/adder.dfn` is an action, so `and` there is
`operation<standard:/boolean/and>`; in a value operation it would be the logical
operation.

## Order

### Argument Order

DLP 60's example:

```define
    it does {
        execute the operation<mv:example.com:logic:/boolean/xor> {
            with view<a> looking at view<switch_a>.
            with view<b> looking at view<switch_b>.
            with view<result> looking at view<switches_differ>.
        }
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<switches_differ>.
            with view<b> looking at view<power>.
            with view<result> looking at view<lit>.
        }
    }
```

```text
File "lamp/bad_argument_order.dfn", line 38, column 37
    with view<a> looking at view<switches_differ>.
                            ^^^^^^^^^^^^^^^^^^^^^
'view<power>' has to go to 'view<a>', and 'view<switches_differ>' to 'view<b>'.
The two views of 'logical_operation<standard:/boolean/and>' are
interchangeable, so their values go in rank order, and 'view<power>' is an
interface view while 'view<switches_differ>' isn't.
Replace lines 38-39 with:
    with view<a> looking at view<power>.
    with view<b> looking at view<switches_differ>.
```

Hard: here the reason is one step away. When both values come from statements,
the first difference can be several statements back, so the message should name
it with both of its lines. When the views belong to a value operation, the
message should say that they're interchangeable because swapping them doesn't
change what it writes, since nothing in its definition says so.

### Statement Order

DLP 60's example:

```define
    it does {
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<a>.
            with view<b> looking at view<b>.
            with view<result> looking at view<both>.
        }
        execute the logical_operation<standard:/boolean/not> {
            with view<a> looking at view<both>.
            with view<result> looking at view<not_both>.
        }
        execute the operation<standard:/boolean/or> {
            with view<a> looking at view<a>.
            with view<b> looking at view<b>.
            with view<result> looking at view<either>.
        }
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<either>.
            with view<b> looking at view<not_both>.
            with view<result> looking at view<result>.
        }
    }
```

```text
File "boolean/bad_xor.dfn", line 45, column 21
    execute the operation<standard:/boolean/or> {
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The statement that writes 'view<either>' has to come before the one that writes
'view<both>', at line 26, because 'view<either>' goes to 'view<a>' of the
statement at line 50, so everything it needs comes first.
Move lines 40-49 to before line 21.
```

Hard: when several statements are out of place, one move at a time can take many
compiles. The message could list the whole order instead: "The statements have
to write, in order: `view<either>`, `view<both>`, `view<not_both>`,
`view<result>`."

## Redundant Values

### The Same as an Input View

DLP 59's example:

```define
    it does {
        execute the operation<standard:/boolean/or> {
            with view<a> looking at view<switch_a>.
            with view<b> looking at view<switch_b>.
            with view<result> looking at view<either>.
        }
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<switch_a>.
            with view<b> looking at view<either>.
            with view<result> looking at view<a_and_either>.
        }
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<power>.
            with view<b> looking at view<a_and_either>.
            with view<result> looking at view<lit>.
        }
    }
```

```text
File "lamp/bad_is_lit.dfn", line 45, column 42
    with view<result> looking at view<a_and_either>.
                                 ^^^^^^^^^^^^^^^^^^
'view<a_and_either>' is always the same as 'view<switch_a>', because
'view<either>' is true whenever 'view<switch_a>' is.
Using 'view<switch_a>' instead means 'view<switch_b>' doesn't change what
'operation<mv:example.com:logic:/lamp/bad_is_lit>' writes:
File "lamp/bad_is_lit.dfn", line 8, column 16
    define the view<switch_b> {
               ^^^^^^^^^^^^^^
What's left only executes 'logical_operation<standard:/boolean/and>' with
'view<switch_a>' and 'view<power>', so it's a wrapper. Remove
'operation<mv:example.com:logic:/lamp/bad_is_lit>', and replace its 2
executions:
    lamp/hall.dfn, line 47: execute 'logical_operation<standard:/boolean/and>'
        with 'view<a>' looking at what 'view<switch_a>' looks at, and 'view<b>'
        looking at what 'view<power>' looks at.
    lamp/porch.dfn, line 30: the same, with 'operation<standard:/boolean/and>',
        because it's an action.
```

Hard: the rule's own fix ("use `view<switch_a>`") is two edits short of a
program that compiles, and the second consequence, that `view<switch_b>` no
longer matters, is the one most likely to mean the logic is wrong. So it comes
right after the headline, before the edits.

### The Same as an Earlier Value

```define
    it does {
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<switch_on>.
            with view<b> looking at view<power>.
            with view<result> looking at view<on_and_powered>.
        }
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<power>.
            with view<b> looking at view<on_and_powered>.
            with view<result> looking at view<powered>.
        }
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<motion>.
            with view<b> looking at view<powered>.
            with view<result> looking at view<lit>.
        }
    }
```

```text
File "lamp/powered_lit.dfn", line 45, column 42
    with view<result> looking at view<powered>.
                                 ^^^^^^^^^^^^^
'view<powered>' is always the same as 'view<on_and_powered>', because
'view<on_and_powered>' is only true when 'view<power>' is:
File "lamp/powered_lit.dfn", line 35, column 42
    with view<result> looking at view<on_and_powered>.
                                 ^^^^^^^^^^^^^^^^^^^^
Remove lines 37-46, and replace line 49 with:
    with view<b> looking at view<on_and_powered>.
```

Hard: "use `view<on_and_powered>` instead" only works when the redundant value
is a local view. When it's a written interface view, the fix is to make the
earlier statement write that view, so the edit has to be spelled out, not
described.

### The Opposite of an Earlier Value

```define
    it does {
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<switch_a>.
            with view<b> looking at view<switch_b>.
            with view<result> looking at view<both_on>.
        }
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<power>.
            with view<b> looking at view<both_on>.
            with view<result> looking at view<lit_by_power>.
        }
        execute the logical_operation<standard:/boolean/not> {
            with view<a> looking at view<switch_a>.
            with view<result> looking at view<not_a>.
        }
        execute the logical_operation<standard:/boolean/not> {
            with view<a> looking at view<switch_b>.
            with view<result> looking at view<not_b>.
        }
        execute the operation<standard:/boolean/or> {
            with view<a> looking at view<not_a>.
            with view<b> looking at view<not_b>.
            with view<result> looking at view<either_off>.
        }
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<override>.
            with view<b> looking at view<either_off>.
            with view<result> looking at view<lit_by_override>.
        }
        execute the operation<standard:/boolean/or> {
            with view<a> looking at view<lit_by_power>.
            with view<b> looking at view<lit_by_override>.
            with view<result> looking at view<lit>.
        }
    }
```

```text
File "hall/light.dfn", line 79, column 42
    with view<result> looking at view<either_off>.
                                 ^^^^^^^^^^^^^^^^
'view<either_off>' is always the opposite of 'view<both_on>':
File "hall/light.dfn", line 41, column 42
    with view<result> looking at view<both_on>.
                                 ^^^^^^^^^^^^^
Use the 'not' of 'view<both_on>' instead. Remove lines 53-70, and replace lines
76-80 with:
    execute the logical_operation<standard:/boolean/not> {
        with view<a> looking at view<both_on>.
        with view<result> looking at view<either_off>.
    }
```

Hard: which of the two is reported depends on statement order. Here `both_on`
comes first, so the `or` is the one that changes. If `either_off` had come
first, the message would tell the programmer to write `both_on` as the `not` of
`either_off`, and fixing would go on to turn it back into an `and`. The finished
fix is the same either way, so the message should show that one.

### Hard Case: The Same Value Only Through an Execution

A value operation that compiles by itself:

```define
    it does {
        execute the logical_operation<standard:/boolean/not> {
            with view<a> looking at view<is_blocked>.
            with view<result> looking at view<not_blocked>.
        }
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<is_public>.
            with view<b> looking at view<not_blocked>.
            with view<result> looking at view<public_and_allowed>.
        }
        execute the operation<standard:/boolean/or> {
            with view<a> looking at view<is_member>.
            with view<b> looking at view<public_and_allowed>.
            with view<result> looking at view<result>.
        }
    }
```

And one that executes it:

```define
    it does {
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<is_member>.
            with view<b> looking at view<is_employee>.
            with view<result> looking at view<is_staff>.
        }
        execute the operation<mv:example.com:logic:/post/may_view> {
            with view<is_member> looking at view<is_member>.
            with view<is_public> looking at view<is_staff>.
            with view<is_blocked> looking at view<is_blocked>.
            with view<result> looking at view<can_view>.
        }
        execute the logical_operation<standard:/boolean/not> {
            with view<a> looking at view<is_locked>.
            with view<result> looking at view<not_locked>.
        }
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<can_view>.
            with view<b> looking at view<not_locked>.
            with view<result> looking at view<can_reply>.
        }
    }
```

```text
File "post/can_reply.dfn", line 52, column 42
    with view<result> looking at view<can_view>.
                                 ^^^^^^^^^^^^^^
'view<can_view>' is always the same as 'view<is_member>', because of what this
statement gives to 'operation<mv:example.com:logic:/post/may_view>':
File "post/can_reply.dfn", line 50, column 45
    with view<is_public> looking at view<is_staff>.
                                    ^^^^^^^^^^^^^^
'view<is_staff>' is only true when 'view<is_member>' is, and 'view<is_member>'
also goes to its 'view<is_member>'. With those values,
'operation<mv:example.com:logic:/post/may_view>' always writes what its
'view<is_member>' looks at. If 'view<is_public>' should look at something else,
that's the fix.
If not, use 'view<is_member>' instead. Then 'view<is_employee>' and
'view<is_blocked>' don't change what
'operation<mv:example.com:logic:/post/can_reply>' writes. Remove lines 8-19 and
33-53, replace line 64 with:
    with view<a> looking at view<is_member>.
and remove the values given to 'view<is_employee>' and 'view<is_blocked>' in
its executions:
    post/thread.dfn, line 118
    post/inbox.dfn, line 64
```

Hard: nothing in `can_reply` looks redundant, and `may_view` compiles, so the
programmer has no way to see it without the reason. The compiler doesn't know a
reason, only that the tables are equal.

Making it obvious: check every pair of values given to the execution for "only
true when," "never both true," and "always the opposite," which takes a few
comparisons of truth tables, and report the ones that hold, pointing at the line
that gives each one. That explains it here. It also points at the line that's
most likely the bug, since related values given to an execution usually mean the
wrong view was given. When no pair explains it, the message can fall back to a
table of the execution's input views, marking the combinations that never
happen.

### Hard Case: A Value That's Always False

```define
    it does {
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<armed>.
            with view<b> looking at view<door_open>.
            with view<result> looking at view<armed_and_open>.
        }
        execute the operation<standard:/boolean/or> {
            with view<a> looking at view<door_open>.
            with view<b> looking at view<window_open>.
            with view<result> looking at view<any_open>.
        }
        execute the logical_operation<standard:/boolean/not> {
            with view<a> looking at view<any_open>.
            with view<result> looking at view<all_closed>.
        }
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<armed_and_open>.
            with view<b> looking at view<all_closed>.
            with view<result> looking at view<sound>.
        }
    }
```

`operation<mv:example.com:logic:/alarm/siren>` executes it and gives its result,
with `view<panic>`, to `operation<standard:/boolean/or>`, and the action in
`alarm/monitor.dfn` executes that.

```text
File "alarm/should_sound.dfn", line 59, column 42
    with view<result> looking at view<sound>.
                                 ^^^^^^^^^^^
'view<sound>' can never be true: 'view<armed_and_open>' and 'view<all_closed>'
are never both true, because 'view<armed_and_open>' needs 'view<door_open>' to
be true, and 'view<all_closed>' needs it to be false.
So 'operation<mv:example.com:logic:/alarm/should_sound>' always writes false,
and none of its input views change its output view. If 'view<sound>' should
sometimes be true, the logic on lines 27-60 is wrong.
If it shouldn't, there's no way to write it, since a boolean statement can't be
given false. Remove 'operation<mv:example.com:logic:/alarm/should_sound>', and
everything its result affects:
1. alarm/siren.dfn, line 38: 'view<sound>' is always false, so 'view<siren>' is
   always the same as 'view<panic>'. Remove
   'operation<mv:example.com:logic:/alarm/siren>' too.
2. alarm/monitor.dfn, lines 52-58: replace the execution of
   'operation<mv:example.com:logic:/alarm/siren>' with:
    set the value of position<siren_on> from position<panic>.
```

Hard: the fix that follows the rules is to delete the logic and everything it
affects, one file after another, but the programmer almost certainly meant
something else, and the compiler can't tell what.

Making it obvious: lead with "can never be true," then the reason, then "if
that's wrong, the logic is wrong," and only then the plan. For an `and` that's
always false, its two values are never both true, which is the first half of the
reason. The second half comes from looking for a boolean input that one of them
needs true and the other needs false, one truth-table comparison per input. The
plan lists every file it changes, numbered, and stops where the result arrives
at an action, which can be given a literal or a position's value. `siren.dfn`
gets its own error too (its `view<sound>` is always false), but it should only
be a step in this message, not a second message that looks like a second
problem.

## Dead Statements

```define
    it does {
        execute the operation<standard:/boolean/or> {
            with view<a> looking at view<switch_a>.
            with view<b> looking at view<switch_b>.
            with view<result> looking at view<either>.
        }
        execute the operation<mv:example.com:logic:/boolean/xor> {
            with view<a> looking at view<switch_a>.
            with view<b> looking at view<switch_b>.
            with view<result> looking at view<switches_differ>.
        }
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<power>.
            with view<b> looking at view<switches_differ>.
            with view<result> looking at view<lit>.
        }
    }
```

```text
File "lamp/leftover.dfn", line 35, column 42
    with view<result> looking at view<either>.
                                 ^^^^^^^^^^^^
Nothing reads 'view<either>', so it doesn't change what
'operation<mv:example.com:logic:/lamp/leftover>' writes.
Remove lines 27-36.
```

Hard: not much. A dead statement has no place in DLP 60's order, so the compiler
shouldn't also report that `view<either>` is in the wrong place. When dead
statements read each other, one message should list all of their lines.

## Input Views That Don't Matter

```define
    it does {
        execute the logical_operation<standard:/boolean/not> {
            with view<a> looking at view<daylight>.
            with view<result> looking at view<not_daylight>.
        }
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<switch_a>.
            with view<b> looking at view<power>.
            with view<result> looking at view<on_and_powered>.
        }
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<motion>.
            with view<b> looking at view<on_and_powered>.
            with view<result> looking at view<lit_when_on>.
        }
        execute the logical_operation<standard:/boolean/not> {
            with view<a> looking at view<switch_a>.
            with view<result> looking at view<off>.
        }
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<power>.
            with view<b> looking at view<off>.
            with view<result> looking at view<off_and_powered>.
        }
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<motion>.
            with view<b> looking at view<off_and_powered>.
            with view<result> looking at view<lit_when_off>.
        }
        execute the operation<standard:/boolean/or> {
            with view<a> looking at view<lit_when_on>.
            with view<b> looking at view<lit_when_off>.
            with view<result> looking at view<either_way>.
        }
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<not_daylight>.
            with view<b> looking at view<either_way>.
            with view<result> looking at view<lit>.
        }
    }
```

```text
File "lamp/motion_lit.dfn", line 2, column 16
    define the view<switch_a> {
               ^^^^^^^^^^^^^^
'view<switch_a>' doesn't change what
'operation<mv:example.com:logic:/lamp/motion_lit>' writes: for every
combination of its other input views, 'view<lit>' is the same whether
'view<switch_a>' is true or false.
'view<lit_when_on>' (line 60) and 'view<lit_when_off>' (line 89) are its two
cases, and both of them come to 'view<power>' and 'view<motion>'.
Remove lines 2-7, and replace lines 33-105 with:
    define the view<either_way> {
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }
    execute the logical_operation<standard:/boolean/and> {
        with view<a> looking at view<power>.
        with view<b> looking at view<motion>.
        with view<result> looking at view<either_way>.
    }
    define the view<not_daylight> {
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }
    execute the logical_operation<standard:/boolean/not> {
        with view<a> looking at view<daylight>.
        with view<result> looking at view<not_daylight>.
    }
    execute the logical_operation<standard:/boolean/and> {
        with view<a> looking at view<either_way>.
        with view<b> looking at view<not_daylight>.
        with view<result> looking at view<lit>.
    }
Then remove the value given to 'view<switch_a>' in its execution at
lamp/yard.dfn, line 51.
```

Hard: the same program has a match (`view<either_way>` is `power and motion`,
removing six statements), and reporting that alone would hide the real news,
that `view<switch_a>` doesn't matter. The finished fix also moves the `not` of
`view<daylight>` after the new `and`, because the new value ranks before it, so
the edit replaces the whole block instead of a few lines.

## Literals

### A Literal Given to `and`

```define
    it does {
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<switch_on>.
            with view<b> looking at literal<standard:/boolean>"true".
            with view<result> looking at view<on>.
        }
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<power>.
            with view<b> looking at view<on>.
            with view<result> looking at view<powered_on>.
        }
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<motion>.
            with view<b> looking at view<powered_on>.
            with view<result> looking at view<lit>.
        }
    }
```

```text
File "lamp/with_literal.dfn", line 34, column 37
    with view<b> looking at literal<standard:/boolean>"true".
                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
A boolean statement can't be given a literal.
'logical_operation<standard:/boolean/and>' given true always writes its other
value, so 'view<on>' is always the same as 'view<switch_on>'.
Use 'view<switch_on>' instead. Remove lines 27-36, and replace lines 43-44
with:
    with view<a> looking at view<switch_on>.
    with view<b> looking at view<power>.
```

Hard: the literal rule and the redundant value are the same problem, so they
should be one message. Using `view<switch_on>` also swaps the two values,
because `view<switch_on>` is defined before `view<power>`.

### A Literal Given to an Execution

```define
    it does {
        execute the operation<mv:example.com:logic:/boolean/xor> {
            with view<a> looking at view<switch_a>.
            with view<b> looking at literal<standard:/boolean>"true".
            with view<result> looking at view<flipped>.
        }
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<power>.
            with view<b> looking at view<flipped>.
            with view<result> looking at view<dark>.
        }
    }
```

```text
File "lamp/is_dark.dfn", line 28, column 37
    with view<b> looking at literal<standard:/boolean>"true".
                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
A boolean statement can't be given a literal. Given true,
'operation<mv:example.com:logic:/boolean/xor>' always writes the opposite of
its other value, so 'view<flipped>' is always the opposite of
'view<switch_a>'.
Use the 'not' of 'view<switch_a>' instead. Replace lines 26-30 with:
    execute the logical_operation<standard:/boolean/not> {
        with view<a> looking at view<switch_a>.
        with view<result> looking at view<flipped>.
    }
```

Hard: here the execution comes to a `not`. When an execution given a literal
doesn't come to a single statement, the tool writes out the executed value
operation's statements, simplified, so the message has to show all of them. The
same execution in an action is fine, since actions can give literals.

## Matches

### An Ordinary Match

```define
    it does {
        execute the logical_operation<standard:/boolean/not> {
            with view<a> looking at view<switch_a>.
            with view<result> looking at view<not_a>.
        }
        execute the logical_operation<standard:/boolean/not> {
            with view<a> looking at view<switch_b>.
            with view<result> looking at view<not_b>.
        }
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<not_a>.
            with view<b> looking at view<not_b>.
            with view<result> looking at view<neither>.
        }
        execute the logical_operation<standard:/boolean/not> {
            with view<a> looking at view<neither>.
            with view<result> looking at view<either>.
        }
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<power>.
            with view<b> looking at view<either>.
            with view<result> looking at view<lit>.
        }
    }
```

```text
File "lamp/written_or.dfn", line 62, column 42
    with view<result> looking at view<either>.
                                 ^^^^^^^^^^^^
'view<either>' is always the same as 'operation<standard:/boolean/or>' with
'view<a>' looking at 'view<switch_a>' and 'view<b>' looking at
'view<switch_b>'. Execute it instead of these 4 statements.
Remove lines 27-54, and replace lines 60-63 with:
    execute the operation<standard:/boolean/or> {
        with view<a> looking at view<switch_a>.
        with view<b> looking at view<switch_b>.
        with view<result> looking at view<either>.
    }
```

Hard: nothing, which is why it's here. The replacement keeps the programmer's
own name for the value.

### An Opposite Result

DLP 56's `operation<standard:/boolean/equal>`, which no longer compiles once the
standard library registers `operation<standard:/boolean/or>`:

```define
    it does {
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<a>.
            with view<b> looking at view<b>.
            with view<result> looking at view<both>.
        }
        execute the logical_operation<standard:/boolean/not> {
            with view<a> looking at view<a>.
            with view<result> looking at view<not_a>.
        }
        execute the logical_operation<standard:/boolean/not> {
            with view<a> looking at view<b>.
            with view<result> looking at view<not_b>.
        }
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<not_a>.
            with view<b> looking at view<not_b>.
            with view<result> looking at view<neither>.
        }
        execute the operation<standard:/boolean/or> {
            with view<a> looking at view<both>.
            with view<b> looking at view<neither>.
            with view<result> looking at view<result>.
        }
    }
```

```text
File "boolean/equality.dfn", line 57, column 42
    with view<result> looking at view<neither>.
                                 ^^^^^^^^^^^^^
'view<neither>' is always the opposite of 'operation<standard:/boolean/or>'
with 'view<a>' looking at 'view<a>' and 'view<b>' looking at 'view<b>'.
Execute it, and the 'not' of its result, instead of these 3 statements.
Replace lines 31-58 with:
    define the view<either> {
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }
    execute the operation<standard:/boolean/or> {
        with view<a> looking at view<a>.
        with view<b> looking at view<b>.
        with view<result> looking at view<either>.
    }
    define the view<neither> {
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }
    execute the logical_operation<standard:/boolean/not> {
        with view<a> looking at view<either>.
        with view<result> looking at view<neither>.
    }
```

Hard: the fix needs a new local view for the `or`'s result, and the compiler has
to make up its name. Here `either` reads well, but there's no rule that gives a
good name every time.

### Hard Case: A Match Spread Over Many Lines

The `xor` from DLP 61's example, written out, with `view<not_a>` also read by a
later statement. It's the whole Operation Statements Block, with its local view
definitions, because the lines are the point:

<details>
<summary>lamp/two_ways.dfn, lines 32-124</summary>

```text
 32      it does {
 33          define the view<both> {
 34              it may only contain particles where {
 35                  it has the value<standard:/boolean>.
 36              }
 37          }
 38          execute the logical_operation<standard:/boolean/and> {
 39              with view<a> looking at view<switch_a>.
 40              with view<b> looking at view<switch_b>.
 41              with view<result> looking at view<both>.
 42          }
 43          define the view<not_both> {
 44              it may only contain particles where {
 45                  it has the value<standard:/boolean>.
 46              }
 47          }
 48          execute the logical_operation<standard:/boolean/not> {
 49              with view<a> looking at view<both>.
 50              with view<result> looking at view<not_both>.
 51          }
 52          define the view<not_a> {
 53              it may only contain particles where {
 54                  it has the value<standard:/boolean>.
 55              }
 56          }
 57          execute the logical_operation<standard:/boolean/not> {
 58              with view<a> looking at view<switch_a>.
 59              with view<result> looking at view<not_a>.
 60          }
 61          define the view<not_b> {
 62              it may only contain particles where {
 63                  it has the value<standard:/boolean>.
 64              }
 65          }
 66          execute the logical_operation<standard:/boolean/not> {
 67              with view<a> looking at view<switch_b>.
 68              with view<result> looking at view<not_b>.
 69          }
 70          define the view<neither> {
 71              it may only contain particles where {
 72                  it has the value<standard:/boolean>.
 73              }
 74          }
 75          execute the logical_operation<standard:/boolean/and> {
 76              with view<a> looking at view<not_a>.
 77              with view<b> looking at view<not_b>.
 78              with view<result> looking at view<neither>.
 79          }
 80          define the view<not_neither> {
 81              it may only contain particles where {
 82                  it has the value<standard:/boolean>.
 83              }
 84          }
 85          execute the logical_operation<standard:/boolean/not> {
 86              with view<a> looking at view<neither>.
 87              with view<result> looking at view<not_neither>.
 88          }
 89          define the view<switches_differ> {
 90              it may only contain particles where {
 91                  it has the value<standard:/boolean>.
 92              }
 93          }
 94          execute the logical_operation<standard:/boolean/and> {
 95              with view<a> looking at view<not_both>.
 96              with view<b> looking at view<not_neither>.
 97              with view<result> looking at view<switches_differ>.
 98          }
 99          define the view<lit_by_power> {
100              it may only contain particles where {
101                  it has the value<standard:/boolean>.
102              }
103          }
104          execute the logical_operation<standard:/boolean/and> {
105              with view<a> looking at view<power>.
106              with view<b> looking at view<switches_differ>.
107              with view<result> looking at view<lit_by_power>.
108          }
109          define the view<lit_by_override> {
110              it may only contain particles where {
111                  it has the value<standard:/boolean>.
112              }
113          }
114          execute the logical_operation<standard:/boolean/and> {
115              with view<a> looking at view<override>.
116              with view<b> looking at view<not_a>.
117              with view<result> looking at view<lit_by_override>.
118          }
119          execute the operation<standard:/boolean/or> {
120              with view<a> looking at view<lit_by_power>.
121              with view<b> looking at view<lit_by_override>.
122              with view<result> looking at view<lit>.
123          }
124      }
```

</details>

```text
File "lamp/two_ways.dfn", line 97, column 42
    with view<result> looking at view<switches_differ>.
                                 ^^^^^^^^^^^^^^^^^^^^^
'view<switches_differ>' is always the same as
'operation<mv:example.com:logic:/boolean/xor>' with 'view<a>' looking at
'view<switch_a>' and 'view<b>' looking at 'view<switch_b>'. Execute it instead
of the 6 statements that write 'view<both>', 'view<not_both>', 'view<not_b>',
'view<neither>', 'view<not_neither>', and 'view<switches_differ>'.
Keep lines 52-60, which write 'view<not_a>', because line 116 reads it too.
Remove lines 33-51 and 61-88, and replace lines 94-98 with:
    execute the operation<mv:example.com:logic:/boolean/xor> {
        with view<a> looking at view<switch_a>.
        with view<b> looking at view<switch_b>.
        with view<result> looking at view<switches_differ>.
    }
```

Hard: six statements over 56 lines, with one statement in the middle that has to
stay. DLP 60's order keeps a match's statements together except for statements
like `view<not_a>`, which the match needs first but something later also reads,
so this is the usual shape, not the worst one. The match's arguments, though,
can come from anywhere earlier in the value operation.

Making it obvious: name every removed statement by the view it writes, give each
range with the local view definitions it includes, and say which statement in
the middle stays and which line still reads it. An editor that understands the
message can highlight the ranges. Past two or three ranges, a diff of the
Operation Statements Block, with `-` and `+` lines, would be clearer than line
numbers.

### Hard Case: A Registered Operation the Programmer Doesn't Know About

A door unlocks with a badge and a PIN, or with a face scan and either one:

```define
    it does {
        execute the logical_operation<standard:/boolean/not> {
            with view<a> looking at view<lockdown>.
            with view<result> looking at view<not_lockdown>.
        }
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<badge>.
            with view<b> looking at view<pin>.
            with view<result> looking at view<badge_and_pin>.
        }
        execute the operation<standard:/boolean/or> {
            with view<a> looking at view<badge>.
            with view<b> looking at view<pin>.
            with view<result> looking at view<badge_or_pin>.
        }
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<face>.
            with view<b> looking at view<badge_or_pin>.
            with view<result> looking at view<face_and_one>.
        }
        execute the operation<standard:/boolean/or> {
            with view<a> looking at view<badge_and_pin>.
            with view<b> looking at view<face_and_one>.
            with view<result> looking at view<two_factors>.
        }
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<not_lockdown>.
            with view<b> looking at view<two_factors>.
            with view<result> looking at view<unlocks>.
        }
    }
```

```text
File "door/unlocks.dfn", line 80, column 42
    with view<result> looking at view<two_factors>.
                                 ^^^^^^^^^^^^^^^^^
'view<two_factors>' is always the same as
'operation<standard:/boolean/majority>' with 'view<a>' looking at 'view<badge>',
'view<b>' looking at 'view<pin>', and 'view<c>' looking at 'view<face>'.
Execute it instead of these 4 statements.
'operation<standard:/boolean/majority>' is true when at least two of its input
views are true. The standard library registers it, so every value operation has
to use it:
    badge  pin    face   | two_factors | majority
    false  false  false  | false       | false
    false  false  true   | false       | false
    false  true   false  | false       | false
    false  true   true   | true        | true
    true   false  false  | false       | false
    true   false  true   | true        | true
    true   true   false  | true        | true
    true   true   true   | true        | true
Replace lines 33-86 with:
    define the view<two_factors> {
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }
    execute the operation<standard:/boolean/majority> {
        with view<a> looking at view<badge>.
        with view<b> looking at view<pin>.
        with view<c> looking at view<face>.
        with view<result> looking at view<two_factors>.
    }
    define the view<not_lockdown> {
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }
    execute the logical_operation<standard:/boolean/not> {
        with view<a> looking at view<lockdown>.
        with view<result> looking at view<not_lockdown>.
    }
    execute the logical_operation<standard:/boolean/and> {
        with view<a> looking at view<two_factors>.
        with view<b> looking at view<not_lockdown>.
        with view<result> looking at view<unlocks>.
    }
```

Hard: the programmer wrote "a badge and a PIN, or a face scan and either one,"
and the compiler answers with an operation they've never heard of, whose views
are named `a`, `b`, and `c`. Nothing in their project mentions it, since the
standard library registers it. And the fix moves `view<not_lockdown>`: the new
`view<two_factors>` is given `view<badge>` first, which is defined before
`view<lockdown>`, so it goes to the last `and`'s `view<a>`.

Making it obvious: say in one sentence what the operation computes, say who
registers it, and show its table next to the value's, which is at most 8 rows
because registered operations read at most three views. The programmer can check
the table against what they meant without trusting the compiler. Then show the
finished block, with the reorder already done.

### Hard Case: A Surprising Spelling Given Related Values

This is DLP 61's example of a match over earlier values: "neither `x` nor `y`"
is the same as "`x` equals `y`" when `x` and `y` are never both true. A lamp is
on by hand in manual mode, and by the dark in automatic mode, and is idle when
neither is on:

```define
    it does {
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<is_manual>.
            with view<b> looking at view<switch_on>.
            with view<result> looking at view<manual_on>.
        }
        execute the logical_operation<standard:/boolean/not> {
            with view<a> looking at view<is_manual>.
            with view<result> looking at view<not_manual>.
        }
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<is_dark>.
            with view<b> looking at view<not_manual>.
            with view<result> looking at view<auto_on>.
        }
        execute the operation<mv:example.com:logic:/lamp/brightness> {
            with view<manual_on> looking at view<manual_on>.
            with view<auto_on> looking at view<auto_on>.
            with view<level> looking at view<level>.
            with view<brightness> looking at view<brightness>.
        }
        execute the logical_operation<standard:/boolean/not> {
            with view<a> looking at view<manual_on>.
            with view<result> looking at view<not_manual_on>.
        }
        execute the logical_operation<standard:/boolean/not> {
            with view<a> looking at view<auto_on>.
            with view<result> looking at view<not_auto_on>.
        }
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<not_manual_on>.
            with view<b> looking at view<not_auto_on>.
            with view<result> looking at view<idle>.
        }
    }
```

```text
File "lamp/status.dfn", line 95, column 42
    with view<result> looking at view<idle>.
                                 ^^^^^^^^^^
'view<idle>' is always the same as 'operation<standard:/boolean/equal>' with
'view<a>' looking at 'view<manual_on>' and 'view<b>' looking at
'view<auto_on>', because they're never both true: 'view<manual_on>' needs
'view<is_manual>' to be true, and 'view<auto_on>' needs it to be false.
    manual_on  auto_on | idle  | equality
    false      false   | true  | true
    false      true    | false | false
    true       false   | false | false
    true       true    | never happens
Executing 'operation<standard:/boolean/or>' and the 'not' of its result would
compute it too, but one execution comes first. Execute
'operation<standard:/boolean/equal>' instead of these 3 statements.
Remove lines 74-91, and replace lines 92-96 with:
    execute the operation<standard:/boolean/equal> {
        with view<a> looking at view<manual_on>.
        with view<b> looking at view<auto_on>.
        with view<result> looking at view<idle>.
    }
```

Hard: the replacement says "the lamp is idle when it's on by hand exactly when
it's on by the dark," which is true but reads like a mistake. The programmer
needs to see both the relation and the one combination that makes "neither" and
"equal" different, and that it never happens.

Making it obvious: the relation, the table with the impossible row marked, and a
sentence on why `equality` beats `not or`, since the programmer would otherwise
write the `or` that DLP 61's "opposite results" rule also points to.

### One Spelling for Each Value

A mixed value operation: a guest checkout is anyone without an account, and a
fee depends on it.

```define
    it does {
        execute the logical_operation<standard:/boolean/not> {
            with view<a> looking at view<has_account>.
            with view<result> looking at view<is_guest>.
        }
        execute the operation<mv:example.com:logic:/shop/fee> {
            with view<is_guest> looking at view<is_guest>.
            with view<weight> looking at view<weight>.
            with view<fee> looking at view<fee>.
        }
        execute the operation<standard:/boolean/or> {
            with view<a> looking at view<verified>.
            with view<b> looking at view<is_guest>.
            with view<result> looking at view<verified_or_guest>.
        }
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<in_stock>.
            with view<b> looking at view<verified_or_guest>.
            with view<result> looking at view<can_ship>.
        }
    }
```

```text
File "shop/checkout.dfn", line 61, column 42
    with view<result> looking at view<verified_or_guest>.
                                 ^^^^^^^^^^^^^^^^^^^^^^^
'view<verified_or_guest>' has to be written with
'operation<standard:/boolean/implies>', with 'view<a>' looking at
'view<has_account>' and 'view<b>' looking at 'view<verified>'. It computes the
same thing without being given a 'not': 'view<is_guest>' is the 'not' of
'view<has_account>'.
'operation<standard:/boolean/implies>' is false only when 'view<a>' is true and
'view<b>' is false.
Replace lines 58-62 with:
    execute the operation<standard:/boolean/implies> {
        with view<a> looking at view<has_account>.
        with view<b> looking at view<verified>.
        with view<result> looking at view<verified_or_guest>.
    }
```

Hard: nothing is removed, so it can look like the compiler is just being picky.
The message has to say which rule picks this spelling (fewest values that are a
`not`). The view's name now describes the old spelling, and only the programmer
can rename it.

## Wrappers

### A Wrapper for a Registered Operation

```define
    it does {
        execute the operation<standard:/boolean/or> {
            with view<a> looking at view<a>.
            with view<b> looking at view<b>.
            with view<result> looking at view<result>.
        }
    }
```

```text
File "lamp/either.dfn", line 1, column 12
    define the operation<mv:example.com:logic:/lamp/either> {
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
'operation<mv:example.com:logic:/lamp/either>' only executes
'operation<standard:/boolean/or>', which is registered, so it's a second name
for it.
Remove it, and execute 'operation<standard:/boolean/or>' directly in its 2
executions, with the same views:
    lamp/stairs.dfn, line 52
    lamp/garage.dfn, line 19
```

Hard: when the wrapper gives the views different names, or a different order,
the message has to say which of the wrapper's views becomes which of the
operation's, and the new executions may then need their values swapped.

### A Second Wrapper for `and`

DLP 61's example:

```define
    it does {
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<a>.
            with view<b> looking at view<b>.
            with view<result> looking at view<result>.
        }
    }
```

```text
File "boolean/both.dfn", line 21, column 21
    execute the logical_operation<standard:/boolean/and> {
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Only 'operation<standard:/boolean/and>' can be a value operation that only
executes 'logical_operation<standard:/boolean/and>'. Remove
'operation<mv:example.com:logic:/boolean/both>', and replace its executions:
    door/entry.dfn, line 88: an action, so execute
        'operation<standard:/boolean/and>'.
    door/rules.dfn, line 40: a value operation, so execute
        'logical_operation<standard:/boolean/and>'.
```

Hard: the replacement depends on where each execution is, so the message has to
say for each one.

### `and`'s Wrapper in a Value Operation

```define
    it does {
        execute the operation<standard:/boolean/and> {
            with view<a> looking at view<switch_on>.
            with view<b> looking at view<power>.
            with view<result> looking at view<on_and_powered>.
        }
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<motion>.
            with view<b> looking at view<on_and_powered>.
            with view<result> looking at view<lit>.
        }
    }
```

```text
File "lamp/uses_wrapper.dfn", line 32, column 21
    execute the operation<standard:/boolean/and> {
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
'operation<standard:/boolean/and>' is only for actions. A value operation has to
execute 'logical_operation<standard:/boolean/and>' directly.
Replace line 32 with:
    execute the logical_operation<standard:/boolean/and> {
```

Hard: nothing, as long as the value operation has another statement. With only
this one, the fix would make it a second wrapper for `and`, and the message
should go straight to the fix above.

### `and`'s Wrapper Registered

```text
File ".define/operations/booleans.defcl", line 4, column 9
    "standard:/boolean/and",
    ^^^^^^^^^^^^^^^^^^^^^^^
'operation<standard:/boolean/and>' can't be registered: it's the wrapper that
actions use for 'logical_operation<standard:/boolean/and>', which is already
registered for every value operation.
Remove line 4.
```

Hard: nothing.

## Registered Operations

### A Registered Operation's Own Definition

The project registers `/boolean/xor`, written as in DLP 60's example:

```define
    it does {
        execute the operation<standard:/boolean/or> {
            with view<a> looking at view<a>.
            with view<b> looking at view<b>.
            with view<result> looking at view<either>.
        }
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<a>.
            with view<b> looking at view<b>.
            with view<result> looking at view<both>.
        }
        execute the logical_operation<standard:/boolean/not> {
            with view<a> looking at view<both>.
            with view<result> looking at view<not_both>.
        }
        execute the logical_operation<standard:/boolean/and> {
            with view<a> looking at view<either>.
            with view<b> looking at view<not_both>.
            with view<result> looking at view<result>.
        }
    }
```

```text
File "boolean/xor.dfn", line 53, column 42
    with view<result> looking at view<result>.
                                 ^^^^^^^^^^^^
'view<result>' is always the opposite of
'operation<standard:/boolean/equal>' with 'view<a>' looking at 'view<a>' and
'view<b>' looking at 'view<b>'.
'operation<mv:example.com:logic:/boolean/xor>' is registered in
.define/operations/booleans.defcl, line 3, and a project's registered
operations have to use every one of the standard library's. Execute it, and the
'not' of its result, instead of these 4 statements.
Replace lines 21-54 with:
    define the view<same> {
        it may only contain particles where {
            it has the value<standard:/boolean>.
        }
    }
    execute the operation<standard:/boolean/equal> {
        with view<a> looking at view<a>.
        with view<b> looking at view<b>.
        with view<result> looking at view<same>.
    }
    execute the logical_operation<standard:/boolean/not> {
        with view<a> looking at view<same>.
        with view<result> looking at view<result>.
    }
```

Hard: the definition is the obvious one, and what makes it wrong is another
operation, registered by another project. The message has to say why this
definition has to use that one, and the order of registered operations is set by
what they compute, not by anything in the project's `booleans.defcl`.

### Two Registered Operations That Compute the Same Thing

```text
File ".define/operations/booleans.defcl", line 4, column 9
    "/boolean/differs",
    ^^^^^^^^^^^^^^^^^^
'operation<mv:example.com:logic:/boolean/differs>' computes the same thing as
'operation<mv:example.com:logic:/boolean/xor>', registered at line 3, so only
one of them can be registered.
Remove line 4, and the compiler will report each value operation that has to
execute 'operation<mv:example.com:logic:/boolean/xor>' instead.
```

Hard: removing either line is a fix, and the compiler can't pick, but it could
say how many executions each choice would change.

## Open Questions

- **The first error or the finished fix.** The DLPs say which error is reported,
  and these examples show the edit that ends where the refactoring tool ends.
  That edit can affect other files and remove whole value operations. Is that
  too much for one message, or should the message offer to run the tool?
- **How many messages.** DLP 59 reports the first redundant value and every dead
  statement, and DLP 61 reports the largest match. Consequences, like an input
  view that stops mattering or an execution elsewhere that becomes always false,
  are folded into one message here. Should they also count as errors of their
  own?
- **A notation for values.** Messages here only use view names and Define
  statements. Writing `switch_a and not switch_b` would be shorter and often
  clearer, but it's a second syntax for Define that only messages use.
- **Names for new views.** Some fixes need a new local view (`either`, `same`).
  The compiler can reuse the name of a view whose value it replaces, but
  otherwise it has to make one up.
- **Explanations that need more than a pair.** Relations between two given
  values explain every example here. When a redundant value needs three or more
  of the boolean inputs to explain, is a table over twenty inputs any use, or
  should the message show one combination where it would differ, and why it
  never happens?
- **Values that are always false or always true.** The rules' fix deletes them,
  but they're almost always bugs. Should the message show the deletion plan at
  all, or only the reason?
- **Order errors with other errors.** Fixing a redundant value or a match often
  changes the order the program has to be in. Should order errors wait until the
  others are fixed?
- **The ROBDD complexity limit.** Past 20 boolean inputs, fixing a 65,536-node
  ROBDD error either groups related conditions closer together or moves logic
  across a non-boolean boundary. How much should the message explain variable
  grouping vs. non-boolean refactoring?
