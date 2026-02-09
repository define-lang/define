class Token(str):
    type: str
    start_pos: int | None
    value: str
    line: int | None
    column: int | None
    end_line: int | None
    end_column: int | None
    end_pos: int | None

    def __new__(
        cls,
        type: str,
        value: str,
        start_pos: int | None = None,
        line: int | None = None,
        column: int | None = None,
        end_line: int | None = None,
        end_column: int | None = None,
        end_pos: int | None = None,
    ) -> Token: ...
    def update(
        self, type: str | None = None, value: str | None = None
    ) -> Token: ...
    def __repr__(self) -> str: ...
    def __eq__(self, other: object) -> bool: ...
    def __hash__(self) -> int: ...
