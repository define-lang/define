---
name: coverage
description:
  Run this repository's coverage workflow. Do not trigger implicitly, only
  trigger when explicitly invoked.
---

# Coverage

## Produce the report

1. Run:

   ```text
   bazelisk coverage --noshow_progress --ui_event_filters=-info --combined_report=lcov //...
   ```

2. Run:

   ```text
   bazelisk run --noshow_progress --ui_event_filters=-info //tools:analyze_coverage
   ```

   The analyzer has `--help` if needed.

3. Create `htmlcov/coverage_report.html` from the analyzer output. Include every
   reported branch and preserve its classification, branch source, uncovered
   outcome when present, and uncovered destination. The `htmlcov/` directory is
   ignored by Git.

4. Put actionable branches in the main review section. Give every actionable
   branch:

   - A checkbox.
   - An optional comments field.
   - Its absolute source-file path in a read-only text field.
   - A Copy button that copies the absolute path.
   - A compact syntax-highlighted source snippet with line numbers and enough
     surrounding code to understand the branch. Visually distinguish the branch
     source line and, when it is in the same file, the uncovered destination
     line.

   Put low-value final-case non-match branches in a separate collapsed section.
   Show their paths, analyzer details, and source snippets, but do not give them
   checkboxes or comments fields and do not include them in the submission.
   Explicit-exit-only branches omitted by the analyzer do not appear in the
   report.

   Keep the report self-contained. Embed the syntax-highlighting styles and any
   required code in the HTML instead of loading a library from the network.
   HTML-escape every path, analyzer value, source line, and comment inserted
   into markup. Serialize data passed to JavaScript rather than interpolating
   source text into script code.

5. Make Submit send a JSON object containing the selected branches and their
   comments to the relative URL `submit`, so the browser retains the random
   access path printed by the server. The server saves it as
   `htmlcov/coverage_report_selection.json`.

6. Run the report server:

   ```text
   bazelisk run --noshow_progress --ui_event_filters=-info //tools:serve_report
   ```

   Open the URL printed by the server in the user's browser. The operating
   system chooses the port, and the server exits automatically after saving a
   successful submission.

7. Tell the user to submit the form and then say it was submitted.

## Investigate submitted items

1. Read `htmlcov/coverage_report_selection.json` after the user reports
   submission.
2. Investigate exactly the selected branches, respecting any comments.
3. For each reachable behavior, try to cover it through public, real behavior:
   - Prefer an existing testdata-driven suite or another test that compiles,
     validates, or executes real Define source.
   - For compiler and validator behavior, do not add direct tests of private
     implementation details merely to execute a branch.
   - If the path is unreachable or exhaustive fallthrough, explain why and do
     not manufacture an artificial test.
4. Run focused validation while iterating.
5. Run the coverage command and analyzer command again for final verification.
   Confirm whether every selected branch disappeared or was classified as
   unreachable.
