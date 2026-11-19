from __future__ import annotations

import types

from define.compiler.config import config_loader
from define.compiler.data_structures import define_path
from define.compiler.parsing import test_helpers
from define.compiler.validator.structural import (
    definition_validator,
    file_validation_context,
    structural_result,
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
                    has_encodings_location=None,
                    has_encoding_operations_location=None,
                ),
            ),
        )

        result, found = validator.validate_definition()

        assert isinstance(result, structural_result.StructuralDefinitionResult)
        assert result.definition == program.definitions[0]
        assert result.structurally_valid
        assert found == []
