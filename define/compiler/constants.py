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
# The compiler provides these standard universe names itself until the Define
# Standard Library exists. They have no definitions, so code that looks up
# definitions has special cases for them.
# TODO: Remove these, and every special case marked with a TODO that refers to
# them, once the Define Standard Library defines these names.
DECIMAL_ASCII_ENCODING: Final = f"encoding<{STANDARD_UNIVERSE}:/number/decimal/ascii>"
BUILT_IN_LITERAL_ENCODINGS: Final = {
    f"literal<{STANDARD_UNIVERSE}:/number>": DECIMAL_ASCII_ENCODING
}
# TODO: Read value encodings from encodings configuration (DLP 47) once it
# exists.
BUILT_IN_VALUE_ENCODINGS: Final = {
    f"value<{STANDARD_UNIVERSE}:/number/rational>": DECIMAL_ASCII_ENCODING
}
BUILT_IN_GLOBAL_NAMES: Final = frozenset(
    {DECIMAL_ASCII_ENCODING, *BUILT_IN_LITERAL_ENCODINGS, *BUILT_IN_VALUE_ENCODINGS}
)
