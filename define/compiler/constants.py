"""Shared constants for the Define compiler."""

import pathlib
from typing import Final

DOCS_ROOT: Final = "https://github.com/mkanat/define/define/docs"
PROJECT_ROOT: Final = pathlib.PurePosixPath(".")
NON_FILESYSTEM_PATH: Final = pathlib.PurePosixPath("<string>")
