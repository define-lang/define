from __future__ import annotations

import types

from crates.source_rendering.python import rendering
from define.compiler import config
from define.compiler.data_structures import define_path
from define.compiler.parsing import test_helpers
from define.compiler.validator import validation_result
from define.compiler.validator.structural import (
    definition_validator,
    file_validation_context,
)

# Where the locations come from does not matter to these tests.
_LOCATION = rendering.SourceLocation(
    line=1, column=1, end_line=1, end_column=1, file_path=".define/project/config.defcl"
)


class TestDefinitionStructuralValidator:
    def test_validate_definition_returns_result_object(self):
        source = "define the potential position<my.domain.com:my_lib:/test>.\n"
        program = test_helpers.parse(source, "/test.dfn")
        validator = definition_validator.DefinitionStructuralValidator(
            definition=program.definitions[0],
            context=file_validation_context.FileValidationContext(
                file_path=define_path.DefinePath("test.dfn"),
                root_prefix=define_path.DefinePath("/project"),
                root_config=config.ProjectRootConfig(
                    fqun="my.domain.com:my_lib",
                    fqun_location=_LOCATION,
                    sub_roots=types.MappingProxyType({}),
                ),
            ),
        )

        result = validator.validate_definition()

        assert isinstance(result, validation_result.DefinitionValidationResult)
        assert result.definition == program.definitions[0]
        assert result.diagnostics == []
