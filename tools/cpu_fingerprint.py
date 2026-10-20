"""Identify CPUs that can share build artifacts compiled with target-cpu=native."""

from __future__ import annotations

import hashlib
import pathlib
import re
import shutil
import subprocess
import sys

_LINUX_FIELDS = re.compile(r"vendor_id|cpu family|model|model name|stepping|flags")
_MACOS_FIELDS = re.compile(
    r"machdep\.cpu\.(brand_string|vendor|family|model|stepping|features|leaf7_features|extfeatures)"
    + r"|hw\.(cputype|cpusubtype|cpufamily|optional\..*)"
)
_WINDOWS_FIELDS = re.compile(r"target-cpu|target-feature")
_FEATURE_FIELDS = {
    "flags",
    "machdep.cpu.features",
    "machdep.cpu.leaf7_features",
    "machdep.cpu.extfeatures",
}


def fingerprint(cpu_info: str, system: str) -> str:
    """Hash CPU identity and capabilities without transient machine statistics."""
    fields = {
        "linux": _LINUX_FIELDS,
        "darwin": _MACOS_FIELDS,
        "win32": _WINDOWS_FIELDS,
    }[system]
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


def windows_cpu_info() -> str:
    """Identify the native CPU and features available to LLVM on Windows."""
    clang = shutil.which("clang")
    if clang is None:
        raise FileNotFoundError("clang is required to identify the Windows CPU")
    # Windows runners include Clang. Its native target detection accounts for
    # OS-enabled instructions, unlike the processor name alone.
    command = subprocess.run(
        [clang, "-###", "-march=native", "-x", "c", "-c", "-"],
        input="",
        check=True,
        capture_output=True,
        text=True,
    ).stderr
    properties: list[tuple[str, str]] = []
    for match in re.finditer(r'"-(target-cpu|target-feature)" "([^"]+)"', command):
        properties.append((match.group(1), match.group(2)))
    if not any(name == "target-cpu" for name, _ in properties):
        raise ValueError("Clang did not report the native CPU")
    if not any(name == "target-feature" for name, _ in properties):
        raise ValueError("Clang did not report native CPU features")
    return "\n".join(f"{name}: {value}" for name, value in properties)


def main():
    """Print a CPU fingerprint for the CI build cache."""
    if sys.platform == "linux":
        cpu_info = pathlib.Path("/proc/cpuinfo").read_text(encoding="utf-8")
    elif sys.platform == "darwin":
        cpu_info = subprocess.run(
            ["/usr/sbin/sysctl", "-a"], check=True, capture_output=True, text=True
        ).stdout
    elif sys.platform == "win32":
        cpu_info = windows_cpu_info()
    else:
        raise ValueError(f"Unsupported CPU fingerprint platform: {sys.platform}")
    print(f"fingerprint={fingerprint(cpu_info, sys.platform)}")


if __name__ == "__main__":
    main()
