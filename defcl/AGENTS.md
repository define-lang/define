# Rules for DCL Python Package

This directory contains the Python implementation of the Define Configuration
Language (DCL) parser.

## Adding New Proto Files

1. Create a new `.proto` file in the appropriate directory.
2. Add a `package` declaration relative to the root of the repository.

## Formatting DCL Files

DCL allows exactly one layout. To fix the layout of DCL files, run:

`bazelisk run --noshow_progress --ui_event_filters=-info --run_under="cd $PWD &&" //defcl/rust/formatter:defclfmt -- FILE...`

It rewrites each file in place and prints the syntax errors that it cannot fix,
such as an empty message value. It does not check the file against its schema,
so it does not reorder fields.
