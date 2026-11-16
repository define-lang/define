# pyright: reportUnusedCallResult=false

# Message format tests exist only for complex diagnostics, such as multi-line
# messages or messages with many fields. Behavioral tests cover simple ones.

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from define.compiler.conftest import ValidateProject

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
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    formatted = all_diags[0].format(result.program_result.source_map)
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
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    formatted = all_diags[0].format(result.program_result.source_map)
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
    all_diags = result.program_result.all_diagnostics
    assert len(all_diags) == 1
    formatted = all_diags[0].format(result.program_result.source_map)
    assert formatted == textwrap.dedent("""\
        File "test.dfn", line 21, column 21
            execute the operation</outer_sum> {
                        ^^^^^^^^^^^^^^^^^^^^^
        no Encoding Operation performs 'logical_operation<standard:/number/add>' for these encodings:
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
