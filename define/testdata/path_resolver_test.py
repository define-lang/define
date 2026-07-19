"""Tests for convention-based testdata path resolution."""

from pathlib import Path

from define.testdata import path_resolver


def test_directory_for():
    directory = path_resolver.directory_for(
        Path(
            "define/compiler/validator/reference_graph/"
            + "reference_graph_validator_tests/create_particle_test.py"
        ),
        "test_short_form_global_reference",
    )
    assert directory == Path(
        "define/testdata/reference_graph/create_particle/short_form_global_reference"
    )


def test_case_name_for_test_in_class():
    assert (
        path_resolver.case_name_for(
            "test_undefined_local_position_in_chain",
            "TestCreateParticle",
        )
        == "create_particle__undefined_local_position_in_chain"
    )
