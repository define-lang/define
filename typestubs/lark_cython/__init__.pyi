from typing import Self

class Token:
    type: str
    value: str
    start_pos: int
    line: int
    column: int
    end_line: int | None
    end_column: int | None
    end_pos: int | None

    def __init__(
        self,
        type_: str,
        value: str,
        start_pos: int = -1,
        line: int = -1,
        column: int = -1,
        end_line: int | None = None,
        end_column: int | None = None,
        end_pos: int | None = None,
    ) -> None: ...
    def update(self, type_: str | None = None, value: str | None = None) -> Self: ...
