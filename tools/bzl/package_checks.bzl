"""Checks for Bazel package structure conventions."""

def require_subpackages(include):
    """Fail if any matching files do not belong to a child package."""
    files_outside_subpackages = native.glob(
        include = include,
        exclude = ["BUILD", "BUILD.bazel"],
        allow_empty = True,
    )
    if files_outside_subpackages:
        fail(
            "Expected all matching files to belong to child packages:\n{}".format(
                "\n".join(files_outside_subpackages),
            ),
        )
