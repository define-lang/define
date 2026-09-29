"""Shared constants for the Define compiler."""

from __future__ import annotations

import pathlib
from typing import Final

from define.compiler.data_structures import define_path

DEFINE_FILE_SUFFIX: Final = ".dfn"
DOCS_ROOT: Final = "https://github.com/mkanat/define/define/docs"
# This is the length of: `File "a.dfn", line 1, column 1` (the shortest possible header)
ERROR_DIVIDER = "\n" + ("-" * 31) + "\n"
PROJECT_ROOT: Final = define_path.DefinePathFromPosix(pathlib.PurePosixPath("."))
NON_FILESYSTEM_PATH: Final = define_path.InvalidDefinePath("<string>")
DEFAULT_MULTIVERSE: Final = "local"
DEFAULT_OUTPUT_DIR: Final = pathlib.Path("define-out")
STANDARD_UNIVERSE: Final = "standard"
# Every project can reference the standard universe without configuring it, so
# its root lies outside every project, and its path is absolute.
# TODO: Load the standard universe from the Define Standard Library once it
# exists.
STANDARD_LIBRARY_ROOT: Final = define_path.DefinePathFromPosix(
    pathlib.PurePosixPath(
        (pathlib.Path(__file__).parent.parent / "standard").as_posix()
    )
)
# The standard universe's files in define/standard define these encodings.
BOOLEAN_ASCII_ENCODING: Final = f"encoding<{STANDARD_UNIVERSE}:/boolean/ascii>"
DECIMAL_ASCII_ENCODING: Final = f"encoding<{STANDARD_UNIVERSE}:/number/decimal/ascii>"
# TODO: Read value encodings from encodings configuration (DLP 47) once it
# exists.
BUILT_IN_VALUE_ENCODINGS: Final = {
    f"value<{STANDARD_UNIVERSE}:/boolean>": BOOLEAN_ASCII_ENCODING,
    f"value<{STANDARD_UNIVERSE}:/number/rational>": DECIMAL_ASCII_ENCODING,
}
# The path, in the standard universe, of the Encoding Operation that performs
# each Value Operation for the encodings of its input views.
# TODO: Read Encoding Operation associations from configuration (DLP 48) once
# it exists.
BUILT_IN_ENCODING_OPERATIONS: Final = {
    f"operation<{STANDARD_UNIVERSE}:/number/rational/absolute_value>": (
        "/number/decimal/ascii/absolute_value"
    ),
    f"operation<{STANDARD_UNIVERSE}:/number/rational/add>": (
        "/number/decimal/ascii/infix_add"
    ),
    f"operation<{STANDARD_UNIVERSE}:/number/rational/ceiling>": (
        "/number/decimal/ascii/ceiling"
    ),
    f"operation<{STANDARD_UNIVERSE}:/number/rational/decrement>": (
        "/number/decimal/ascii/infix_decrement"
    ),
    f"operation<{STANDARD_UNIVERSE}:/number/rational/floor>": (
        "/number/decimal/ascii/floor"
    ),
    f"operation<{STANDARD_UNIVERSE}:/number/rational/increment>": (
        "/number/decimal/ascii/infix_increment"
    ),
    f"operation<{STANDARD_UNIVERSE}:/number/rational/maximum>": (
        "/number/decimal/ascii/maximum"
    ),
    f"operation<{STANDARD_UNIVERSE}:/number/rational/minimum>": (
        "/number/decimal/ascii/minimum"
    ),
    f"operation<{STANDARD_UNIVERSE}:/number/rational/multiply>": (
        "/number/decimal/ascii/infix_multiply"
    ),
    f"operation<{STANDARD_UNIVERSE}:/number/rational/negate>": (
        "/number/decimal/ascii/prefix_negate"
    ),
    f"operation<{STANDARD_UNIVERSE}:/number/rational/subtract>": (
        "/number/decimal/ascii/infix_subtract"
    ),
    f"operation<{STANDARD_UNIVERSE}:/number/rational/truncate>": (
        "/number/decimal/ascii/truncate"
    ),
}
