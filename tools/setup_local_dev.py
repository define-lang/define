"""Sets up the local dev environment by copying Bazel-generated files into the source tree and configuring git."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

from tools import runfiles

REPO_ROOT = Path(os.environ["BUILD_WORKSPACE_DIRECTORY"])

LARK_TARGETS = [
    "//defcl/python/lark:lark_standalone_gen",
]

LARK_FILES = [
    "defcl/python/lark/lark_standalone.py",
]

# Relative to the git directory. tools/agent_hooks/shell_command_checks.py reads
# it by the same name.
SUCCESSFUL_RUN_STAMP = "setup-local-dev-stamp"

# rust-analyzer reads generated Rust sources from the source tree. They are in
# the order of their command-line arguments.
GENERATED_RUST_SOURCES = [
    "define/compiler/parsing/native/ast.rs",
    "define/compiler/parsing/native/parser_diagnostics.rs",
    "define/compiler/parsing/native/syntax_errors.rs",
]

# Type checkers and editors read the stubs of native extensions whose stubs
# Bazel generates from the source tree. They are in the order of their
# command-line arguments.
GENERATED_PYTHON_STUBS = [
    "define/compiler/codegen/literal/python/renderer.pyi",
]

# Native extensions, by the package that each is copied into, in the order of
# their command-line arguments.
NATIVE_EXTENSION_PACKAGES = [
    "define/compiler/codegen/literal/python",
    "define/compiler/parsing/native",
]

# re2 makes only its py_library public, so its files are found by their path in
# that library's runfiles, using re2's apparent repository name.
RE2_PYTHON_PACKAGE = "re2/python"

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


def _git() -> str:
    path = shutil.which("git")
    if path is None:
        msg = "git not found on PATH"
        raise FileNotFoundError(msg)
    return path


def sync_venv(uv_path: Path):
    """Synchronize the local venv with Bazel's Python interpreter."""
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


def _venv_executable(name: str) -> Path:
    if os.name == "nt":
        return REPO_ROOT / ".venv" / "Scripts" / f"{name}.exe"
    return REPO_ROOT / ".venv" / "bin" / name


def _copy_re2():
    site_packages_result = subprocess.run(
        [
            str(_venv_executable("python")),
            "-c",
            "import sysconfig; print(sysconfig.get_path('platlib'))",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    site_packages = Path(site_packages_result.stdout.strip())
    re2_source = runfiles.resolve(f"{RE2_PYTHON_PACKAGE}/re2.py")
    _copy_file(re2_source, site_packages / "re2.py")

    extension_name = "_re2.pyd" if os.name == "nt" else "_re2.so"
    extension_source = runfiles.resolve(f"{RE2_PYTHON_PACKAGE}/{extension_name}")
    _copy_file(extension_source, site_packages / extension_source.name)
    print((site_packages / "re2.py").relative_to(REPO_ROOT))
    print((site_packages / extension_source.name).relative_to(REPO_ROOT))


def _configure_git_blame():
    # git has no default file of revisions for blame to skip, so each clone
    # names one.
    _ = subprocess.run(
        [_git(), "config", "blame.ignoreRevsFile", ".git-blame-ignore-revs"],
        cwd=REPO_ROOT,
        check=True,
    )


def _install_git_hooks():
    _ = subprocess.run(
        [str(_venv_executable("prek")), "install"], cwd=REPO_ROOT, check=True
    )


def _record_successful_run():
    # Agent hooks compare source times against this file to decide whether the
    # generated files may be out of date. The git directory is per worktree.
    stamp_path = subprocess.run(
        [_git(), "rev-parse", "--git-path", SUCCESSFUL_RUN_STAMP],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    (REPO_ROOT / stamp_path).touch()


def main():
    """Build Bazel-generated files, copy them into the source tree, and configure git."""
    uv_location, *locations = sys.argv[1:]
    generated_rust_locations = locations[: len(GENERATED_RUST_SOURCES)]
    generated_stub_locations = locations[
        len(GENERATED_RUST_SOURCES) : len(GENERATED_RUST_SOURCES)
        + len(GENERATED_PYTHON_STUBS)
    ]
    native_extension_locations = locations[
        len(GENERATED_RUST_SOURCES) + len(GENERATED_PYTHON_STUBS) :
    ]
    sync_venv(runfiles.resolve(uv_location))
    proto_targets = _discover_py_proto_targets()
    all_targets = [*LARK_TARGETS, *proto_targets]
    print(f"Building {len(all_targets)} targets...")
    _build_targets(all_targets)

    proto_dirs = _find_proto_dirs()
    _copy_proto_files(proto_dirs)
    _copy_lark_files()
    _copy_buf_validate()
    _copy_re2()
    for package, location in zip(
        NATIVE_EXTENSION_PACKAGES, native_extension_locations, strict=True
    ):
        extension_source = runfiles.resolve(location)
        extension_path = Path(package) / extension_source.name
        _copy_file(extension_source, REPO_ROOT / extension_path)
        print(extension_path)
    for source, location in zip(
        GENERATED_RUST_SOURCES, generated_rust_locations, strict=True
    ):
        _copy_file(runfiles.resolve(location), REPO_ROOT / source)
        print(source)
    for stub, location in zip(
        GENERATED_PYTHON_STUBS, generated_stub_locations, strict=True
    ):
        _copy_file(runfiles.resolve(location), REPO_ROOT / stub)
        print(stub)
    _configure_git_blame()
    _install_git_hooks()
    _record_successful_run()
    print("Done.")


if __name__ == "__main__":
    main()
