import pathlib

from define.compiler import ast

def parse(source: bytes, file_path: pathlib.PurePosixPath | None) -> ast.Program: ...
