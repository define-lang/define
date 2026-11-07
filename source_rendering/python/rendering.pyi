def render_location(
    *,
    line: int,
    column: int,
    end_line: int,
    end_column: int,
    source_line: str | None,
    file_path: str | None,
) -> str: ...
def escape_invisible(text: str) -> str: ...
