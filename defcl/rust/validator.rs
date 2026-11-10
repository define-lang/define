//! The validation of a DCL file's text against its schema: parsing it, then
//! checking it.

use defcl_parser::{SyntaxError, parse};
use defcl_semantics::{FileDescriptorSet, Schema, SchemaError, SemanticError, check_semantics};
use std::io;
use std::path::Path;

/// The errors in a DCL file, which it has none of if it is valid.
#[derive(Debug, PartialEq, Eq)]
pub struct FileErrors {
    /// Every syntax error, in the order the parser found them. If one stopped
    /// the parse, it is the last.
    pub syntax_errors: Vec<SyntaxError>,
    /// Every semantic error, in source order, unless a syntax error stopped the
    /// parse.
    pub semantic_errors: Vec<SemanticError>,
}

/// Validates `source`, the text of a DCL file, against the schema whose
/// top-level message type has the full name `top_level_message_type` in
/// `descriptor_set`, and returns its errors.
///
/// # Errors
///
/// Returns the schema's error if the descriptor set has no message type with
/// the top-level message type's name, or the schema breaks DCL's rules.
pub fn validate(
    source: &str,
    descriptor_set: FileDescriptorSet,
    top_level_message_type: &str,
) -> Result<FileErrors, SchemaError> {
    let schema = Schema::from_descriptor_set(descriptor_set, top_level_message_type)?;
    let parsed = parse(source);
    let semantic_errors = match &parsed.file {
        Some(file) => check_semantics(file, &schema),
        None => Vec::new(),
    };
    Ok(FileErrors {
        syntax_errors: parsed.errors,
        semantic_errors,
    })
}

/// Validates the DCL file at `path` as `validate` validates its text, and
/// returns the text with the result of validating it.
///
/// # Errors
///
/// Returns the error that reading the file ends in.
// TODO: Return the binary encoding of the file's message instead of its text
// when this crate writes the encoding.
pub fn validate_file(
    path: &Path,
    descriptor_set: FileDescriptorSet,
    top_level_message_type: &str,
) -> io::Result<(String, Result<FileErrors, SchemaError>)> {
    let source = std::fs::read_to_string(path)?;
    let result = validate(&source, descriptor_set, top_level_message_type);
    Ok((source, result))
}

#[cfg(test)]
mod tests {
    use super::{FileErrors, validate, validate_file};
    use defcl_parser::{SyntaxError, SyntaxErrorKind};
    use defcl_semantics::{FileDescriptorSet, SchemaError, SemanticError, SemanticErrorKind};
    use googletest::prelude::*;
    use prost::Message as _;
    use runfiles::Runfiles;
    use source_rendering::{Position, SourceLocation};
    use std::io;
    use std::path::Path;

    /// The descriptor set of the schemas in `defcl/testdata/valid`.
    fn valid_schemas() -> Result<FileDescriptorSet> {
        read_descriptor_set(env!("VALID_SCHEMAS"))
    }

    /// The descriptor set of the schemas in `defcl/testdata/invalid/semantics`.
    fn invalid_semantics_schemas() -> Result<FileDescriptorSet> {
        read_descriptor_set(env!("INVALID_SEMANTICS_SCHEMAS"))
    }

    /// Decodes the descriptor set in the runfile at `rlocation_path`.
    fn read_descriptor_set(rlocation_path: &str) -> Result<FileDescriptorSet> {
        let runfiles = Runfiles::create().or_fail()?;
        let path = runfiles::rlocation!(runfiles, rlocation_path).or_fail()?;
        FileDescriptorSet::decode(std::fs::read(path).or_fail()?.as_slice()).or_fail()
    }

    #[gtest]
    fn valid_file() -> Result<()> {
        verify_that!(
            validate(
                include_str!("../testdata/valid/single_toplevel.defcl"),
                valid_schemas()?,
                "defcl.testdata.valid.schemas.SingleToplevelFile",
            ),
            ok(eq(&FileErrors {
                syntax_errors: vec![],
                semantic_errors: vec![],
            }))
        )
    }

    #[gtest]
    fn missing_message_type() -> Result<()> {
        verify_that!(
            validate(
                include_str!("../testdata/valid/single_toplevel.defcl"),
                valid_schemas()?,
                "defcl.testdata.valid.schemas.NoSuchFile",
            ),
            err(eq(&SchemaError::MissingMessageType {
                message_type: "defcl.testdata.valid.schemas.NoSuchFile".to_owned(),
            }))
        )
    }

    #[gtest]
    fn syntax_error() -> Result<()> {
        verify_that!(
            validate(
                include_str!("../testdata/invalid/syntax/characters/at_sign.defcl"),
                valid_schemas()?,
                "defcl.testdata.valid.schemas.SingleToplevelFile",
            ),
            ok(eq(&FileErrors {
                syntax_errors: vec![SyntaxError {
                    kind: SyntaxErrorKind::UnexpectedCharacter { character: '@' },
                    location: SourceLocation {
                        start: Position { line: 2, column: 6 },
                        end: Position { line: 2, column: 6 }
                    },
                }],
                semantic_errors: vec![],
            }))
        )
    }

    #[gtest]
    fn semantic_errors() -> Result<()> {
        verify_that!(
            validate(
                include_str!(
                    "../testdata/invalid/semantics/multiple_errors/unknown_field_written_twice.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.MultipleErrorsFile",
            ),
            ok(eq(&FileErrors {
                syntax_errors: vec![],
                semantic_errors: vec![
                    SemanticError {
                        kind: SemanticErrorKind::UnknownFieldName {
                            message_type:
                                "defcl.testdata.invalid.semantics.schemas.MultipleErrorsFile.Config"
                                    .to_owned(),
                        },
                        location: SourceLocation {
                            start: Position { line: 2, column: 3 },
                            end: Position { line: 2, column: 6 }
                        },
                        field_name: "size".to_owned(),
                    },
                    SemanticError {
                        kind: SemanticErrorKind::UnknownFieldName {
                            message_type:
                                "defcl.testdata.invalid.semantics.schemas.MultipleErrorsFile.Config"
                                    .to_owned(),
                        },
                        location: SourceLocation {
                            start: Position { line: 3, column: 3 },
                            end: Position { line: 3, column: 6 }
                        },
                        field_name: "size".to_owned(),
                    },
                ],
            }))
        )
    }

    #[gtest]
    fn layout_errors_and_semantic_errors() -> Result<()> {
        verify_that!(
            validate(
                "project: {\n size: 1\n}\n",
                valid_schemas()?,
                "defcl.testdata.valid.schemas.SingleToplevelFile",
            ),
            ok(eq(&FileErrors {
                syntax_errors: vec![SyntaxError {
                    kind: SyntaxErrorKind::WrongIndentation { expected_spaces: 2 },
                    location: SourceLocation {
                        start: Position { line: 2, column: 1 },
                        end: Position { line: 2, column: 1 }
                    },
                }],
                semantic_errors: vec![SemanticError {
                    kind: SemanticErrorKind::UnknownFieldName {
                        message_type: "defcl.testdata.valid.schemas.SingleToplevelFile.Project"
                            .to_owned(),
                    },
                    location: SourceLocation {
                        start: Position { line: 2, column: 2 },
                        end: Position { line: 2, column: 5 }
                    },
                    field_name: "size".to_owned(),
                }],
            }))
        )
    }

    #[gtest]
    fn validate_file_returns_the_text_with_the_result() -> Result<()> {
        let runfiles = Runfiles::create().or_fail()?;
        let path = runfiles::rlocation!(
            runfiles,
            "_main/defcl/testdata/invalid/syntax/characters/at_sign.defcl"
        )
        .or_fail()?;
        verify_that!(
            validate_file(
                &path,
                valid_schemas()?,
                "defcl.testdata.valid.schemas.SingleToplevelFile",
            )
            .or_fail()?,
            (
                eq("a: {\n  b: @\n}\n"),
                ok(eq(&FileErrors {
                    syntax_errors: vec![SyntaxError {
                        kind: SyntaxErrorKind::UnexpectedCharacter { character: '@' },
                        location: SourceLocation {
                            start: Position { line: 2, column: 6 },
                            end: Position { line: 2, column: 6 }
                        },
                    }],
                    semantic_errors: vec![],
                }))
            )
        )
    }

    #[gtest]
    fn validate_file_of_a_missing_file_is_an_error_reading_it() -> Result<()> {
        verify_that!(
            validate_file(
                Path::new("no_such_file.defcl"),
                valid_schemas()?,
                "defcl.testdata.valid.schemas.SingleToplevelFile",
            )
            .map_err(|error| error.kind()),
            err(eq(&io::ErrorKind::NotFound))
        )
    }
}
