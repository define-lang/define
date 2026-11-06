//! The validation of a DCL file's text against its schema: parsing it, then
//! checking it.

use defcl_parser::{SyntaxError, parse};
use defcl_semantics::{FileDescriptorSet, Schema, SchemaError, SemanticError, check_semantics};

/// Why a DCL file is not valid.
#[derive(Debug, PartialEq, Eq)]
pub enum ValidationError {
    /// The descriptor set has no message type with the top-level message
    /// type's name.
    Schema(SchemaError),
    /// The first syntax error, which stops parsing.
    Syntax(SyntaxError),
    /// Every semantic error, in source order.
    Semantic(Vec<SemanticError>),
}

/// Validates `source`, the text of a DCL file, against the schema whose
/// top-level message type has the full name `top_level_message_type` in
/// `descriptor_set`.
///
/// # Errors
///
/// Returns the schema's error, or the first syntax error in `source`, or, if
/// it has none, every semantic error in it.
pub fn validate(
    source: &str,
    descriptor_set: FileDescriptorSet,
    top_level_message_type: &str,
) -> Result<(), ValidationError> {
    let schema = Schema::from_descriptor_set(descriptor_set, top_level_message_type)
        .map_err(ValidationError::Schema)?;
    let file = parse(source).map_err(ValidationError::Syntax)?;
    check_semantics(&file, &schema).map_err(ValidationError::Semantic)
}

#[cfg(test)]
mod tests {
    use super::{ValidationError, validate};
    use defcl_parser::{SourceLocation, SyntaxError, SyntaxErrorKind};
    use defcl_semantics::{FileDescriptorSet, SchemaError, SemanticError, SemanticErrorKind};
    use googletest::prelude::*;
    use prost::Message;
    use runfiles::Runfiles;

    const MULTIPLE_ERRORS_FILE: &str =
        "defcl.testdata.invalid.semantics.schemas.MultipleErrorsFile";

    /// The descriptor set of the schemas in `defcl/testdata/invalid/semantics`.
    fn invalid_semantics_schemas() -> Result<FileDescriptorSet> {
        let runfiles = Runfiles::create().or_fail()?;
        let path = runfiles::rlocation!(runfiles, env!("INVALID_SEMANTICS_SCHEMAS")).or_fail()?;
        FileDescriptorSet::decode(std::fs::read(path).or_fail()?.as_slice()).or_fail()
    }

    #[gtest]
    fn missing_message_type() -> Result<()> {
        verify_that!(
            validate(
                "config: {\n    name: \"a\"\n}\n",
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.NoSuchFile"
            ),
            err(eq(&ValidationError::Schema(
                SchemaError::MissingMessageType {
                    message_type: "defcl.testdata.invalid.semantics.schemas.NoSuchFile".to_owned(),
                }
            )))
        )
    }

    #[gtest]
    fn valid_file() -> Result<()> {
        verify_ok!(validate(
            "config: {\n    name: \"a\"\n}\n",
            invalid_semantics_schemas()?,
            MULTIPLE_ERRORS_FILE
        ))
    }

    #[gtest]
    fn syntax_error() -> Result<()> {
        verify_that!(
            validate(
                "config: {\n    name: @\n}\n",
                invalid_semantics_schemas()?,
                MULTIPLE_ERRORS_FILE
            ),
            err(eq(&ValidationError::Syntax(SyntaxError {
                kind: SyntaxErrorKind::UnexpectedCharacter { character: '@' },
                location: SourceLocation {
                    line: 2,
                    column: 11,
                    end_line: 2,
                    end_column: 11
                },
            })))
        )
    }

    #[gtest]
    fn semantic_errors() -> Result<()> {
        verify_that!(
            validate(
                "config: {\n    size: 1\n    status: 1\n}\n",
                invalid_semantics_schemas()?,
                MULTIPLE_ERRORS_FILE
            ),
            err(eq(&ValidationError::Semantic(vec![
                SemanticError {
                    kind: SemanticErrorKind::UnknownFieldName {
                        message_type:
                            "defcl.testdata.invalid.semantics.schemas.MultipleErrorsFile.Config"
                                .to_owned(),
                    },
                    location: SourceLocation {
                        line: 2,
                        column: 5,
                        end_line: 2,
                        end_column: 8
                    },
                    field_name: "size".to_owned(),
                },
                SemanticError {
                    kind: SemanticErrorKind::IntegerEnum,
                    location: SourceLocation {
                        line: 3,
                        column: 13,
                        end_line: 3,
                        end_column: 13
                    },
                    field_name: "status".to_owned(),
                },
            ])))
        )
    }
}
