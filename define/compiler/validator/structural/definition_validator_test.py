from __future__ import annotations

import types

from define.compiler.config import config_loader
from define.compiler.data_structures import define_path
from define.compiler.parsing import test_helpers
from define.compiler.validator import validation_result
from define.compiler.validator.structural import (
    definition_validator,
    file_validation_context,
)

# Where the locations come from does not matter to these tests.


class TestDefinitionStructuralValidator:
    def test_validate_definition_returns_result_object(self):
        source = "define the potential position<my.domain.com:my_lib:/test>.\n"
        program = test_helpers.parse(source, "/test.dfn")
        validator = definition_validator.DefinitionStructuralValidator(
            definition=program.definitions[0],
            context=file_validation_context.FileValidationContext(
                file_path=define_path.DefinePath("test.dfn"),
                root_prefix=define_path.DefinePath("/project"),
                root_config=config_loader.Config(
                    fqun=test_helpers.parse_fqun("my.domain.com:my_lib"),
                    sub_roots=types.MappingProxyType({}),
                    value_encodings={},
                    logical_operation_encoding_operations={},
                ),
            ),
        )

        result = validator.validate_definition()

        assert isinstance(result, validation_result.DefinitionValidationResult)
        assert result.definition == program.definitions[0]
        assert result.diagnostics == []
