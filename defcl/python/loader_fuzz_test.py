"""Fuzz tests that the loader's checks reject every file text_format.Parse would."""

from __future__ import annotations

import dataclasses
import string
import sys

from hypothesis import event, example, given, settings
from hypothesis import strategies as st

from defcl.python import loader
from defcl.testdata.valid.schemas import every_field_type_pb2

_MAX_DEPTH = 2
_INTEGER_EDGES = [
    0,
    1,
    -1,
    2**31 - 1,
    2**31,
    -(2**31),
    -(2**31) - 1,
    2**32 - 1,
    2**32,
    2**63 - 1,
    2**63,
    -(2**63),
    -(2**63) - 1,
    2**64 - 1,
    2**64,
]
_LARGEST_FLOAT = int(sys.float_info.max)
_FLOAT_INTEGER_PART_EDGES = [
    0,
    1,
    # The largest float, and the smallest integer that rounds to infinity as a
    # float.
    340282346638528859811704183484516925440,
    340282356779733661637539395458142568448,
    _LARGEST_FLOAT,
    _LARGEST_FLOAT * 2,
]
_SIMPLE_ESCAPES = [
    r"\a",
    r"\b",
    r"\f",
    r"\n",
    r"\r",
    r"\t",
    r"\v",
    r"\?",
    r"\\",
    r"\'",
    r"\"",
]
_STRING_CHARACTERS = (
    string.ascii_letters + string.digits + " !#$%&()*+,-./:;<=>?@[]^_`{|}~é日😀"
)
_ENUM_VALUES = ["MODE_UNSPECIFIED", "MODE_ACTIVE", "MODE_INACTIVE"]


def _integers() -> st.SearchStrategy[str]:
    return st.one_of(st.sampled_from(_INTEGER_EDGES), st.integers(-(2**70), 2**70)).map(
        str
    )


def _float(sign: str, integer_part: int, fraction: str) -> str:
    return f"{sign}{integer_part}.{fraction}"


def _floats() -> st.SearchStrategy[str]:
    return st.builds(
        _float,
        st.sampled_from(["", "-"]),
        st.one_of(
            st.sampled_from(_FLOAT_INTEGER_PART_EDGES),
            st.integers(0, 10**40),
        ),
        st.one_of(st.just("0"), st.from_regex(r"[0-9]{0,5}[1-9]", fullmatch=True)),
    )


def _hex_escapes(text: str) -> str:
    escapes: list[str] = []
    for byte in text.encode():
        escapes.append(f"\\x{byte:02x}")
    return "".join(escapes)


def _strings() -> st.SearchStrategy[str]:
    pieces = st.one_of(
        st.text(alphabet=_STRING_CHARACTERS, min_size=1, max_size=5),
        st.sampled_from(_SIMPLE_ESCAPES),
        st.integers(0, 255).map(lambda byte: f"\\x{byte:02x}"),
        st.integers(0, 255).map(lambda byte: f"\\{byte:03o}"),
        st.characters(exclude_categories=["Cs"]).map(_hex_escapes),
        st.integers(0, 0xFFFF).map(lambda code_point: f"\\u{code_point:04x}"),
        st.integers(0, 0x10FFFF).map(lambda code_point: f"\\U{code_point:08x}"),
    )
    return st.lists(pieces, max_size=6).map(lambda parts: '"' + "".join(parts) + '"')


@dataclasses.dataclass(frozen=True)
class _Message:
    fields: list[tuple[str, _Value]]


@dataclasses.dataclass(frozen=True)
class _Repeated:
    elements: list[_Value]


# A scalar's source text, or a message value or repeated value.
type _Value = str | _Message | _Repeated

# The fields of every_field_type.proto's Values in field number order, which
# is the order that a message value writes them in.
_FIELD_ORDER = [
    "int32_value",
    "int64_value",
    "uint32_value",
    "uint64_value",
    "sint32_value",
    "sint64_value",
    "fixed32_value",
    "fixed64_value",
    "sfixed32_value",
    "sfixed64_value",
    "float_value",
    "double_value",
    "string_value",
    "enum_value",
    "message_value",
    "delimited_value",
    "uint32_values",
    "float_values",
    "string_values",
    "enum_values",
    "message_values",
    "first_choice",
    "second_choice",
]


def _render(value: _Value, level: int) -> str:
    """Return the source text of value, written on a line indented level levels."""
    if isinstance(value, str):
        return value
    indentation = "  " * (level + 1)
    if isinstance(value, _Message):
        lines: list[str] = []
        for name, field_value in value.fields:
            lines.append(f"{indentation}{name}: {_render(field_value, level + 1)}\n")
        return "{\n" + "".join(lines) + "  " * level + "}"
    elements: list[str] = []
    for element in value.elements:
        elements.append(indentation + _render(element, level + 1))
    return "[\n" + ",\n".join(elements) + "\n" + "  " * level + "]"


def _message_in_field_order(fields: list[tuple[str, _Value]]) -> _Message:
    return _Message(sorted(fields, key=lambda field: _FIELD_ORDER.index(field[0])))


def _field(
    name: str, values: st.SearchStrategy[_Value]
) -> st.SearchStrategy[tuple[str, _Value]]:
    return st.tuples(st.just(name), values)


def _repeated_field(
    name: str, elements: st.SearchStrategy[_Value]
) -> st.SearchStrategy[tuple[str, _Value]]:
    return st.tuples(
        st.just(name), st.lists(elements, min_size=1, max_size=3).map(_Repeated)
    )


def _message_values(depth: int) -> st.SearchStrategy[_Value]:
    enum_values = st.sampled_from(_ENUM_VALUES)
    fields = [
        _field("int32_value", _integers()),
        _field("int64_value", _integers()),
        _field("uint32_value", _integers()),
        _field("uint64_value", _integers()),
        _field("sint32_value", _integers()),
        _field("sint64_value", _integers()),
        _field("fixed32_value", _integers()),
        _field("fixed64_value", _integers()),
        _field("sfixed32_value", _integers()),
        _field("sfixed64_value", _integers()),
        _field("float_value", _floats()),
        _field("double_value", _floats()),
        _field("string_value", _strings()),
        _field("enum_value", enum_values),
        _field("first_choice", _strings()),
        _field("second_choice", _integers()),
        _repeated_field("uint32_values", _integers()),
        _repeated_field("float_values", _floats()),
        _repeated_field("string_values", _strings()),
        _repeated_field("enum_values", enum_values),
    ]
    if depth < _MAX_DEPTH:
        nested = st.deferred(lambda: _message_values(depth + 1))
        fields.extend(
            [
                _field("message_value", nested),
                _field("delimited_value", nested),
                _repeated_field("message_values", nested),
            ]
        )
    return st.lists(st.one_of(fields), min_size=1, max_size=5).map(
        _message_in_field_order
    )


@settings(max_examples=500, deadline=None)
@given(_message_values(0))
@example(_Message([("string_value", r'"\u005c"')]))
@example(_Message([("string_value", r'"\U0000005cn"')]))
@example(_Message([("string_value", r'"caf\u00e9 \U0001F600 \xc3\xa9 \303\251 日"')]))
@example(_Message([("float_value", "340282346638528859811704183484516925440.0")]))
@example(_Message([("double_value", f"-{_LARGEST_FLOAT}.0")]))
@example(
    _Message(
        [
            ("uint64_value", "18446744073709551615"),
            ("sint64_value", "-9223372036854775808"),
        ]
    )
)
@example(
    _Message(
        [
            (
                "delimited_value",
                _Message([("enum_values", _Repeated(["MODE_ACTIVE"]))]),
            ),
            ("second_choice", "1"),
        ]
    )
)
def test_text_format_parses_every_file_the_checks_accept(values: _Value):
    result = loader.load(
        f"values: {_render(values, 0)}\n", every_field_type_pb2.EveryFieldTypeFile
    )
    if result.message is None:
        event("not understood")
        return
    event("diagnostics" if result.diagnostics else "accepted")
    assert result.message.HasField("values")
