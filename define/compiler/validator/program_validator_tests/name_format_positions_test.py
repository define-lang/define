"""Name format position validation tests.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from define.compiler import diagnostics
from define.compiler.validator import program_validator


def test_multiverse_name_position():
    source = "define the potential position<_mv:my.domain.com:my_lib:/path>.\n"
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    mv_diags = [
        d
        for d in diags
        if isinstance(d, diagnostics.MultiverseNameInvalidCharDiagnostic)
    ]
    assert len(mv_diags) == 1
    assert mv_diags[0].multiverse_name == "_mv"
    assert mv_diags[0].char == "_"
    assert mv_diags[0].position.line == 1
    assert mv_diags[0].position.column == 31


def test_authority_domain_position():
    source = "define the potential position<mv:-example.com:my_lib:/path>.\n"
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    ad_diags = [
        d
        for d in diags
        if isinstance(d, diagnostics.AuthorityDomainInvalidCharDiagnostic)
    ]
    assert len(ad_diags) == 1
    assert ad_diags[0].domain == "-example.com"
    assert ad_diags[0].char == "-"
    assert ad_diags[0].position.line == 1
    assert ad_diags[0].position.column == 34


def test_authority_path_position():
    source = "define the potential position<mv:example.com/.hidden:my_lib:/path>.\n"
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    ap_diags = [
        d
        for d in diags
        if isinstance(d, diagnostics.InvalidAuthorityPathSegmentDiagnostic)
    ]
    assert len(ap_diags) == 1
    assert ap_diags[0].segment == ".hidden"
    assert ap_diags[0].char == "."
    assert ap_diags[0].position.line == 1
    assert ap_diags[0].position.column == 46


def test_universe_name_position():
    source = "define the potential position<mv:my.domain.com:_my_lib:/path>.\n"
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    un_diags = [
        d for d in diags if isinstance(d, diagnostics.UniverseNameInvalidCharDiagnostic)
    ]
    assert len(un_diags) == 1
    assert un_diags[0].universe_name == "_my_lib"
    assert un_diags[0].char == "_"
    assert un_diags[0].position.line == 1
    assert un_diags[0].position.column == 48


def test_path_segment_position():
    source = "define the potential position<my.domain.com:my_lib:/2bad>.\n"
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    ps_diags = [
        d
        for d in diags
        if isinstance(d, diagnostics.InvalidGlobalNamePathCharacterDiagnostic)
    ]
    assert len(ps_diags) == 1
    assert ps_diags[0].segment == "2bad"
    assert ps_diags[0].char == "2"
    assert ps_diags[0].position.line == 1
    assert ps_diags[0].position.column == 53


def test_local_name_position():
    source = (
        "define the potential action<mv:my.domain.com:my_lib:/act> {\n"
        "    define the position<my-pos>.\n"
        "    it happens when {\n"
        "        the position<my-pos> has a dimension point.\n"
        "    } and it does {\n"
        "    }\n"
        "}\n"
    )
    results = program_validator.ProgramValidator().validate_program_non_filesystem(
        source
    )
    diags = results[0].diagnostics
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.InvalidLocalNameFormatDiagnostic)
    assert diags[0].local_name == "my-pos"
    assert diags[0].char == "-"
    assert diags[0].position.line == 2
    assert diags[0].position.column == 27
    assert isinstance(diags[1], diagnostics.InvalidLocalNameFormatDiagnostic)
    assert diags[1].local_name == "my-pos"
    assert diags[1].char == "-"
    assert diags[1].position.line == 4
    assert diags[1].position.column == 24
