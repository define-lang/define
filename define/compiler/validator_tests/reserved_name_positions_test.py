from define.compiler import diagnostics
from define.compiler.validator_tests.test_helpers import parse_transform_validate


def test_reserved_universe_name_position():
    source = "define the potential position<standard:/path>.\n"
    diags = parse_transform_validate(source)
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ReservedUniverseNameDiagnostic)
    assert diags[0].position.line == 1
    assert diags[0].position.column == 31


def test_reserved_universe_name_with_authority_position():
    source = "define the potential position<example.com:example:/path>.\n"
    diags = parse_transform_validate(source)
    assert len(diags) == 2
    assert isinstance(diags[0], diagnostics.ReservedAuthorityDomainDiagnostic)
    assert diags[0].position.line == 1
    assert diags[0].position.column == 31
    assert isinstance(diags[1], diagnostics.ReservedUniverseNameDiagnostic)
    assert diags[1].position.line == 1
    assert diags[1].position.column == 43


def test_reserved_authority_position():
    source = "define the potential position<example.com:my_lib:/path>.\n"
    diags = parse_transform_validate(source)
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ReservedAuthorityDomainDiagnostic)
    assert diags[0].position.line == 1
    assert diags[0].position.column == 31


def test_reserved_authority_with_multiverse_position():
    source = "define the potential position<mv:example.com:my_lib:/path>.\n"
    diags = parse_transform_validate(source)
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ReservedAuthorityDomainDiagnostic)
    assert diags[0].position.line == 1
    assert diags[0].position.column == 34


def test_dotless_authority_position():
    source = "define the potential position<localhost:my_lib:/path>.\n"
    diags = parse_transform_validate(source)
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.DotlessAuthorityDomainDiagnostic)
    assert diags[0].position.line == 1
    assert diags[0].position.column == 31


def test_reserved_multiverse_position():
    source = "define the potential position<python:example.org:my_lib:/path>.\n"
    diags = parse_transform_validate(source)
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.ReservedMultiverseNameDiagnostic)
    assert diags[0].position.line == 1
    assert diags[0].position.column == 31
