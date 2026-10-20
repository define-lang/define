"""Project pyo3_extension macro."""

load("@rules_rust_pyo3//:defs.bzl", _pyo3_extension = "pyo3_extension")

def pyo3_extension(name, **kwargs):
    """Wraps rules_rust's `pyo3_extension` with the C++ runtime linked statically.

    The hermetic LLVM toolchain otherwise links each extension against its own
    libc++, libc++abi, and libunwind shared libraries, which only exist inside
    Bazel's output tree. An extension that needs them fails to import outside
    Bazel, such as under `uv run` or on a machine where Define is installed.
    Rust code needs only the unwinder from them, so linking them statically
    adds little and leaves the extension depending on glibc alone.

    Args:
      name: Name of the extension target.
      **kwargs: Additional arguments passed through to rules_rust's
        `pyo3_extension`.
    """
    _pyo3_extension(name = name, cc_runtime_linkage = "static", **kwargs)
