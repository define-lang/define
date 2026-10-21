"""The functions of Rust source files and the calls that `?` applies to."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import msgspec

if TYPE_CHECKING:
    from collections.abc import Iterable

_FUNCTION = re.compile(r"\bfn\s+(?P<name>\w+)")
# An `impl` item, which formatted code always starts on its own line.
_IMPL = re.compile(r"^[ \t]*(?:unsafe[ \t]+)?impl\b", re.MULTILINE)
_CHAR_LITERAL = re.compile(
    r"b?'(?:\\(?:x[0-9a-fA-F]{2}|u\{[0-9a-fA-F]{1,6}\}|.)|[^\\'\n])'"
)
_RAW_STRING_START = re.compile(r'b?r(?P<hashes>#*)"')
_WHERE = re.compile(r"\bwhere\b")
# A closure's parameters, at the start of the arguments of a call.
_CLOSURE_ARGUMENT = re.compile(r"(?:^|,)\s*(?:move\s+)?\|")
# A closure's parameters and return type, before the `{` of its body.
_CLOSURE_BODY_HEAD = re.compile(r"\|\s*(?:->[^{|]*)?$")
_IDENTIFIER_CHARACTERS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
)
_PYTHON_RESULT = "PyResult<"
_OPENERS = {")": "(", "]": "[", "}": "{", ">": "<"}
_CLOSERS = {opener: closer for closer, opener in _OPENERS.items()}


class RustFunction(msgspec.Struct, frozen=True):
    """A function declared in Rust source."""

    name: str
    impl_type: str | None
    returns_python_result: bool


class _FunctionBody(msgspec.Struct, frozen=True):
    """The offsets of the `{` and `}` of a function's body."""

    function: RustFunction
    start: int
    end: int


class Callee(msgspec.Struct, frozen=True):
    """The function that a call names, and the type that qualifies its path if one does."""

    name: str
    qualifier: str | None


class RustSource:
    """A Rust source file and the functions it declares."""

    def __init__(self, text: str):
        """Index the functions in `text`."""
        self._text: str = text
        self._code: str = _code_only(text)
        self._line_starts: list[int] = [0]
        for line in text.splitlines(keepends=True):
            self._line_starts.append(self._line_starts[-1] + len(line))
        self.functions: list[RustFunction] = []
        self._bodies: list[_FunctionBody] = []
        for function, signature_end in _declared_functions(self._code):
            self.functions.append(function)
            if self._code[signature_end] == "{":
                self._bodies.append(
                    _FunctionBody(
                        function=function,
                        start=signature_end,
                        end=_closing(self._code, signature_end),
                    )
                )

    def offset(self, line: int, byte_column: int) -> int:
        """Return the offset in the text of a 1-based line and byte column."""
        line_start = self._line_starts[line - 1]
        line_text = self._text[line_start : self._line_starts[line]]
        return line_start + len(line_text.encode()[: byte_column - 1].decode())

    def enclosing_function(self, offset: int) -> RustFunction | None:
        """Return the innermost function whose body has `offset`, unless `offset` is in a closure."""
        enclosing = None
        for body in self._bodies:
            if body.start < offset < body.end and (
                enclosing is None or enclosing.start < body.start
            ):
                enclosing = body
        if enclosing is None or self._is_in_closure(enclosing.start, offset):
            return None
        return enclosing.function

    def _is_in_closure(self, body_start: int, offset: int) -> bool:
        """Return whether `offset` is in a closure in the function body that starts at `body_start`."""
        index = offset - 1
        while index > body_start:
            character = self._code[index]
            if character in _OPENERS and character != ">":
                index = _opening(self._code, index) - 1
                continue
            if character == "{" and _CLOSURE_BODY_HEAD.search(
                self._code[body_start:index].rstrip()
            ):
                return True
            if character == "(" and _CLOSURE_ARGUMENT.search(
                self._code[index + 1 : offset]
            ):
                return True
            index -= 1
        return False

    def callee_before(self, offset: int) -> Callee | None:
        """Return the function that the call just before `offset` names, if a call is there."""
        index = _skip_space_backward(self._code, offset - 1)
        if self._code[index] != ")":
            return None
        index = _skip_space_backward(self._code, _opening(self._code, index) - 1)
        # A turbofish names the type arguments of the call.
        if self._code[index] == ">":
            index = _opening(self._code, index) - 1
            if self._code[index - 1 : index + 1] != "::":
                return None
            index -= 2
        # A macro call has `!` before its arguments.
        if self._code[index] == "!":
            index -= 1
        name, index = _identifier_ending_at(self._code, index)
        if not name:
            return None
        qualifier = None
        if self._code[index - 2 : index] == "::":
            qualifier, _ = _identifier_ending_at(self._code, index - 3)
        return Callee(name=name, qualifier=qualifier)


class RustCrate:
    """The functions that the source files of one Rust crate declare."""

    def __init__(self, sources: Iterable[RustSource]):
        """Index the functions of `sources` by name and by their `impl` type."""
        self._by_name: dict[str, set[bool]] = {}
        self._by_qualified_name: dict[tuple[str, str], set[bool]] = {}
        for source in sources:
            for function in source.functions:
                self._by_name.setdefault(function.name, set()).add(
                    function.returns_python_result
                )
                if function.impl_type is not None:
                    self._by_qualified_name.setdefault(
                        (function.impl_type, function.name), set()
                    ).add(function.returns_python_result)

    def returns_python_result(self, callee: Callee) -> bool | None:
        """Return whether every function that `callee` may name returns a `PyResult`.

        Returns None if the crate declares no function that `callee` may name.
        """
        if callee.qualifier is not None:
            results = self._by_qualified_name.get((callee.qualifier, callee.name))
        else:
            results = self._by_name.get(callee.name)
        if results is None:
            return None
        return results == {True}


def _code_only(text: str) -> str:
    """Return `text` with its comments and literals replaced by spaces, keeping line feeds."""
    characters = list(text)
    index = 0
    while index < len(text):
        end = _comment_end(text, index)
        if end is None:
            end = _literal_end(text, index)
        if end is None:
            index += 1
            continue
        for position in range(index, end):
            if characters[position] != "\n":
                characters[position] = " "
        index = end
    return "".join(characters)


def _comment_end(text: str, index: int) -> int | None:
    """Return the offset after the comment that starts at `index`, if one does."""
    if text.startswith("//", index):
        end = text.find("\n", index)
        return len(text) if end < 0 else end
    if text.startswith("/*", index):
        return _block_comment_end(text, index)
    return None


def _literal_end(text: str, index: int) -> int | None:
    """Return the offset after the string or character literal that starts at `index`, if one does."""
    # A literal's prefix, such as the `b` of `b"bytes"`, is not part of an
    # identifier.
    if index > 0 and text[index - 1] in _IDENTIFIER_CHARACTERS:
        return None
    if raw_string := _RAW_STRING_START.match(text, index):
        hashes = raw_string.group("hashes")
        return text.index('"' + hashes, raw_string.end()) + 1 + len(hashes)
    if text.startswith('"', index) or text.startswith('b"', index):
        end = text.index('"', index) + 1
        while text[end] != '"':
            end += 2 if text[end] == "\\" else 1
        return end + 1
    if char_literal := _CHAR_LITERAL.match(text, index):
        return char_literal.end()
    return None


def _block_comment_end(text: str, index: int) -> int:
    """Return the offset after the block comment, which may have block comments in it, that starts at `index`."""
    depth = 0
    end = index
    while True:
        if text.startswith("/*", end):
            depth += 1
            end += 2
        elif text.startswith("*/", end):
            depth -= 1
            end += 2
            if depth == 0:
                return end
        else:
            end += 1


def _impls(code: str) -> list[tuple[str, int, int]]:
    """Return the type, and the offsets of the `{` and `}`, of each `impl` in `code`."""
    impls: list[tuple[str, int, int]] = []
    for match in _IMPL.finditer(code):
        head_end = _first_at_depth_zero(code, match.end(), "{")
        head = code[match.end() : head_end].strip()
        if head.startswith("<"):
            head = head[_closing(head, 0) + 1 :]
        implemented = head.rsplit(" for ", 1)[-1].strip()
        type_path, _ = _identifier_starting_at(implemented.split("<", 1)[0], 0)
        impls.append(
            (type_path.rsplit("::", 1)[-1], head_end, _closing(code, head_end))
        )
    return impls


def _declared_functions(code: str) -> list[tuple[RustFunction, int]]:
    """Return each function declared in `code`, which has no comments or literals, with the offset after its signature."""
    impls = _impls(code)
    functions: list[tuple[RustFunction, int]] = []
    for match in _FUNCTION.finditer(code):
        signature_end = _first_at_depth_zero(code, match.end(), "{;")
        signature = code[match.end() : signature_end]
        arrow = _first_arrow_at_depth_zero(signature)
        return_type = "" if arrow is None else signature[arrow + 2 :]
        where = _WHERE.search(return_type)
        if where is not None:
            return_type = return_type[: where.start()]
        impl_type = None
        for type_name, impl_start, impl_end in impls:
            if impl_start < match.start() < impl_end:
                impl_type = type_name
        function = RustFunction(
            name=match.group("name"),
            impl_type=impl_type,
            returns_python_result=return_type.strip().startswith(_PYTHON_RESULT),
        )
        functions.append((function, signature_end))
    return functions


def _first_at_depth_zero(code: str, start: int, targets: str) -> int:
    """Return the offset of the first of `targets` from `start` outside parentheses, brackets, and angle brackets."""
    depth = 0
    index = start
    while True:
        character = code[index]
        if code.startswith("->", index):
            index += 2
            continue
        if depth == 0 and character in targets:
            return index
        if character in "([<":
            depth += 1
        elif character in ")]>":
            depth -= 1
        index += 1


def _first_arrow_at_depth_zero(signature: str) -> int | None:
    """Return the offset of the `->` of a function signature's return type, if it has one."""
    depth = 0
    index = 0
    while index < len(signature):
        if signature.startswith("->", index):
            if depth == 0:
                return index
            index += 2
            continue
        if signature[index] in "([<":
            depth += 1
        elif signature[index] in ")]>":
            depth -= 1
        index += 1
    return None


def _closing(code: str, open_index: int) -> int:
    """Return the offset of the bracket that closes the one at `open_index`."""
    opener = code[open_index]
    closer = _CLOSERS[opener]
    depth = 0
    index = open_index
    while True:
        if code.startswith("->", index):
            index += 2
            continue
        if code[index] == opener:
            depth += 1
        elif code[index] == closer:
            depth -= 1
            if depth == 0:
                return index
        index += 1


def _opening(code: str, close_index: int) -> int:
    """Return the offset of the bracket that opens the one at `close_index`."""
    closer = code[close_index]
    opener = _OPENERS[closer]
    depth = 0
    index = close_index
    while True:
        if closer == ">" and code[index - 1 : index + 1] == "->":
            index -= 2
            continue
        if code[index] == closer:
            depth += 1
        elif code[index] == opener:
            depth -= 1
            if depth == 0:
                return index
        index -= 1


def _skip_space_backward(code: str, index: int) -> int:
    while code[index].isspace():
        index -= 1
    return index


def _identifier_ending_at(code: str, index: int) -> tuple[str, int]:
    """Return the identifier whose last character is at `index`, and the offset of its first character."""
    end = index + 1
    while index >= 0 and code[index] in _IDENTIFIER_CHARACTERS:
        index -= 1
    return code[index + 1 : end], index + 1


def _identifier_starting_at(code: str, index: int) -> tuple[str, int]:
    """Return the path of identifiers that starts at `index`, and the offset after it."""
    end = index
    while end < len(code) and (code[end] in _IDENTIFIER_CHARACTERS or code[end] == ":"):
        end += 1
    return code[index:end], end
