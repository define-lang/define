"""Semantic validation for the Define language AST."""

from __future__ import annotations

import pathlib

from define.compiler import (
    ast,
    config,
    constants,
    diagnostics,
    exceptions,
    file_validator,
)


class Validator:
    """Validates a single Define program."""

    # TODO: Re-enable the correct non-filesystem context behavior.
    # Delete _build_validation_context because it's nonsense.
    def validate(
        self,
        program: ast.Program,
        expected_definition_path: pathlib.PurePosixPath | None = None,
        # TODO: Rename this to expected_fqun.
        expected_universe_name: str | None = None,
    ) -> list[diagnostics.Diagnostic]:
        """Validate all semantic rules and return collected diagnostics.

        Args:
            expected_definition_path: Optional expected definition path, relative
                to project root, without the .def extension. When provided, the
                validator validates that definition paths match this path.
            expected_universe_name: Optional FQUN string from the project config.
                When provided, validates that each definition's FQUN matches
                this value.
        """
        context = _build_validation_context(expected_universe_name)
        fdv = file_validator.ProgramAstValidator(context, expected_definition_path)
        fdv.validate_program(program)
        return fdv.diagnostics


def _build_validation_context(
    expected_universe_name: str | None,
) -> file_validator.FileValidationContext:
    """Load project config from CWD and build a FileValidationContext."""
    root_prefix = constants.PROJECT_ROOT
    sub_root_mappings: dict[str, pathlib.PurePosixPath] = {}
    fqun = expected_universe_name or ""
    config_load_error: exceptions.ConfigError | None = None

    try:
        loader = config.ConfigLoader(root_prefix)
        loader.assert_is_project_root()
        project_config = loader.project_config()
        universe_locations = loader.local_deps_config()
        if not fqun:
            fqun = project_config.project.universe_name or ""
        sub_root_mappings = dict(universe_locations)
    except exceptions.ConfigError as e:
        config_load_error = e

    broken_sub_root_errors: dict[str, exceptions.ConfigError] = {}
    for universe, rel_path in list(sub_root_mappings.items()):
        sub_root = root_prefix / rel_path
        try:
            sub_loader = config.ConfigLoader(sub_root)
            sub_loader.assert_is_project_root()
            _ = sub_loader.project_config()
        except exceptions.ConfigError as e:
            broken_sub_root_errors[universe] = e
            del sub_root_mappings[universe]

    return file_validator.FileValidationContext(
        file_path=pathlib.PurePosixPath(),
        root_prefix=root_prefix,
        expected_fqun=fqun,
        sub_root_mappings=sub_root_mappings,
        config_load_error=config_load_error,
        broken_sub_root_errors=broken_sub_root_errors or None,
    )
