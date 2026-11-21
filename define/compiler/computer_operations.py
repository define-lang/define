"""The computer operations that the compiler knows how to perform."""

from __future__ import annotations

from typing import Final

from define.compiler import constants

# The full typed name of each Encoding Operation whose computer operation the
# compiler knows how to perform. Validation reports any other Encoding
# Operation that executes the computer operation, and each code generation
# backend performs every one of these.
PERFORMABLE: Final = frozenset(
    [
        f"encoding_operation<{constants.STANDARD_UNIVERSE}:/binary/ascii/and>",
        f"encoding_operation<{constants.STANDARD_UNIVERSE}:/binary/ascii/equals>",
        f"encoding_operation<{constants.STANDARD_UNIVERSE}:/binary/ascii/exclusive_or>",
        f"encoding_operation<{constants.STANDARD_UNIVERSE}:/boolean/ascii/and>",
        f"encoding_operation<{constants.STANDARD_UNIVERSE}:/boolean/ascii/not>",
        f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/integer/ascii/absolute_value>",
        f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/integer/ascii/add>",
        f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/integer/ascii/less_than>",
        f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/integer/ascii/minimum>",
        f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/integer/ascii/multiply>",
        f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/integer/ascii/negate>",
        f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/natural/ascii/add>",
        f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/natural/ascii/add_integer>",
        f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/natural/ascii/less_than>",
        f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/natural/ascii/minimum>",
        f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/natural/ascii/multiply>",
        f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/natural/ascii/negate>",
        f"encoding_operation<{constants.STANDARD_UNIVERSE}:/text/unicode/scalar/utf8/less_than>",
        f"encoding_operation<{constants.STANDARD_UNIVERSE}:/boolean/ascii/exclusive_or>",
        f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/integer/ascii/equals>",
        f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/integer/ascii/maximum>",
        f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/natural/ascii/equals>",
        f"encoding_operation<{constants.STANDARD_UNIVERSE}:/number/natural/ascii/maximum>",
        f"encoding_operation<{constants.STANDARD_UNIVERSE}:/text/unicode/scalar/utf8/equals>",
    ]
)
