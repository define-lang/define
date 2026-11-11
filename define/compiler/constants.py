"""Shared constants for the Define compiler."""

from __future__ import annotations

import pathlib
from typing import Final

from define.compiler.data_structures import define_path

DEFINE_FILE_SUFFIX: Final = ".dfn"
DOCS_ROOT: Final = "https://github.com/mkanat/define/define/docs"
# This is the length of: `File "a.dfn", line 1, column 1` (the shortest possible header)
ERROR_DIVIDER = "\n" + ("-" * 31) + "\n"
PROJECT_ROOT: Final = define_path.DefinePathFromPosix(pathlib.PurePosixPath())
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
BINARY_ASCII_ENCODING: Final = f"encoding<{STANDARD_UNIVERSE}:/binary/ascii>"
BOOLEAN_ASCII_ENCODING: Final = f"encoding<{STANDARD_UNIVERSE}:/boolean/ascii>"
CODE_POINT_ASCII_ENCODING: Final = (
    f"encoding<{STANDARD_UNIVERSE}:/text/unicode/code_point/ascii>"
)
DECIMAL_ASCII_ENCODING: Final = f"encoding<{STANDARD_UNIVERSE}:/number/decimal/ascii>"
HEX_ASCII_ENCODING: Final = f"encoding<{STANDARD_UNIVERSE}:/number/hex/ascii>"
INTEGER_ASCII_ENCODING: Final = f"encoding<{STANDARD_UNIVERSE}:/number/integer/ascii>"
NATURAL_ASCII_ENCODING: Final = f"encoding<{STANDARD_UNIVERSE}:/number/natural/ascii>"
SCALAR_UTF8_ENCODING: Final = f"encoding<{STANDARD_UNIVERSE}:/text/unicode/scalar/utf8>"
UTF8_ENCODING: Final = f"encoding<{STANDARD_UNIVERSE}:/text/unicode/utf8>"
# The paths, in the standard universe, of the Encoding Operations that perform
# each logical operation, one for each combination of encodings they use.
# TODO: Read Encoding Operation associations from configuration (DLP 48) once
# it exists.
BUILT_IN_LOGICAL_OPERATION_ENCODING_OPERATIONS: Final = {
    f"logical_operation<{STANDARD_UNIVERSE}:/binary/and>": ("/binary/ascii/and",),
    f"logical_operation<{STANDARD_UNIVERSE}:/binary/equals>": ("/binary/ascii/equals",),
    f"logical_operation<{STANDARD_UNIVERSE}:/binary/exclusive_or>": (
        "/binary/ascii/exclusive_or",
    ),
    f"logical_operation<{STANDARD_UNIVERSE}:/boolean/and>": ("/boolean/ascii/and",),
    f"logical_operation<{STANDARD_UNIVERSE}:/boolean/not>": ("/boolean/ascii/not",),
    f"logical_operation<{STANDARD_UNIVERSE}:/number/absolute_value>": (
        "/number/integer/ascii/absolute_value",
    ),
    f"logical_operation<{STANDARD_UNIVERSE}:/number/add>": (
        "/number/integer/ascii/add",
        "/number/natural/ascii/add",
        "/number/natural/ascii/add_integer",
    ),
    f"logical_operation<{STANDARD_UNIVERSE}:/number/less_than>": (
        "/number/integer/ascii/less_than",
        "/number/natural/ascii/less_than",
    ),
    f"logical_operation<{STANDARD_UNIVERSE}:/number/minimum>": (
        "/number/integer/ascii/minimum",
        "/number/natural/ascii/minimum",
    ),
    f"logical_operation<{STANDARD_UNIVERSE}:/number/multiply>": (
        "/number/integer/ascii/multiply",
        "/number/natural/ascii/multiply",
    ),
    f"logical_operation<{STANDARD_UNIVERSE}:/number/negate>": (
        "/number/integer/ascii/negate",
        "/number/natural/ascii/negate",
    ),
    f"logical_operation<{STANDARD_UNIVERSE}:/text/less_than>": (
        "/text/unicode/scalar/utf8/less_than",
    ),
}
# The path, in the standard universe, of the Encoding Operation that performs
# each Value Operation for the encodings of its input views.
# TODO: Delete this once the standard Value Operations are compositions of
# logical operations.
BUILT_IN_ENCODING_OPERATIONS: Final = {
    f"operation<{STANDARD_UNIVERSE}:/binary/and>": "/binary/ascii/and",
    f"operation<{STANDARD_UNIVERSE}:/binary/equals>": "/binary/ascii/equals",
    f"operation<{STANDARD_UNIVERSE}:/binary/exclusive_or>": (
        "/binary/ascii/exclusive_or"
    ),
    f"operation<{STANDARD_UNIVERSE}:/binary/or>": "/binary/ascii/or",
    f"operation<{STANDARD_UNIVERSE}:/boolean/and>": "/boolean/ascii/and",
    f"operation<{STANDARD_UNIVERSE}:/boolean/exclusive_or>": (
        "/boolean/ascii/exclusive_or"
    ),
    f"operation<{STANDARD_UNIVERSE}:/boolean/not>": "/boolean/ascii/not",
    f"operation<{STANDARD_UNIVERSE}:/boolean/or>": "/boolean/ascii/or",
    f"operation<{STANDARD_UNIVERSE}:/number/integer/absolute_value>": (
        "/number/integer/ascii/absolute_value"
    ),
    f"operation<{STANDARD_UNIVERSE}:/number/integer/add>": (
        "/number/integer/ascii/add"
    ),
    f"operation<{STANDARD_UNIVERSE}:/number/integer/decrement>": (
        "/number/integer/ascii/decrement"
    ),
    f"operation<{STANDARD_UNIVERSE}:/number/integer/equals>": (
        "/number/integer/ascii/equals"
    ),
    f"operation<{STANDARD_UNIVERSE}:/number/integer/increment>": (
        "/number/integer/ascii/increment"
    ),
    f"operation<{STANDARD_UNIVERSE}:/number/integer/less_than>": (
        "/number/integer/ascii/less_than"
    ),
    f"operation<{STANDARD_UNIVERSE}:/number/integer/less_than_or_equal>": (
        "/number/integer/ascii/less_than_or_equal"
    ),
    f"operation<{STANDARD_UNIVERSE}:/number/integer/maximum>": (
        "/number/integer/ascii/maximum"
    ),
    f"operation<{STANDARD_UNIVERSE}:/number/integer/minimum>": (
        "/number/integer/ascii/minimum"
    ),
    f"operation<{STANDARD_UNIVERSE}:/number/integer/multiply>": (
        "/number/integer/ascii/multiply"
    ),
    f"operation<{STANDARD_UNIVERSE}:/number/integer/negate>": (
        "/number/integer/ascii/negate"
    ),
    f"operation<{STANDARD_UNIVERSE}:/number/integer/subtract>": (
        "/number/integer/ascii/subtract"
    ),
    f"operation<{STANDARD_UNIVERSE}:/number/natural/add>": (
        "/number/natural/ascii/add"
    ),
    f"operation<{STANDARD_UNIVERSE}:/number/natural/decrement_saturating>": (
        "/number/natural/ascii/decrement_saturating"
    ),
    f"operation<{STANDARD_UNIVERSE}:/number/natural/equals>": (
        "/number/natural/ascii/equals"
    ),
    f"operation<{STANDARD_UNIVERSE}:/number/natural/increment>": (
        "/number/natural/ascii/increment"
    ),
    f"operation<{STANDARD_UNIVERSE}:/number/natural/less_than>": (
        "/number/natural/ascii/less_than"
    ),
    f"operation<{STANDARD_UNIVERSE}:/number/natural/less_than_or_equal>": (
        "/number/natural/ascii/less_than_or_equal"
    ),
    f"operation<{STANDARD_UNIVERSE}:/number/natural/maximum>": (
        "/number/natural/ascii/maximum"
    ),
    f"operation<{STANDARD_UNIVERSE}:/number/natural/minimum>": (
        "/number/natural/ascii/minimum"
    ),
    f"operation<{STANDARD_UNIVERSE}:/number/natural/multiply>": (
        "/number/natural/ascii/multiply"
    ),
    f"operation<{STANDARD_UNIVERSE}:/number/natural/subtract>": (
        "/number/natural/ascii/subtract"
    ),
    f"operation<{STANDARD_UNIVERSE}:/number/natural/subtract_saturating>": (
        "/number/natural/ascii/subtract_saturating"
    ),
    f"operation<{STANDARD_UNIVERSE}:/text/unicode/scalar/equals>": (
        "/text/unicode/scalar/utf8/equals"
    ),
    f"operation<{STANDARD_UNIVERSE}:/text/unicode/scalar/less_than>": (
        "/text/unicode/scalar/utf8/less_than"
    ),
    f"operation<{STANDARD_UNIVERSE}:/text/unicode/scalar/less_than_or_equal>": (
        "/text/unicode/scalar/utf8/less_than_or_equal"
    ),
    f"operation<{STANDARD_UNIVERSE}:/text/unicode/scalar/greater_than_or_equal>": (
        "/text/unicode/scalar/utf8/greater_than_or_equal"
    ),
}
