---
name: todo-hunter
description:
  Find TODO comments in this repo that are actionable right now, fix them in
  parallel git worktrees via subagents, and land each fix on main only after the
  user approves it. Use this skill whenever the user asks to hunt TODOs, fix
  easy or straightforward TODOs, clean up TODO debt, check what TODO fixes are
  pending, review or approve or land a todo worktree, or mentions todo-hunter —
  and also when leftover todo/* branches or todo worktrees from a previous
  session need to be inspected, landed, or cleaned up.
---

# TODO Hunter

This skill hunts for TODO comments that can actually be fixed right now, fixes
each one in its own git worktree, and lands each fix on main only after the user
has looked at it. It is specific to the Define repo's Bazel/uv setup and commit
conventions.

The whole design serves one goal: the user reviews finished, verified fixes
instead of doing the work themselves. A fix reaches them only when the full test
suite proves it out; a fixer that hits a genuine question asks it the moment it
comes up; and nothing touches main until they approve it.

## State model

Each in-flight fix is exactly:

- one branch named `todo/<slug>` with **no commits of its own** (it points at
  the `main` commit it was created from), and
- one worktree at `.todo-worktrees/<slug>` under the repo's writable root,
  holding the fix as **staged, uncommitted changes**.

Nothing is committed until the user approves the fix; the commit is the user's
decision, so it happens only during landing. A fully-staged worktree with
nothing unstaged is the "ready for review" signal; unstaged or mixed changes
mean a fixer is still working (or died mid-fix — ask the user). A `todo/*`
branch that does have a commit of its own is a landing that stopped partway
(rebase conflict or failed re-verification) — report it as such.

There is no state file. Discover state from git at the start of **every**
invocation, before doing anything else:

```
git worktree list --porcelain
git branch --list 'todo/*'
```

Report what is pending (ready for review, mid-fix, or conflicted) before
starting new work. This matters because review can happen days later in a
different session: the worktree — not the subagent, not the conversation — is
the durable artifact. **Never remove a worktree or `todo/*` branch that has not
been landed or explicitly abandoned by the user**, no matter how old it looks.

## The bar: actionable and verifiable

Do not filter TODOs by how much design work, review effort, or diff size their
fix involves. Design choices (including user-facing behavior changes),
efficiency work, and large mechanical diffs like file splits are all in scope —
the fixer makes reasonable choices and surfaces them, and review is a veto, not
an investigation. A TODO is a candidate when:

1. **It is actionable now.** Read the code around it and verify — the TODO's own
   text may be stale in either direction. For "remove/do this once X" TODOs,
   confirm X actually happened; a TODO blocked on an unbuilt feature, an
   upstream release that has not landed, or code that cannot yet exercise the
   change is not actionable, and acting on it would break things.
2. **The fix can prove itself.** The full Bazel suite, together with any tests
   the fix adds or updates, must be able to verify the result. If correctness
   could only be established by manual judgment that no test can capture, it is
   not a candidate.
3. **Questions go to the user when they arise — not before.** A fixer that is
   genuinely unsure between reasonable options asks at that moment (see
   "Questions during fixing"); choices it makes confidently are simply made,
   with the significant ones noted in its report. Do not forecast choices or
   vetoes in the candidate list.

Do not hunt in `define/spec/`, `define/proposals/`, `drafts/`, or `TODO.md`
(language-design notes, not code debt), and skip pseudo-TODOs that are not
instructions about the code (string literals in test data, prose that merely
cross-references another TODO).

## Workflow

### 1. Hunt

Scan with `rg -n "TODO"` across the repo (excluding the directories above) and
judge every hit against the bar. For any plausible candidate, actually read the
surrounding code — especially to verify preconditions and estimate the diff.
Judging from the TODO text alone produces false positives.

### 2. Present candidates

Show the user a table: proposed slug, `file:line`, the TODO text, a one-line fix
plan, and expected diff size. Include every TODO that meets the bar — there is
no cap; a backlog that has not been cleaned up in a while may legitimately
contain many candidates. The table is the entire report. Say nothing about the
TODOs you are not proposing — no exclusion lists, categories, or justifications
— and add no notes about choices the fixers will make: if a candidate hinges on
a choice, fold the proposed answer into its fix-plan cell. The pull to
demonstrate diligence with extra commentary is strong; resist it — the user
reads this list to pick work, not to audit your process. **Wait for the user to
approve or trim the list before creating any worktree.**

### 3. Fix

For each approved TODO:

1. Create its worktree from the repo root:
   `git worktree add .todo-worktrees/<slug> -b todo/<slug> main`
2. Spawn a background subagent named `todo-<slug>` whose prompt is the contents
   of `agents/fixer.md` plus the specific TODO (file, line, text, fix plan) and
   the absolute worktree path.

Spawn fixers for all approved TODOs concurrently. Do not impose a concurrency
cap; the runtime and the user control the available resources.

Spawn each fixer with the cheapest model you are confident can complete that
specific fix — a purely mechanical rename or deletion tolerates a cheaper model
than a fix that needs cross-file reasoning. When in doubt, choose the more
capable model: a wasted review cycle costs the user more than the model does.

The fixer verifies with the full test suite and leaves the fix uncommitted.
After it finishes, the orchestrator runs `git -C .todo-worktrees/<slug> add -A`
so writes to shared Git metadata happen from the primary agent rather than
requiring a subagent permission prompt. Committing is the user's decision and
happens only at landing. Because the pre-commit hooks (ruff, basedpyright)
therefore run at landing time rather than fix time, the fixer must leave a tree
that will pass them; running `//tools:format` and the full Bazel suite (which
lints via aspects and runs the `pyright_test` targets) covers this.

If the runtime cannot spawn background subagents (for example Codex), do the
fixer work yourself: work through the approved TODOs one worktree at a time,
following `agents/fixer.md` exactly, then report every worktree as ready for
review. The rest of the workflow is unchanged.

### Monitor active fixers

Keep the orchestrator's turn active while any fixer or review-revision task is
running. Use the runtime's agent-wait mechanism and continue waiting after
status updates until every active fixer has either finished or asked the user a
question. Do not yield back to the user merely because the work continues in a
background agent: once the turn ends, the orchestrator cannot proactively
deliver the completion report. Relay each completion immediately, stage the
worktree, and provide its review command before ending the turn.

### Questions during fixing

Fixers surface questions at the moment they have them, not in advance. When a
fixer sends you a question, relay it to the user immediately, tagged with the
fixer's slug (e.g.
`[split-nested-requirements-test] Duplicate the shared test header into each new file, or extract it? Recommend extracting.`),
and route the answer back to that fixer. The tag matters because several fixers
may have questions at the same time — each question must be answerable
independently. Keep every question self-contained (context, options, and the
fixer's recommendation) so the user can answer without opening the worktree.
While one fixer waits on an answer, the others keep going; never answer on the
user's behalf.

### 4. Ready for review

As each fixer finishes, relay its report and tell the user exactly how to
review, e.g.:

```
git -C .todo-worktrees/<slug> diff --cached
```

or by opening the worktree in their editor. If your runtime lets you message
running subagents, keep the fixers alive for follow-up questions — but never
block on them. If the session ends before review, that is fine; the worktree
carries the fix. If review feedback requires changes, the fixer (or you, in a
later session) adjusts the fix in the worktree, re-verifies, and re-stages.

A fixer may instead report that the TODO turned out to be blocked after all.
Relay that conceptually to the user and leave the worktree for them to inspect;
do not silently retry or escalate the fix.

### 5. Land on approval

Only when the user approves a specific fix:

1. In the main checkout: `git pull --ff-only origin main`
2. In the worktree: `git -C .todo-worktrees/<slug> add -A`, then commit with a
   message that describes the change (never "fix TODO"), following your own
   runtime's commit-attribution conventions. The pre-commit hooks run here. If
   one fails, fix the underlying issue in the worktree, re-stage, and retry —
   never `--no-verify`.
3. `git -C .todo-worktrees/<slug> rebase main`. If the rebase conflicts, abort
   it and report; do not resolve conflicts silently. (The commit stays on the
   branch — this is the stopped-partway state.)
4. **If the rebase moved the commit** (main had advanced since the fix was
   verified), re-run the full suite in the worktree before landing:
   `bazelisk test --noshow_progress --ui_event_filters=-info //...` If the
   branch was already on main's tip, the tested tree is unchanged and this
   re-run is unnecessary.
5. In the main checkout: `git merge --ff-only todo/<slug>` then
   `git push origin main`
6. Clean up: `git worktree remove .todo-worktrees/<slug>` and
   `git branch -d todo/<slug>`

### 6. Rebase the survivors

After every landing, rebase each remaining ready-for-review `todo/*` worktree
onto the new main: `git -C <worktree> rebase main --autostash`. The autostash
leaves the changes unstaged afterward, so restore the ready-for-review signal
with `git -C <worktree> add -A`. On any conflict — in the rebase itself or when
the autostash reapplies — stop, leave the worktree exactly as git left it, and
report its state; the user decides whether to respawn a fixer or abandon it.
Skip worktrees where a fixer is still actively working. Do not re-run their test
suites now; each fix re-verifies at its own landing if main has moved.

### Abandoning

Only on the user's explicit say-so: `git worktree remove --force <worktree>` and
`git branch -D todo/<slug>`.
