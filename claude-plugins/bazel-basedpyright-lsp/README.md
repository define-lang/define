# bazel-basedpyright-lsp

Claude Code LSP plugin that provides Python code intelligence (go-to-definition,
find-references, hover, diagnostics) using the Bazel-hermetic basedpyright
language server.

## How it works

This plugin runs `tools/basedpyright-langserver`, a wrapper script that:

1. Builds `//:basedpyright-langserver` via Bazel (using the hermetic Node.js and
   basedpyright npm package).
2. Launches the built language server with `--stdio`.

## Prerequisites

- Bazel (via bazelisk) must be installed and working.
- The repo must have been built at least once (`bazelisk build //...`).
