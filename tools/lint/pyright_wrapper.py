"""Wrapper to invoke pyright inside Bazel sandbox."""

import json
import os
import subprocess
import sys
import tempfile


def main():
    """Run pyright on specified files and write a report."""
    report_file = sys.argv[1]
    files = sys.argv[2:]

    extra_paths = os.environ.get("PYRIGHT_EXTRA_PATHS", "")
    extra_paths_list = [p for p in extra_paths.split(":") if p]

    config = {"extraPaths": extra_paths_list, "pythonVersion": "3.12"}

    # Write config in cwd so extraPaths resolve relative to exec root.
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", dir=".", delete=False, prefix=".pyrightconfig_"
    ) as config_file:
        json.dump(config, config_file)
        config_path = config_file.name

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pyright", "--project", config_path, *files],
            capture_output=True,
            text=True,
        )
    finally:
        os.unlink(config_path)

    with open(report_file, "w") as f:
        f.write(result.stdout)
        if result.stderr:
            f.write(result.stderr)

    if result.stdout:
        print(result.stdout, end="", file=sys.stderr)
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
