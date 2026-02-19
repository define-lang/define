from define.compiler.validator_tests.test_helpers import parse_transform_validate


def test_multiple_diagnostics_collected():
    source = (
        "define the potential position<standard:/first>.\n"
        "define the potential position<standard:/second>.\n"
    )
    diags = parse_transform_validate(source)
    assert len(diags) == 2
    assert diags[0].position.line == 1
    assert diags[0].position.column == 31
    assert diags[1].position.line == 2
    assert diags[1].position.column == 31


def test_diagnostics_in_source_order():
    source = (
        "define the potential position<standard:/first>.\n"
        "define the potential position<standard:/second>.\n"
    )
    diags = parse_transform_validate(source)
    assert diags[0].position.line == 1
    assert diags[1].position.line == 2
