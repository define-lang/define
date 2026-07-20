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


def test_directory_for_driver_test():
    directory = path_resolver.directory_for(
        Path("define/compiler/driver_run_test.py"),
        "test_valid_file_returns_success",
    )
    assert directory == Path(
        "define/testdata/driver/driver_run/valid_file_returns_success"
    )


def test_directory_for_codegen_test():
    directory = path_resolver.directory_for(
        Path("define/compiler/codegen/generator_test.py"),
        "test_constructor_entry_point_adds_no_diagnostics",
    )
    assert directory == Path(
        "define/testdata/codegen/generator/constructor_entry_point_adds_no_diagnostics"
    )
