//! The validation of a DCL file's text against its schema: parsing it, then
//! checking it.

use defcl_parser::{SyntaxError, parse};
use defcl_semantics::{FileDescriptorSet, Schema, SchemaError, SemanticError, check_semantics};
use source_rendering::SourceLines;
use std::io;
use std::path::Path;

/// Why a DCL file is not valid.
#[derive(Debug, PartialEq, Eq)]
pub enum ValidationError {
    /// The descriptor set has no message type with the top-level message
    /// type's name.
    Schema(SchemaError),
    /// The first syntax error, which stops parsing.
    Syntax(RenderedError<SyntaxError>),
    /// Every semantic error, in source order.
    Semantic(Vec<RenderedError<SemanticError>>),
}

/// An error in a DCL file, with the text that shows it to a developer.
#[derive(Debug, PartialEq, Eq)]
pub struct RenderedError<E> {
    pub error: E,
    /// The error's location, as its source line underlined with carets, then
    /// its message.
    pub rendered: String,
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
    validate_source(source, None, descriptor_set, top_level_message_type)
}

/// Validates the DCL file at `path` as `validate` validates its text, and
/// returns the text with the result of validating it. The rendered errors
/// name the file.
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
) -> io::Result<(String, Result<(), ValidationError>)> {
    let source = std::fs::read_to_string(path)?;
    let result = validate_source(
        &source,
        Some(&path.display().to_string()),
        descriptor_set,
        top_level_message_type,
    );
    Ok((source, result))
}

fn validate_source(
    source: &str,
    file_path: Option<&str>,
    descriptor_set: FileDescriptorSet,
    top_level_message_type: &str,
) -> Result<(), ValidationError> {
    let schema = Schema::from_descriptor_set(descriptor_set, top_level_message_type)
        .map_err(ValidationError::Schema)?;
    // The line table is built only for a file with errors, which is rare.
    let file = parse(source).map_err(|error| {
        ValidationError::Syntax(RenderedError {
            rendered: error.render(&SourceLines::new(source), file_path),
            error,
        })
    })?;
    check_semantics(&file, &schema).map_err(|errors| {
        let source_lines = SourceLines::new(source);
        let mut rendered_errors = Vec::with_capacity(errors.len());
        for error in errors {
            rendered_errors.push(RenderedError {
                rendered: error.render(&source_lines, file_path),
                error,
            });
        }
        ValidationError::Semantic(rendered_errors)
    })
}

#[cfg(test)]
mod tests {
    use super::{RenderedError, ValidationError, validate, validate_file};
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
        verify_ok!(validate(
            include_str!("../testdata/valid/single_toplevel.defcl"),
            valid_schemas()?,
            "defcl.testdata.valid.schemas.SingleToplevelFile",
        ))
    }

    #[gtest]
    fn missing_message_type() -> Result<()> {
        verify_that!(
            validate(
                include_str!("../testdata/valid/single_toplevel.defcl"),
                valid_schemas()?,
                "defcl.testdata.valid.schemas.NoSuchFile",
            ),
            err(eq(&ValidationError::Schema(
                SchemaError::MissingMessageType {
                    message_type: "defcl.testdata.valid.schemas.NoSuchFile".to_owned(),
                }
            )))
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
            err(eq(&ValidationError::Syntax(RenderedError {
                error: SyntaxError {
                    kind: SyntaxErrorKind::UnexpectedCharacter { character: '@' },
                    location: SourceLocation {
                        start: Position { line: 2, column: 8 },
                        end: Position { line: 2, column: 8 }
                    },
                },
                rendered: "line 2, column 8\n    b: @\n       ^\nUnexpected character '@' (U+0040)"
                    .to_owned(),
            })))
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
            err(eq(&ValidationError::Semantic(vec![
                RenderedError {
                    error: SemanticError {
                        kind: SemanticErrorKind::UnknownFieldName {
                            message_type:
                                "defcl.testdata.invalid.semantics.schemas.MultipleErrorsFile.Config"
                                    .to_owned(),
                        },
                        location: SourceLocation { start: Position { line: 2, column: 5 }, end: Position { line: 2, column: 8 } },
                        field_name: "size".to_owned(),
                    },
                    rendered: "line 2, column 5\n    size: 1\n    ^^^^\nsize: defcl.testdata.invalid.semantics.schemas.MultipleErrorsFile.Config has no field with this name"
                        .to_owned(),
                },
                RenderedError {
                    error: SemanticError {
                        kind: SemanticErrorKind::UnknownFieldName {
                            message_type:
                                "defcl.testdata.invalid.semantics.schemas.MultipleErrorsFile.Config"
                                    .to_owned(),
                        },
                        location: SourceLocation { start: Position { line: 3, column: 5 }, end: Position { line: 3, column: 8 } },
                        field_name: "size".to_owned(),
                    },
                    rendered: "line 3, column 5\n    size: 2\n    ^^^^\nsize: defcl.testdata.invalid.semantics.schemas.MultipleErrorsFile.Config has no field with this name"
                        .to_owned(),
                },
            ])))
        )
    }

    #[gtest]
    fn validate_file_returns_the_text_and_names_the_file_in_rendered_errors() -> Result<()> {
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
                eq("a: {\n    b: @\n}\n"),
                err(eq(&ValidationError::Syntax(RenderedError {
                    error: SyntaxError {
                        kind: SyntaxErrorKind::UnexpectedCharacter { character: '@' },
                        location: SourceLocation {
                            start: Position { line: 2, column: 8 },
                            end: Position { line: 2, column: 8 }
                        },
                    },
                    rendered: format!(
                        "File \"{}\", line 2, column 8\n    b: @\n       ^\nUnexpected character '@' (U+0040)",
                        path.display()
                    ),
                })))
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
