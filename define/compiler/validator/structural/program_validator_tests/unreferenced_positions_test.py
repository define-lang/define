"""Dead-code detection for interface and local positions never referenced.

Follow program validator test authoring rules in program_validator_tests/AGENTS.md.
"""

from collections.abc import Sequence

from define.compiler import diagnostics
from define.compiler.validator.structural import program_validator


def _diagnostics(source: str) -> Sequence[diagnostics.Diagnostic]:
    result = (
        program_validator.ProgramStructuralValidator().validate_program_non_filesystem(
            source
        )
    )
    assert not result.all_exceptions
    return result.file_results[0].diagnostics


def test_unreferenced_interface_position_error():
    source = (
        "define the potential action<my.domain.com:my_lib:/act> {\n"
        "    define the position<run>.\n"
        "    define the position<unused_iface>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        define the position<_noop>.\n"
        "        create a particle in position<_noop>.\n"
        "    }\n"
        "}\n"
    )
    diags = _diagnostics(source)
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.UnreferencedPositionDiagnostic)
    assert diags[0].position_name == "position<unused_iface>"
    assert diags[0].location.line == 3
    assert diags[0].location.column == 25


def test_unreferenced_local_position_error():
    source = (
        "define the potential action<my.domain.com:my_lib:/act> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        define the position<_noop>.\n"
        "        create a particle in position<_noop>.\n"
        "        define the position<unused_local>.\n"
        "    }\n"
        "}\n"
    )
    diags = _diagnostics(source)
    assert len(diags) == 1
    assert isinstance(diags[0], diagnostics.UnreferencedPositionDiagnostic)
    assert diags[0].position_name == "position<unused_local>"
    assert diags[0].location.line == 8
    assert diags[0].location.column == 29


def test_trigger_only_interface_position_is_referenced():
    # TODO: Decide whether this is the right behavior.
    source = (
        "define the potential action<my.domain.com:my_lib:/act> {\n"
        "    define the position<run>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        define the position<_noop>.\n"
        "        create a particle in position<_noop>.\n"
        "    }\n"
        "}\n"
    )
    diags = _diagnostics(source)
    assert len(diags) == 0


def test_positions_referenced_by_create_move_destroy_are_alive():
    source = (
        "define the potential action<my.domain.com:my_lib:/act> {\n"
        "    define the position<run>.\n"
        "    define the position<src>.\n"
        "    define the position<dest>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        create a particle in position<src>.\n"
        "        move the particle in position<src> to position<dest>.\n"
        "        destroy the particle in position<dest>.\n"
        "    }\n"
        "}\n"
    )
    diags = _diagnostics(source)
    assert len(diags) == 0


def test_position_referenced_as_chain_prefix_is_alive():
    source = (
        "define the potential action<my.domain.com:my_lib:/inner> {\n"
        "    define the position<run>.\n"
        "    define the position<slot>.\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        create a particle in position<slot>.\n"
        "    }\n"
        "}\n"
        "define the potential action<my.domain.com:my_lib:/act> {\n"
        "    define the position<run>.\n"
        "    define the position<holder> {\n"
        "        it may only contain particles where {\n"
        "            it has the action</inner>.\n"
        "        }\n"
        "    }\n"
        "    it happens when {\n"
        "        the position<run> has a particle.\n"
        "    } and it does {\n"
        "        create a particle in position<holder>::action</inner>::position<slot>.\n"
        "    }\n"
        "}\n"
    )
    diags = _diagnostics(source)
    assert len(diags) == 0
