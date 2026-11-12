from define.compiler import ast
from define.compiler.errors import diagnostics as diagnostics_mod
from define.compiler.errors import syntax_errors

class ParseResult:
    @property
    def program(self) -> ast.Program | None: ...
    @property
    def diagnostics(self) -> list[diagnostics_mod.Diagnostic]: ...
    @property
    def syntax_error(self) -> syntax_errors.DefineSyntaxError | None: ...

def parse_global_name(
    name: bytes, file_path: str | None, line: int, column: int
) -> ast.ReferenceGlobalNameContent | syntax_errors.DefineSyntaxError: ...
def parse(
    source: bytes,
    file_path: str | None,
    *,
    check_indentation: bool = True,
) -> ParseResult: ...
