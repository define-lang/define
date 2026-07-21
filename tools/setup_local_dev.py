"""Sets up the local dev environment by copying Bazel-generated files into the source tree."""

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

RUNFILES_WORKSPACE = Path(__file__).absolute().parent.parent
REPO_ROOT = Path(os.environ.get("BUILD_WORKSPACE_DIRECTORY", RUNFILES_WORKSPACE))

LARK_TARGETS = [
    "//define/compiler/lark:lark_standalone_gen",
    "//defcl/python/lark:lark_standalone_gen",
]

LARK_FILES = [
    "define/compiler/lark/lark_standalone.py",
    "defcl/python/lark/lark_standalone.py",
]

BUF_VALIDATE_SRC = (
    "external/protovalidate+/proto/protovalidate/buf/validate"
    "/_virtual_imports/validate_proto/buf/validate"
)


def _bazelisk() -> str:
    """Resolve the bazelisk executable path."""
    path = shutil.which("bazelisk")
    if path is None:
        msg = "bazelisk not found on PATH"
        raise FileNotFoundError(msg)
    return path


def sync_venv(uv_location: str):
    """Synchronize the local venv with Bazel's Python interpreter."""
    uv_path = (RUNFILES_WORKSPACE / uv_location).resolve()
    uv_environment = os.environ.copy()
    _ = uv_environment.pop("VIRTUAL_ENV", None)
    _ = subprocess.run(
        [
            str(uv_path),
            "sync",
            "--frozen",
            "--project",
            str(REPO_ROOT),
            "--python",
            sys.executable,
        ],
        cwd=REPO_ROOT,
        env=uv_environment,
        check=True,
    )


def _discover_py_proto_targets() -> list[str]:
    result = subprocess.run(
        [_bazelisk(), "query", "kind(py_proto_library, //...)"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _build_targets(targets: list[str]):
    _ = subprocess.run(
        [_bazelisk(), "build", "--noshow_progress", *targets],
        cwd=REPO_ROOT,
        check=True,
    )


def _find_proto_dirs() -> set[Path]:
    dirs: set[Path] = set()
    for root, _dirnames, filenames in os.walk(REPO_ROOT / "define"):
        for f in filenames:
            if f.endswith(".proto"):
                dirs.add(Path(root))
    for root, _dirnames, filenames in os.walk(REPO_ROOT / "defcl"):
        for f in filenames:
            if f.endswith(".proto"):
                dirs.add(Path(root))
    return dirs


def _copy_file(src: Path, dest: Path):
    if dest.exists():
        dest.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
    _ = shutil.copy2(src, dest)
    dest.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)


def _copy_proto_files(proto_dirs: set[Path]):
    bazel_bin = REPO_ROOT / "bazel-bin"
    for proto_dir in sorted(proto_dirs):
        rel_dir = proto_dir.relative_to(REPO_ROOT)
        for proto_file in sorted(proto_dir.glob("*.proto")):
            stem = proto_file.stem
            for suffix in ("_pb2.py", "_pb2.pyi"):
                generated = bazel_bin / rel_dir / f"{stem}{suffix}"
                if generated.exists():
                    dest = proto_dir / f"{stem}{suffix}"
                    _copy_file(generated, dest)
                    print(dest.relative_to(REPO_ROOT))


def _copy_lark_files():
    bazel_bin = REPO_ROOT / "bazel-bin"
    for rel_path in LARK_FILES:
        src = bazel_bin / rel_path
        dest = REPO_ROOT / rel_path
        if src.exists():
            _copy_file(src, dest)
            print(rel_path)


def _copy_buf_validate():
    bazel_bin = REPO_ROOT / "bazel-bin"
    src_dir = bazel_bin / Path(BUF_VALIDATE_SRC)
    dest_dir = REPO_ROOT / "buf" / "validate"
    dest_dir.mkdir(parents=True, exist_ok=True)
    for parent in [dest_dir.parent, dest_dir]:
        init = parent / "__init__.py"
        if not init.exists():
            init.touch()
    for suffix in ("validate_pb2.py", "validate_pb2.pyi"):
        src = src_dir / suffix
        if src.exists():
            dest = dest_dir / suffix
            _copy_file(src, dest)
            print(dest.relative_to(REPO_ROOT))


def main():
    """Build Bazel-generated files and copy them into the source tree."""
    sync_venv(sys.argv[1])
    proto_targets = _discover_py_proto_targets()
    all_targets = LARK_TARGETS + proto_targets
    print(f"Building {len(all_targets)} targets...")
    _build_targets(all_targets)

    proto_dirs = _find_proto_dirs()
    _copy_proto_files(proto_dirs)
    _copy_lark_files()
    _copy_buf_validate()
    print("Done.")


if __name__ == "__main__":
    main()
