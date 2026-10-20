"""Identify CPUs that can share build artifacts compiled with target-cpu=native."""

from __future__ import annotations

import hashlib
import pathlib
import re
import subprocess
import sys

_LINUX_FIELDS = re.compile(r"vendor_id|cpu family|model|model name|stepping|flags")
_MACOS_FIELDS = re.compile(
    r"machdep\.cpu\.(brand_string|vendor|family|model|stepping|features|leaf7_features|extfeatures)"
    + r"|hw\.(cputype|cpusubtype|cpufamily|optional\..*)"
)
_FEATURE_FIELDS = {
    "flags",
    "machdep.cpu.features",
    "machdep.cpu.leaf7_features",
    "machdep.cpu.extfeatures",
}


def fingerprint(cpu_info: str, system: str) -> str:
    """Hash CPU identity and capabilities without transient machine statistics."""
    fields = {"linux": _LINUX_FIELDS, "darwin": _MACOS_FIELDS}[system]
    properties: set[str] = set()
    for line in cpu_info.splitlines():
        name, separator, value = line.partition(":")
        name = name.strip()
        if not separator or fields.fullmatch(name) is None:
            continue
        value = value.strip()
        if name in _FEATURE_FIELDS:
            value = " ".join(sorted(value.split()))
        # /proc/cpuinfo repeats identical properties for each logical CPU.
        properties.add(f"{name}: {value}")
    if not properties:
        raise ValueError("No CPU identity or feature information found")
    return hashlib.sha256("\n".join(sorted(properties)).encode()).hexdigest()


def main():
    """Print a CPU fingerprint for the CI build cache."""
    if sys.platform == "linux":
        cpu_info = pathlib.Path("/proc/cpuinfo").read_text(encoding="utf-8")
    elif sys.platform == "darwin":
        cpu_info = subprocess.run(
            ["/usr/sbin/sysctl", "-a"], check=True, capture_output=True, text=True
        ).stdout
    else:
        raise ValueError(f"Unsupported CPU fingerprint platform: {sys.platform}")
    print(f"fingerprint={fingerprint(cpu_info, sys.platform)}")


if __name__ == "__main__":
    main()
