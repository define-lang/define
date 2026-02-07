# Rules for DCL Python Package

This directory contains the Python implementation of the Define Configuration
Language (DCL) parser.

## Adding New Proto Files

1. Create a new `.proto` file in the appropriate directory.
2. Use `edition = "2023";` (2024 is not yet supported by protoc).
3. Add a `package` declaration relative to the root of the repository.
4. Run gazelle to regenerate the build file.
