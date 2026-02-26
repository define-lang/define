from typing import IO

import lark

def gen_standalone(
    lark_inst: lark.Lark,
    output: str | None = None,
    out: IO[str] = ...,
    compress: bool = False,
) -> None: ...
