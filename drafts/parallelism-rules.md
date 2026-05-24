# Automatic Parallelism and Paradox Detection: Design Rules

This is a draft list of design properties Define would need to guarantee in
order to detect automatic parallelism and detect paradoxes on its own, so that
normal code never has to write `wait until`.

The goal behind all of these: let the compiler figure out what can run at the
same time, and catch paradoxes, without the programmer marking it by hand.

These were worked out in a design discussion and are not yet part of any
finalized proposal.

## Checking each piece on its own

1. **Every action and operation states its full footprint up front.** It
   declares what it reads and what it writes, and that list is the whole story:
   no hidden reads, no hidden writes, no secret effects. This is what lets us
   check one piece at a time without reading the whole program.

2. **No circular references between global names** (already a rule). The "who
   uses what" graph has no loops, so checking always finishes and stays cheap.

## Catching clashes and picking order

3. **The basic position operations have strict rules.** Create needs an empty
   spot; move needs a full source and an empty target; destroy needs a full
   spot. Because of this, when two operations touch the same spot at once there
   are only two outcomes: exactly one order works (a real dependency), or no
   order works (a clash). There is never a case where two different orders both
   work but give different answers.

4. **A paradox is just "no working order exists."** Finding the order and
   finding the clash are the same cheap check.

5. **When in doubt, run things in order instead of side by side.** If we can't
   prove two things are independent, we assume one depends on the other. We lose
   a little speed, never correctness. And adding a dependency later never
   quietly changes how a program behaves.

6. **It's okay to reject a safe program if we can't prove it's safe.** For
   paradoxes we would rather wrongly reject a fine program than wrongly accept a
   broken one. (With clear errors and an escape hatch to override.)

## Conditionals

7. **We don't work out exactly which branch of an `if` runs.** That would need
   the whole program and could blow up. Instead, at every branch point we
   **merge**: keep the tightest single rule about a spot that is true no matter
   which branch ran. (One branch makes it "0-10," the other leaves it "5", so we
   keep "0-10".)

8. **We still use the one free fact: the two branches of a single `if` can't
   both happen.** That keeps ordinary `if`/`else` from being rejected. Full
   detail is tracked inside one action; only merged rules cross between actions.

9. **Presence and value use the same merging.** "Maybe created" leaves a spot
   "maybe full"; "maybe written" leaves it with the merged value rule. One
   system: each position carries what is known about it (full? what value?) at
   each point, merged at every branch.

## Values and operations

10. **Values can change in place.** A dimension point has one meaning and it can
    be overwritten; we do not force a brand-new dimension point for every new
    value. One value type per position (so we always merge values of the same
    type).

11. **Operations are pure and synchronous.** An operation only reads its inputs
    and writes its outputs: no triggering actions, no outside state, no I/O.
    Anything that does those is an action, not an operation. So operations add
    nothing new to the problem; they are plain work we order by inputs and
    outputs.

12. **Operations promise a rule about their result, not an exact value.** We do
    not need the same exact bits every time, just a true promise ("the answer is
    an integer from 0 to 10"). The compiler reasons about the promise.

13. **Operations can't fail halfway.** Anything that could go wrong (like
    overflow) is a requirement checked _before_ the operation runs, never a
    surprise mid-run. A half-finished value would be as bad as a paradox.

14. **An operation's output can't point at the same spot as another of its
    arguments.** Keeps each operation's read list and write list clean.

15. **Two kinds of clash, two rules.** Spots (full/empty) use the strict-order
    rule from #3. Values use this rule: if two things touch the same value at
    once and at least one writes, that is a clash (two reads are fine). Inside
    one straight run of code everything is already ordered, so overwriting there
    is fine; clashes only happen across triggered (parallel) actions.

## The rule that replaces `wait until`

16. **A read sees the finished writes of actions triggered before it, in code
    order.** Trigger an action that writes a spot, then read that spot, and the
    compiler automatically reads _after_ the action is done. You write nothing.

17. **For a "maybe it writes" action, wait for the action to finish, not for the
    write.** The action always finishes; the write might not. So wait for the
    action to settle, then read whatever is there, described by the merged rule
    from #7 and #9. No hanging, no race.

## What still needs an explicit statement

These are the only places an explicit `wait until` (or similar) still earns its
keep:

- Two or more actions writing the same spot where it is genuinely unclear which
  wins.
- Waiting on something you didn't cause yourself.
- Overriding an over-rejection (the escape hatch).
