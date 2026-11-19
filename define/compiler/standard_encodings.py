"""The full names of the encodings that the standard universe's files in define/standard define."""

from __future__ import annotations

from typing import Final

from define.compiler import constants

BINARY_ASCII_ENCODING: Final = f"encoding<{constants.STANDARD_UNIVERSE}:/binary/ascii>"
BOOLEAN_ASCII_ENCODING: Final = (
    f"encoding<{constants.STANDARD_UNIVERSE}:/boolean/ascii>"
)
CODE_POINT_ASCII_ENCODING: Final = (
    f"encoding<{constants.STANDARD_UNIVERSE}:/text/unicode/code_point/ascii>"
)
DECIMAL_ASCII_ENCODING: Final = (
    f"encoding<{constants.STANDARD_UNIVERSE}:/number/decimal/ascii>"
)
HEX_ASCII_ENCODING: Final = f"encoding<{constants.STANDARD_UNIVERSE}:/number/hex/ascii>"
INTEGER_ASCII_ENCODING: Final = (
    f"encoding<{constants.STANDARD_UNIVERSE}:/number/integer/ascii>"
)
NATURAL_ASCII_ENCODING: Final = (
    f"encoding<{constants.STANDARD_UNIVERSE}:/number/natural/ascii>"
)
SCALAR_UTF8_ENCODING: Final = (
    f"encoding<{constants.STANDARD_UNIVERSE}:/text/unicode/scalar/utf8>"
)
UTF8_ENCODING: Final = f"encoding<{constants.STANDARD_UNIVERSE}:/text/unicode/utf8>"
