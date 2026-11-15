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
