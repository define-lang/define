"""Shared constants for the Define compiler."""

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
