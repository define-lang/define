from define.compiler import diagnostics
from define.compiler.validator_tests.test_helpers import parse_transform_validate


def test_multiverse_name_position():
    source = "define the potential position<_mv:my.domain.com:my_lib:/path>.\n"
    diags = parse_transform_validate(source)
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
    diags = parse_transform_validate(source)
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
    diags = parse_transform_validate(source)
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
    diags = parse_transform_validate(source)
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
    diags = parse_transform_validate(source)
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
        "define the position<my-pos>.\n"
        "it happens when {\n"
        "} and it does {\n"
        "}\n"
        "}\n"
    )
    diags = parse_transform_validate(source)
    ln_diags = [
        d for d in diags if isinstance(d, diagnostics.InvalidLocalNameFormatDiagnostic)
    ]
    assert len(ln_diags) == 1
    assert ln_diags[0].local_name == "my-pos"
    assert ln_diags[0].char == "-"
    assert ln_diags[0].position.line == 2
    assert ln_diags[0].position.column == 23
