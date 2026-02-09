"""Entry point for the Define compiler."""

import sys
from pathlib import Path

import lark

from define.compiler import driver, parser_exceptions


def main() -> int:
    """Run the Define compiler CLI."""
    if len(sys.argv) < 2:
        print("Usage: main <file.def>", file=sys.stderr)
        return 2  # Usual error code for bad usage.

    d = driver.Driver()
    try:
        diagnostics, source = d.validate_file(Path(sys.argv[1]))
    except parser_exceptions.DefineSyntaxError as e:
        print(str(e), file=sys.stderr)
        return 1
    except lark.exceptions.UnexpectedInput as e:
        print(str(e), file=sys.stderr)
        return 1

    if diagnostics:
        source_lines = source.splitlines()
        for diagnostic in diagnostics:
            print(diagnostic.format(source_lines), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
