from crates.source_rendering.python import rendering
from define.compiler import ast
from define.compiler.errors import diagnostics as diagnostics_mod
from define.compiler.errors import syntax_errors

class ParseResult:
    @property
    def program(self) -> ast.Program | None: ...
    @property
    def diagnostics(self) -> list[diagnostics_mod.Diagnostic]: ...
    @property
    def load_failure(self) -> syntax_errors.FileLoadFailureDiagnostic | None: ...

def parse_global_name(
    name: bytes, file_path: str | None, line: int, column: int
) -> ast.ReferenceGlobalNameContent | syntax_errors.DefineSyntaxError: ...
def parse(
    source: bytes,
    file_path: str | None,
    *,
    check_indentation: bool = True,
) -> ParseResult: ...
def parse_file(file_path: str, source_map: rendering.SourceMap) -> ParseResult: ...
