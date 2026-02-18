"""Update toolchain versions that Renovate cannot handle.

Handles Go SDK version (MODULE.bazel + go.mod), buf toolchain
version + SHA256 (MODULE.bazel), Node.js toolchain version
(MODULE.bazel), and multitool lockfile (ruff, uv).

Usage:
    uv run tools/update_toolchains.py
"""

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import cast

import requests

# Paths relative to the repository root.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_MODULE_BAZEL = _REPO_ROOT / "MODULE.bazel"
_GO_MOD = _REPO_ROOT / "defcl" / "buf" / "go.mod"

_GO_DL_API = "https://go.dev/dl/?mode=json"
_BUF_LATEST_API = "https://api.github.com/repos/bufbuild/buf/releases/latest"
_BUF_SHA256_URL = "https://github.com/bufbuild/buf/releases/download/{tag}/sha256.txt"
_NODE_DL_API = "https://nodejs.org/dist/index.json"


def _fetch_latest_go_version() -> str:
    """Fetch the latest stable Go version from go.dev."""
    resp = requests.get(_GO_DL_API, timeout=30)
    resp.raise_for_status()
    releases = cast("list[dict[str, str]]", json.loads(resp.text))
    # First entry is the latest stable release, e.g. "go1.25.7".
    version_str = releases[0]["version"]
    return version_str.removeprefix("go")


def _fetch_latest_buf_release() -> tuple[str, str]:
    """Fetch the latest buf release tag and SHA256 of sha256.txt.

    Returns:
        A (tag, sha256_digest) tuple where tag is like "v1.65.0".
    """
    resp = requests.get(_BUF_LATEST_API, timeout=30)
    resp.raise_for_status()
    release = cast("dict[str, str]", json.loads(resp.text))
    tag = release["tag_name"]

    sha_resp = requests.get(_BUF_SHA256_URL.format(tag=tag), timeout=30)
    sha_resp.raise_for_status()
    digest = hashlib.sha256(sha_resp.content).hexdigest()
    return tag, digest


def _update_go_sdk(latest: str) -> bool:
    """Update Go SDK version in MODULE.bazel and go.mod.

    Returns True if any file was modified.
    """
    changed = False

    # MODULE.bazel: go_sdk.download(version = "X.Y.Z")
    text = _MODULE_BAZEL.read_text()
    new_text = re.sub(
        r'(go_sdk\.download\(version\s*=\s*")[^"]+(")',
        rf"\g<1>{latest}\2",
        text,
    )
    if new_text != text:
        _ = _MODULE_BAZEL.write_text(new_text)
        print(f"  MODULE.bazel: go_sdk version -> {latest}")
        changed = True

    # go.mod: go X.Y.Z
    go_mod_text = _GO_MOD.read_text()
    new_go_mod = re.sub(
        r"^(go\s+)\S+",
        rf"\g<1>{latest}",
        go_mod_text,
        count=1,
        flags=re.MULTILINE,
    )
    if new_go_mod != go_mod_text:
        _ = _GO_MOD.write_text(new_go_mod)
        print(f"  defcl/buf/go.mod: go directive -> {latest}")
        changed = True

    return changed


def _fetch_latest_node_lts_version() -> str:
    """Fetch the latest LTS Node.js version from nodejs.org.

    Returns the version as "major.minor.0" since rules_nodejs only
    includes .0 patch versions in its known-version list.
    """
    resp = requests.get(_NODE_DL_API, timeout=30)
    resp.raise_for_status()
    releases = cast("list[dict[str, object]]", json.loads(resp.text))
    # Releases are newest-first; lts is a codename string when active, False otherwise.
    for release in releases:
        if release.get("lts"):
            version_str = cast("str", release["version"]).lstrip("v")
            major, minor, _ = version_str.split(".")
            return f"{major}.{minor}.0"
    raise RuntimeError("No LTS release found in Node.js dist index")


def _update_node_toolchain(version: str) -> bool:
    """Update Node.js toolchain version in MODULE.bazel.

    Returns True if the file was modified.
    """
    text = _MODULE_BAZEL.read_text()
    new_text = re.sub(
        r'(node\.toolchain\(node_version\s*=\s*")[^"]+(")',
        rf"\g<1>{version}\2",
        text,
    )
    if new_text != text:
        _ = _MODULE_BAZEL.write_text(new_text)
        print(f"  MODULE.bazel: node_version -> {version}")
        return True
    return False


def _update_buf_toolchain(tag: str, sha256: str) -> bool:
    """Update buf toolchain version and SHA256 in MODULE.bazel.

    Returns True if the file was modified.
    """
    text = _MODULE_BAZEL.read_text()
    original = text

    text = re.sub(
        r'(buf\.toolchains\(\s*sha256\s*=\s*")[^"]+(")',
        rf"\g<1>{sha256}\2",
        text,
    )
    text = re.sub(
        r'(buf\.toolchains\([^)]*version\s*=\s*")[^"]+(")',
        rf"\g<1>{tag}\2",
        text,
    )

    if text != original:
        _ = _MODULE_BAZEL.write_text(text)
        print(f"  MODULE.bazel: buf version -> {tag}, sha256 -> {sha256[:16]}...")
        return True
    return False


def _update_multitool() -> None:
    """Run multitool update via Bazel to refresh ruff and uv versions."""
    lockfile = _REPO_ROOT / "tools" / "multitool.lock.json"
    cmd = [
        "bazelisk",
        "run",
        "@multitool//tools/multitool:cwd",
        "--",
        "--lockfile",
        str(lockfile),
        "update",
    ]
    print(f"  Running: {' '.join(cmd)}")
    _ = subprocess.run(cmd, check=True)


def main() -> int:
    """Update all toolchains and report results."""
    print("Checking Go SDK...")
    latest_go = _fetch_latest_go_version()
    if _update_go_sdk(latest_go):
        print(f"  Updated Go SDK to {latest_go}")
    else:
        print(f"  Already at latest ({latest_go})")

    print("\nChecking buf toolchain...")
    buf_tag, buf_sha = _fetch_latest_buf_release()
    if _update_buf_toolchain(buf_tag, buf_sha):
        print(f"  Updated buf to {buf_tag}")
    else:
        print(f"  Already at latest ({buf_tag})")

    print("\nChecking Node.js toolchain...")
    latest_node = _fetch_latest_node_lts_version()
    if _update_node_toolchain(latest_node):
        print(f"  Updated Node.js to {latest_node}")
    else:
        print(f"  Already at latest ({latest_node})")

    print("\nUpdating multitool (ruff, uv)...")
    _update_multitool()
    print("  Done.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
