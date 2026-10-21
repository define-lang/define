"""Describe the build interpreter's ABI to PyO3."""

from __future__ import annotations

import argparse
import struct
import sys
import sysconfig
from pathlib import Path
from typing import cast


def main():
    """Write the interpreter configuration required by the native extension."""
    parser = argparse.ArgumentParser()
    _ = parser.add_argument("output", type=Path)
    _ = parser.add_argument("--windows-target", action="store_true")
    args = parser.parse_args()
    output = cast("Path", args.output)
    windows_target = cast("bool", args.windows_target)

    flags = "Py_GIL_DISABLED" if sysconfig.get_config_var("Py_GIL_DISABLED") else ""
    config = (
        f"implementation=CPython\nversion={sys.version_info.major}.{sys.version_info.minor}\n"
        f"shared=true\nabi3=false\npointer_width={struct.calcsize('P') * 8}\n"
        f"build_flags={flags}\n"
    )
    if windows_target:
        # Windows extension modules must link the Python DLL. Given its name,
        # pyo3-ffi links it with raw-dylib, so no import library is needed.
        abi_suffix = "t" if flags else ""
        config += (
            f"lib_name=python{sys.version_info.major}{sys.version_info.minor}{abi_suffix}\n"
            "suppress_build_script_link_lines=false\n"
        )
    else:
        config += "suppress_build_script_link_lines=true\n"
    _ = output.write_text(config, encoding="utf-8")


if __name__ == "__main__":
    main()
