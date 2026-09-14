"""Describe the build interpreter's ABI to PyO3."""

from __future__ import annotations

import struct
import sys
import sysconfig
from pathlib import Path


def main():
    """Write the interpreter configuration required by the native extension."""
    flags = "Py_GIL_DISABLED" if sysconfig.get_config_var("Py_GIL_DISABLED") else ""
    config = (
        f"implementation=CPython\nversion={sys.version_info.major}.{sys.version_info.minor}\n"
        f"shared=true\nabi3=false\npointer_width={struct.calcsize('P') * 8}\n"
        f"build_flags={flags}\nsuppress_build_script_link_lines=true\n"
    )
    _ = Path(sys.argv[1]).write_text(config)


if __name__ == "__main__":
    main()
