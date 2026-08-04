"""I/O helpers shared by source generators."""

import os
import tempfile
from collections.abc import Iterable
from pathlib import Path


def write_lines(output: Path, lines: Iterable[str]) -> int:
    """Atomically write lines with Unix newlines and return the line count."""
    line_count = 0
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=output.parent, delete=False
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            for line in lines:
                _ = temporary_file.write(line)
                _ = temporary_file.write("\n")
                line_count += 1
        os.replace(temporary_path, output)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return line_count
