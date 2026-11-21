# pyright: reportUnusedCallResult=false

# Message format tests exist only for complex diagnostics, such as multi-line
# messages or messages with many fields. Behavioral tests cover simple ones.

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from define.compiler.test_fixtures.validation_pipeline import ValidateProject

pytest_plugins = ["define.compiler.test_fixtures.validation_pipeline"]

# Keep Define source inline in this module so each formatted diagnostic can be
# reviewed together with the source that produces it.


def test_invalid_literal_content_format(validate_project: ValidateProject):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    it also assigns the position</target>.\n"
        "    it happens when {\n"
        "        this particle is created.\n"
        "    } and it does {\n"
        "        create a particle in position</target>.\n"
        '        set the value of position</target> from literal<standard:/number>"1.2.3".\n'
        "    }\n"
        "}\n"
    )
    result = validate_project(
        {
            "test.dfn": source,
            "target.dfn": "define the potential position<my.domain.com:my_lib:/target> {\n    it may only contain particles where {\n        it has the value<standard:/number/natural>.\n    }\n}\n",
        },
    )
    all_diags = result.program_validation.sorted_diagnostics()
    assert len(all_diags) == 1
    formatted = all_diags[0].format(result.program_validation.source_map)
    assert (
        formatted
        == textwrap.dedent("""\
        File "test.dfn", line 7, column 78
            set the value of position</target> from literal<standard:/number>"1.2.3".
                                                                                 ^
        '1.2.3' is not a valid value for 'literal<standard:/number>' here, because it cannot be represented as 'encoding<standard:/number/natural/ascii>': a number may have only one decimal point.""")
    )


def test_literal_cannot_set_value_format(validate_project: ValidateProject):
    source = (
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    it also assigns the position</target>.\n"
        "    it happens when {\n"
        "        this particle is created.\n"
        "    } and it does {\n"
        "        create a particle in position</target>.\n"
        '        set the value of position</target> from literal</text>"5".\n'
        "    }\n"
        "}\n"
    )
    result = validate_project(
        {
            "test.dfn": source,
            "target.dfn": "define the potential position<my.domain.com:my_lib:/target> {\n    it may only contain particles where {\n        it has the value<standard:/number/natural>.\n    }\n}\n",
            "text.dfn": "define the potential literal<my.domain.com:my_lib:/text> {\n    it has the encoding</text_encoding>.\n}\n",
            "text_encoding.dfn": "define the encoding<my.domain.com:my_lib:/text_encoding>.\n",
        },
    )
    all_diags = result.program_validation.sorted_diagnostics()
    assert len(all_diags) == 1
    formatted = all_diags[0].format(result.program_validation.source_map)
    assert formatted == textwrap.dedent("""\
        File "test.dfn", line 7, column 49
            set the value of position</target> from literal</text>"5".
                                                    ^^^^^^^^^^^^^^
        literal</text> cannot set a value<standard:/number/natural>, because literals with the encoding</text_encoding> cannot be read as value<standard:/number/natural>.
        To set a value<standard:/number/natural>, use a literal with one of these encodings:
            encoding<standard:/binary/ascii>
            encoding<standard:/number/decimal/ascii>
            encoding<standard:/number/hex/ascii>""")


def test_missing_encoding_operation_format(
    validate_project: ValidateProject,
):
    result = validate_project(
        {
            "final_result.dfn": (
                "define the potential position<my.domain.com:my_lib:/final_result> {\n"
                "    it may only contain particles where {\n"
                "        it has the value<standard:/number/integer>.\n"
                "    }\n"
                "}\n"
            ),
            "mixed_sum.dfn": (
                "define the operation<my.domain.com:my_lib:/mixed_sum> {\n"
                "    define the view<a> {\n"
                "        it is read.\n"
                "        it may only contain particles where {\n"
                "            it has the value<standard:/number/integer>.\n"
                "        }\n"
                "    }\n"
                "    define the view<b> {\n"
                "        it is read.\n"
                "        it may only contain particles where {\n"
                "            it has the value<standard:/number/natural>.\n"
                "        }\n"
                "    }\n"
                "    define the view<result> {\n"
                "        it is written.\n"
                "        it may only contain particles where {\n"
                "            it has the value<standard:/number/integer>.\n"
                "        }\n"
                "    }\n"
                "\n"
                "    it does {\n"
                "        execute the logical_operation<standard:/number/add> {\n"
                "            with view<a> looking at view<a>.\n"
                "            with view<b> looking at view<b>.\n"
                "            with view<result> looking at view<result>.\n"
                "        }\n"
                "    }\n"
                "}\n"
            ),
            "outer_sum.dfn": (
                "define the operation<my.domain.com:my_lib:/outer_sum> {\n"
                "    define the view<a> {\n"
                "        it is read.\n"
                "        it may only contain particles where {\n"
                "            it has the value<standard:/number/integer>.\n"
                "        }\n"
                "    }\n"
                "    define the view<b> {\n"
                "        it is read.\n"
                "        it may only contain particles where {\n"
                "            it has the value<standard:/number/natural>.\n"
                "        }\n"
                "    }\n"
                "    define the view<result> {\n"
                "        it is written.\n"
                "        it may only contain particles where {\n"
                "            it has the value<standard:/number/integer>.\n"
                "        }\n"
                "    }\n"
                "\n"
                "    it does {\n"
                "        execute the operation</mixed_sum> {\n"
                "            with view<a> looking at view<a>.\n"
                "            with view<b> looking at view<b>.\n"
                "            with view<result> looking at view<result>.\n"
                "        }\n"
                "    }\n"
                "}\n"
            ),
            "test.dfn": (
                "define the potential action<my.domain.com:my_lib:/test> {\n"
                "    it also assigns the position</final_result>.\n"
                "    it happens when {\n"
                "        this particle is created.\n"
                "    } and it does {\n"
                "        define the position<offset> {\n"
                "            it may only contain particles where {\n"
                "                it has the value<standard:/number/integer>.\n"
                "            }\n"
                "        }\n"
                "        define the position<count> {\n"
                "            it may only contain particles where {\n"
                "                it has the value<standard:/number/natural>.\n"
                "            }\n"
                "        }\n"
                "        create a particle in position<offset>.\n"
                '        set the value of position<offset> from literal<standard:/number>"-1".\n'
                "        create a particle in position<count>.\n"
                '        set the value of position<count> from literal<standard:/number>"2".\n'
                "        create a particle in position</final_result>.\n"
                "        execute the operation</outer_sum> {\n"
                "            with view<a> looking at position<offset>.\n"
                "            with view<b> looking at position<count>.\n"
                "            with view<result> looking at position</final_result>.\n"
                "        }\n"
                "    }\n"
                "}\n"
            ),
        },
    )
    all_diags = result.program_validation.sorted_diagnostics()
    assert len(all_diags) == 1
    formatted = all_diags[0].format(result.program_validation.source_map)
    assert formatted == textwrap.dedent("""\
        File "test.dfn", line 21, column 21
            execute the operation</outer_sum> {
                        ^^^^^^^^^^^^^^^^^^^^^
        no Encoding Operation is associated with 'logical_operation<standard:/number/add>' for these encodings:
          view<a>: encoding<standard:/number/integer/ascii>
          view<b>: encoding<standard:/number/natural/ascii>
          view<result>: encoding<standard:/number/integer/ascii>
        so this execution cannot run.

        This error happens because:
          'action<my.domain.com:my_lib:/test>' executes 'operation</outer_sum>':
            File "test.dfn", line 21, column 21
                execute the operation</outer_sum> {
                            ^^^^^^^^^^^^^^^^^^^^^
          'operation</outer_sum>' executes 'operation</mixed_sum>':
            File "outer_sum.dfn", line 22, column 21
                execute the operation</mixed_sum> {
                            ^^^^^^^^^^^^^^^^^^^^^
          'operation</mixed_sum>' executes 'logical_operation<standard:/number/add>':
            File "mixed_sum.dfn", line 22, column 21
                execute the logical_operation<standard:/number/add> {
                            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^""")


def _association_files(encoding_operations: str) -> dict[str, str]:
    return {
        ".define/project/config.defcl": (
            "project: {\n"
            '  universe_name: "my.domain.com:my_lib"\n'
            "  associations: {\n"
            "    has_encodings: TRUE\n"
            "    has_encoding_operations: TRUE\n"
            "  }\n"
            "}\n"
        ),
        ".define/encodings/encodings.defcl": (
            "encodings: {\n"
            "  value_encodings: [\n"
            "    {\n"
            '      value: "/number"\n'
            '      encoding: "standard:/number/integer/ascii"\n'
            "    }\n"
            "  ]\n"
            "}\n"
        ),
        ".define/encodings/encoding_operations.defcl": encoding_operations,
        "combine.dfn": (
            "define the logical_operation<my.domain.com:my_lib:/combine> {\n"
            "    define the view<a> {\n"
            "        it is read.\n"
            "    }\n"
            "    define the view<b> {\n"
            "        it is read.\n"
            "    }\n"
            "    define the view<result> {\n"
            "        it is written.\n"
            "    }\n"
            "}\n"
        ),
        "number.dfn": (
            "define the potential value<my.domain.com:my_lib:/number> {\n"
            "    it supports the logical_operation</combine> {\n"
            "        it may be read.\n"
            "        it may be written.\n"
            "    }\n"
            "}\n"
        ),
        "test.dfn": (
            "define the operation<my.domain.com:my_lib:/test> {\n"
            "    define the view<first> {\n"
            "        it is read.\n"
            "        it may only contain particles where {\n"
            "            it has the value</number>.\n"
            "        }\n"
            "    }\n"
            "    define the view<second> {\n"
            "        it is read.\n"
            "        it may only contain particles where {\n"
            "            it has the value</number>.\n"
            "        }\n"
            "    }\n"
            "    define the view<combined> {\n"
            "        it is written.\n"
            "        it may only contain particles where {\n"
            "            it has the value</number>.\n"
            "        }\n"
            "    }\n"
            "\n"
            "    it does {\n"
            "        execute the logical_operation</combine> {\n"
            "            with view<a> looking at view<first>.\n"
            "            with view<b> looking at view<second>.\n"
            "            with view<result> looking at view<combined>.\n"
            "        }\n"
            "    }\n"
            "}\n"
        ),
    }


def _chosen_association_files(encoding_operations: str) -> dict[str, str]:
    # Only an Encoding Operation that an execution chooses is loaded and
    # checked against its association.
    files = _association_files(encoding_operations)
    files["test.dfn"] += (
        "\n"
        "define the potential action<my.domain.com:my_lib:/test> {\n"
        "    it also assigns the position</combined>.\n"
        "    it happens when {\n"
        "        this particle is created.\n"
        "    } and it does {\n"
        "        define the position<first> {\n"
        "            it may only contain particles where {\n"
        "                it has the value</number>.\n"
        "            }\n"
        "        }\n"
        "        define the position<second> {\n"
        "            it may only contain particles where {\n"
        "                it has the value</number>.\n"
        "            }\n"
        "        }\n"
        "        create a particle in position<first>.\n"
        '        set the value of position<first> from literal<standard:/number>"1".\n'
        "        create a particle in position<second>.\n"
        '        set the value of position<second> from literal<standard:/number>"2".\n'
        "        create a particle in position</combined>.\n"
        "        execute the operation</test> {\n"
        "            with view<first> looking at position<first>.\n"
        "            with view<second> looking at position<second>.\n"
        "            with view<combined> looking at position</combined>.\n"
        "        }\n"
        "    }\n"
        "}\n"
    )
    files["combined.dfn"] = (
        "define the potential position<my.domain.com:my_lib:/combined> {\n"
        "    it may only contain particles where {\n"
        "        it has the value</number>.\n"
        "    }\n"
        "}\n"
    )
    return files


def test_association_view_count_format(validate_project: ValidateProject):
    encoding_operations = (
        "encoding_operations: {\n"
        "  operation_encodings: [\n"
        "    {\n"
        '      logical_operation: "/combine"\n'
        "      encoding_operation: {\n"
        '        name: "standard:/number/integer/ascii/add"\n'
        "        views: [\n"
        "          {\n"
        '            view: "a"\n'
        '            encoding: "standard:/number/integer/ascii"\n'
        "          },\n"
        "          {\n"
        '            view: "b"\n'
        '            encoding: "standard:/number/integer/ascii"\n'
        "          }\n"
        "        ]\n"
        "      }\n"
        "    }\n"
        "  ]\n"
        "}\n"
    )
    result = validate_project(_association_files(encoding_operations))
    assert [
        diagnostic.format(result.program_validation.source_map)
        for diagnostic in result.program_validation.sorted_diagnostics()
    ] == [
        """\
File ".define/encodings/encoding_operations.defcl", line 6, column 16
    name: "standard:/number/integer/ascii/add"
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
this association lists 2 views for 'encoding_operation<standard:/number/integer/ascii/add>', but 'logical_operation<my.domain.com:my_lib:/combine>' has 3, defined here:
File "combine.dfn", line 1, column 12
    define the logical_operation<my.domain.com:my_lib:/combine> {
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^""",
    ]


def test_association_view_name_and_encoding_format(validate_project: ValidateProject):
    encoding_operations = (
        "encoding_operations: {\n"
        "  operation_encodings: [\n"
        "    {\n"
        '      logical_operation: "/combine"\n'
        "      encoding_operation: {\n"
        '        name: "standard:/number/integer/ascii/add"\n'
        "        views: [\n"
        "          {\n"
        '            view: "a"\n'
        '            encoding: "standard:/number/integer/ascii"\n'
        "          },\n"
        "          {\n"
        '            view: "c"\n'
        '            encoding: "standard:/number/integer/ascii"\n'
        "          },\n"
        "          {\n"
        '            view: "result"\n'
        '            encoding: "standard:/number/natural/ascii"\n'
        "          }\n"
        "        ]\n"
        "      }\n"
        "    }\n"
        "  ]\n"
        "}\n"
    )
    result = validate_project(_association_files(encoding_operations))
    assert [
        diagnostic.format(result.program_validation.source_map)
        for diagnostic in result.program_validation.sorted_diagnostics()
    ] == [
        """\
File ".define/encodings/encoding_operations.defcl", line 13, column 19
    view: "c"
          ^^^
this association lists 'c' as view 2 of 'encoding_operation<standard:/number/integer/ascii/add>', but view 2 of 'logical_operation<my.domain.com:my_lib:/combine>' is 'b', defined here:
File "combine.dfn", line 5, column 16
    define the view<b> {
               ^^^^^^^""",
    ]


def test_association_encoding_operation_view_count_format(
    validate_project: ValidateProject,
):
    encoding_operations = (
        "encoding_operations: {\n"
        "  operation_encodings: [\n"
        "    {\n"
        '      logical_operation: "/combine"\n'
        "      encoding_operation: {\n"
        '        name: "/combine/integer"\n'
        "        views: [\n"
        "          {\n"
        '            view: "a"\n'
        '            encoding: "standard:/number/integer/ascii"\n'
        "          },\n"
        "          {\n"
        '            view: "b"\n'
        '            encoding: "standard:/number/integer/ascii"\n'
        "          },\n"
        "          {\n"
        '            view: "result"\n'
        '            encoding: "standard:/number/integer/ascii"\n'
        "          }\n"
        "        ]\n"
        "      }\n"
        "    }\n"
        "  ]\n"
        "}\n"
    )
    encoding_operation = (
        "define the encoding_operation<my.domain.com:my_lib:/combine/integer> {\n"
        "    define the view<a> {\n"
        "        it is read.\n"
        "        it may only contain particles where {\n"
        "            it has the encoding<standard:/number/integer/ascii>.\n"
        "        }\n"
        "    }\n"
        "    define the view<result> {\n"
        "        it is written.\n"
        "        it may only contain particles where {\n"
        "            it has the encoding<standard:/number/integer/ascii>.\n"
        "        }\n"
        "    }\n"
        "\n"
        "    it does {\n"
        "        execute the computer operation.\n"
        "    }\n"
        "}\n"
    )
    result = validate_project(
        {
            **_chosen_association_files(encoding_operations),
            "combine/integer.dfn": encoding_operation,
        }
    )
    assert [
        diagnostic.format(result.program_validation.source_map)
        for diagnostic in result.program_validation.sorted_diagnostics()
    ] == [
        """\
File ".define/encodings/encoding_operations.defcl", line 6, column 16
    name: "/combine/integer"
           ^^^^^^^^^^^^^^^^
this association lists 3 views for 'encoding_operation<my.domain.com:my_lib:/combine/integer>', but it has 2 interface views, defined here:
File "combine/integer.dfn", line 1, column 12
    define the encoding_operation<my.domain.com:my_lib:/combine/integer> {
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^""",
    ]


def test_association_encoding_operation_view_name_and_encoding_format(
    validate_project: ValidateProject,
):
    encoding_operations = (
        "encoding_operations: {\n"
        "  operation_encodings: [\n"
        "    {\n"
        '      logical_operation: "/combine"\n'
        "      encoding_operation: {\n"
        '        name: "/combine/integer"\n'
        "        views: [\n"
        "          {\n"
        '            view: "a"\n'
        '            encoding: "standard:/number/integer/ascii"\n'
        "          },\n"
        "          {\n"
        '            view: "b"\n'
        '            encoding: "standard:/number/integer/ascii"\n'
        "          },\n"
        "          {\n"
        '            view: "result"\n'
        '            encoding: "standard:/number/integer/ascii"\n'
        "          }\n"
        "        ]\n"
        "      }\n"
        "    }\n"
        "  ]\n"
        "}\n"
    )
    encoding_operation = (
        "define the encoding_operation<my.domain.com:my_lib:/combine/integer> {\n"
        "    define the view<a> {\n"
        "        it is read.\n"
        "        it may only contain particles where {\n"
        "            it has the encoding<standard:/number/integer/ascii>.\n"
        "        }\n"
        "    }\n"
        "    define the view<c> {\n"
        "        it is read.\n"
        "        it may only contain particles where {\n"
        "            it has the encoding<standard:/number/integer/ascii>.\n"
        "        }\n"
        "    }\n"
        "    define the view<result> {\n"
        "        it is written.\n"
        "        it may only contain particles where {\n"
        "            it has the encoding<standard:/number/natural/ascii>.\n"
        "        }\n"
        "    }\n"
        "\n"
        "    it does {\n"
        "        execute the computer operation.\n"
        "    }\n"
        "}\n"
    )
    result = validate_project(
        {
            **_chosen_association_files(encoding_operations),
            "combine/integer.dfn": encoding_operation,
        }
    )
    assert [
        diagnostic.format(result.program_validation.source_map)
        for diagnostic in result.program_validation.sorted_diagnostics()
    ] == [
        """\
File ".define/encodings/encoding_operations.defcl", line 13, column 19
    view: "b"
          ^^^
this association lists 'b' as view 2 of 'encoding_operation<my.domain.com:my_lib:/combine/integer>', but its view 2 is 'c', defined here:
File "combine/integer.dfn", line 8, column 16
    define the view<c> {
               ^^^^^^^""",
        """\
File ".define/encodings/encoding_operations.defcl", line 18, column 24
    encoding: "standard:/number/integer/ascii"
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
this association says 'view<result>' of 'encoding_operation<my.domain.com:my_lib:/combine/integer>' has 'encoding<standard:/number/integer/ascii>', but it has 'encoding<standard:/number/natural/ascii>', assigned here:
File "combine/integer.dfn", line 17, column 24
    it has the encoding<standard:/number/natural/ascii>.
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^""",
    ]


def _value_quality_files(encodings: str | None) -> dict[str, str]:
    files = {
        ".define/project/config.defcl": (
            "project: {\n"
            '  universe_name: "my.domain.com:my_lib"\n'
            "  associations: {\n"
            "    has_encodings: TRUE\n"
            "  }\n"
            "}\n"
        ),
        "test.dfn": (
            "define the potential value<my.domain.com:my_lib:/test> {\n"
            "    it supports the logical_operation<standard:/text/less_than> {\n"
            "        it may be read.\n"
            "    }\n"
            "}\n"
            "\n"
            "define the potential position<my.domain.com:my_lib:/test> {\n"
            "    it may only contain particles where {\n"
            "        it has the value</test>.\n"
            "    }\n"
            "}\n"
        ),
    }
    if encodings is not None:
        files[".define/encodings/encodings.defcl"] = encodings
    return files


def test_encodings_config_not_found_format(validate_project: ValidateProject):
    result = validate_project(_value_quality_files(None))
    assert [
        diagnostic.format(result.program_validation.source_map)
        for diagnostic in result.program_validation.sorted_diagnostics()
    ] == [
        """\
File ".define/project/config.defcl", line 4, column 20
    has_encodings: TRUE
                   ^^^^
The project says it has encoding associations, but .define/encodings/encodings.defcl was not found.""",
    ]


def test_unsorted_value_encoding_format(validate_project: ValidateProject):
    encodings = (
        "encodings: {\n"
        "  value_encodings: [\n"
        "    {\n"
        '      value: "/test"\n'
        '      encoding: "standard:/number/integer/ascii"\n'
        "    },\n"
        "    {\n"
        '      value: "/number"\n'
        '      encoding: "standard:/number/integer/ascii"\n'
        "    }\n"
        "  ]\n"
        "}\n"
    )
    result = validate_project(_value_quality_files(encodings))
    assert [
        diagnostic.format(result.program_validation.source_map)
        for diagnostic in result.program_validation.sorted_diagnostics()
    ] == [
        """\
File ".define/encodings/encodings.defcl", line 8, column 14
    value: "/number"
           ^^^^^^^^^
Encoding associations must be sorted by value quality, but '/number' comes after '/test'.""",
    ]


def test_duplicate_value_encoding_format(validate_project: ValidateProject):
    encodings = (
        "encodings: {\n"
        "  value_encodings: [\n"
        "    {\n"
        '      value: "/test"\n'
        '      encoding: "standard:/number/integer/ascii"\n'
        "    },\n"
        "    {\n"
        '      value: "/test"\n'
        '      encoding: "standard:/number/integer/ascii"\n'
        "    }\n"
        "  ]\n"
        "}\n"
    )
    result = validate_project(_value_quality_files(encodings))
    assert [
        diagnostic.format(result.program_validation.source_map)
        for diagnostic in result.program_validation.sorted_diagnostics()
    ] == [
        """\
File ".define/encodings/encodings.defcl", line 7, column 5
    {
    ^
Value quality '/test' is already associated with encoding 'standard:/number/integer/ascii' here:
File ".define/encodings/encodings.defcl", line 3, column 5
    {
    ^""",
    ]
