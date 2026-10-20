import pathlib

from define.compiler import ast
from define.compiler.errors import diagnostics as diagnostics_mod
from define.compiler.errors import parser_exceptions

class ParseResult:
    @property
    def program(self) -> ast.Program | None: ...
    @property
    def diagnostics(self) -> list[diagnostics_mod.Diagnostic]: ...
    @property
    def exception(self) -> parser_exceptions.DefineSyntaxError | None: ...

def parse(source: bytes, file_path: pathlib.PurePosixPath | None) -> ParseResult: ...
