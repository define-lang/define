//! The rules that a schema's message types must follow for DCL files to be
//! written in them.

use crate::schema::MessageType;
use derive_more::Display;
use descriptor_proto::google::protobuf::feature_set::{FieldPresence, Utf8Validation};
use descriptor_proto::google::protobuf::field_descriptor_proto::Type;
use descriptor_proto::google::protobuf::{Edition, FieldDescriptorProto, FileDescriptorProto};

const ANY_TYPE_NAME: &str = ".google.protobuf.Any";

/// A way that a message type which DCL files can write breaks DCL's rules for
/// schemas.
#[derive(Debug, PartialEq, Eq, Display)]
pub enum SchemaViolation {
    /// A file that defines such a message type uses an edition before 2024,
    /// or no edition. It is reported once for each file.
    #[display(
        "{file} uses {edition}, but the files of a DCL schema must use edition 2024 or later"
    )]
    UnsupportedEdition {
        /// The file's name, as the descriptor set has it.
        file: String,
        /// The edition's name, such as `EDITION_2023`, or the syntax of a file
        /// that uses no edition, `proto2` or `proto3`.
        edition: String,
    },
    /// A field of a type that DCL does not allow.
    #[display("{message_type}.{field_name} is a {field_type} field, which DCL does not allow")]
    ProhibitedFieldType {
        message_type: String,
        field_name: String,
        field_type: ProhibitedFieldType,
    },
    /// A field whose presence is `LEGACY_REQUIRED`.
    #[display("{message_type}.{field_name} is a required field, which DCL does not allow")]
    RequiredField {
        message_type: String,
        field_name: String,
    },
    /// A field whose type is a message type with no fields, which a DCL file
    /// could only write as an empty message value.
    #[display(
        "{message_type}.{field_name} is a {field_type} field, a message type with no fields, which DCL does not allow"
    )]
    FieldOfMessageTypeWithoutFields {
        message_type: String,
        field_name: String,
        /// The full name of the field's message type.
        field_type: String,
    },
    /// A string field whose `utf8_validation` is `NONE`.
    #[display("{message_type}.{field_name} does not validate UTF-8, which DCL does not allow")]
    Utf8ValidationNone {
        message_type: String,
        field_name: String,
    },
}

/// A field type that DCL does not allow.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Display)]
pub enum ProhibitedFieldType {
    #[display("bool")]
    Bool,
    #[display("bytes")]
    Bytes,
    #[display("google.protobuf.Any")]
    Any,
}

/// What the restrictions need to know about a file of the schema.
pub(crate) struct SchemaFile {
    name: String,
    /// The edition or syntax of a file that uses an edition before 2024, or
    /// no edition.
    unsupported_edition: Option<String>,
    /// The file's default `utf8_validation`, if it sets one.
    utf8_validation: Option<i32>,
}

impl SchemaFile {
    pub(crate) fn new(file: &FileDescriptorProto) -> Self {
        let unsupported_edition = match file.syntax() {
            // Later editions have larger numbers.
            "editions" => ((file.edition() as i32) < (Edition::Edition2024 as i32))
                .then(|| file.edition().as_str_name().to_owned()),
            "proto3" => Some("proto3".to_owned()),
            // protoc leaves the syntax of a proto2 file empty.
            _ => Some("proto2".to_owned()),
        };
        Self {
            name: file.name().to_owned(),
            unsupported_edition,
            utf8_validation: file
                .options
                .as_ref()
                .and_then(|options| options.features.as_ref())
                .and_then(|features| features.utf8_validation),
        }
    }
}

/// Every way that the message type at `top_level_message_type`, and the
/// message types that its fields lead to, break DCL's rules for schemas.
/// `files` has the files of the descriptor set, in its order.
pub(crate) fn violations(
    message_types: &[MessageType],
    files: &[SchemaFile],
    top_level_message_type: usize,
) -> Vec<SchemaViolation> {
    let mut violations = Vec::new();
    let mut reached = vec![false; message_types.len()];
    let mut reported_files = vec![false; files.len()];
    reached[top_level_message_type] = true;
    // Message types are checked in the order the fields reach them, so that
    // the violations are always in the same order.
    let mut pending = vec![top_level_message_type];
    let mut next = 0;
    while let Some(&index) = pending.get(next) {
        next += 1;
        let message_type = &message_types[index];
        let file = &files[message_type.file];
        if let Some(edition) = &file.unsupported_edition
            && !reported_files[message_type.file]
        {
            reported_files[message_type.file] = true;
            violations.push(SchemaViolation::UnsupportedEdition {
                file: file.name.clone(),
                edition: edition.clone(),
            });
        }
        for field in &message_type.descriptor.field {
            check_field(message_type, field, file, &mut violations);
            // An Any field is reported, so what it holds is not checked.
            if field.type_name() == ANY_TYPE_NAME {
                continue;
            }
            let Some(field_message_type) = message_type.field_message_type(field.name()) else {
                continue;
            };
            let field_type = &message_types[field_message_type];
            if field_type.descriptor.field.is_empty() {
                violations.push(SchemaViolation::FieldOfMessageTypeWithoutFields {
                    message_type: message_type.full_name.clone(),
                    field_name: field.name().to_owned(),
                    field_type: field_type.full_name.clone(),
                });
            }
            if !reached[field_message_type] {
                reached[field_message_type] = true;
                pending.push(field_message_type);
            }
        }
    }
    violations
}

fn check_field(
    message_type: &MessageType,
    field: &FieldDescriptorProto,
    file: &SchemaFile,
    violations: &mut Vec<SchemaViolation>,
) {
    let prohibited_field_type = match field.r#type() {
        Type::Bool => Some(ProhibitedFieldType::Bool),
        Type::Bytes => Some(ProhibitedFieldType::Bytes),
        Type::Message if field.type_name() == ANY_TYPE_NAME => Some(ProhibitedFieldType::Any),
        _ => None,
    };
    if let Some(field_type) = prohibited_field_type {
        violations.push(SchemaViolation::ProhibitedFieldType {
            message_type: message_type.full_name.clone(),
            field_name: field.name().to_owned(),
            field_type,
        });
    }
    // The features of another edition are reported as that edition.
    if file.unsupported_edition.is_some() {
        return;
    }
    let features = field
        .options
        .as_ref()
        .and_then(|options| options.features.as_ref());
    // Features resolve against the defaults of edition 2024, the latest
    // edition that exists. Edition 2024 lets a file set a default for utf8_validation
    // but not for field_presence, and neither can be set on a message.
    if features.and_then(|features| features.field_presence)
        == Some(FieldPresence::LegacyRequired as i32)
    {
        violations.push(SchemaViolation::RequiredField {
            message_type: message_type.full_name.clone(),
            field_name: field.name().to_owned(),
        });
    }
    let utf8_validation = features
        .and_then(|features| features.utf8_validation)
        .or(file.utf8_validation);
    if field.r#type() == Type::String && utf8_validation == Some(Utf8Validation::None as i32) {
        violations.push(SchemaViolation::Utf8ValidationNone {
            message_type: message_type.full_name.clone(),
            field_name: field.name().to_owned(),
        });
    }
}

#[cfg(test)]
mod tests {
    use super::{ProhibitedFieldType, SchemaViolation};
    use crate::schema::{Schema, SchemaError};
    use crate::test_support::invalid_schemas;
    use googletest::prelude::*;

    const PACKAGE: &str = "defcl.testdata.invalid.schemas";

    fn schema_error(top_level_message_type: &str) -> Result<Option<SchemaError>> {
        Ok(Schema::from_descriptor_set(
            invalid_schemas()?,
            &format!("{PACKAGE}.{top_level_message_type}"),
        )
        .err())
    }

    #[gtest]
    fn prohibited_field_types_that_dcl_files_can_write() -> Result<()> {
        verify_that!(
            schema_error("ProhibitedFieldTypesFile")?,
            some(eq(&SchemaError::BreaksRestrictions {
                violations: vec![
                    SchemaViolation::ProhibitedFieldType {
                        message_type: format!("{PACKAGE}.ProhibitedFieldTypesFile.Config"),
                        field_name: "enabled".to_owned(),
                        field_type: ProhibitedFieldType::Bool,
                    },
                    SchemaViolation::ProhibitedFieldType {
                        message_type: format!("{PACKAGE}.ProhibitedFieldTypesFile.Config"),
                        field_name: "data".to_owned(),
                        field_type: ProhibitedFieldType::Bytes,
                    },
                    SchemaViolation::ProhibitedFieldType {
                        message_type: format!("{PACKAGE}.ProhibitedFieldTypesFile.Config"),
                        field_name: "extra".to_owned(),
                        field_type: ProhibitedFieldType::Any,
                    },
                ]
            }))
        )
    }

    #[gtest]
    fn required_field() -> Result<()> {
        verify_that!(
            schema_error("RequiredFieldFile")?,
            some(eq(&SchemaError::BreaksRestrictions {
                violations: vec![SchemaViolation::RequiredField {
                    message_type: format!("{PACKAGE}.RequiredFieldFile.Config"),
                    field_name: "name".to_owned(),
                }]
            }))
        )
    }

    #[gtest]
    fn field_of_message_type_without_fields() -> Result<()> {
        verify_that!(
            schema_error("MessageTypeWithoutFieldsFile")?,
            some(eq(&SchemaError::BreaksRestrictions {
                violations: vec![SchemaViolation::FieldOfMessageTypeWithoutFields {
                    message_type: format!("{PACKAGE}.MessageTypeWithoutFieldsFile.Config"),
                    field_name: "marker".to_owned(),
                    field_type: format!("{PACKAGE}.MessageTypeWithoutFieldsFile.Marker"),
                }]
            }))
        )
    }

    #[gtest]
    fn string_field_without_utf8_validation_from_its_file() -> Result<()> {
        verify_that!(
            schema_error("Utf8ValidationNoneFile")?,
            some(eq(&SchemaError::BreaksRestrictions {
                violations: vec![SchemaViolation::Utf8ValidationNone {
                    message_type: format!("{PACKAGE}.Utf8ValidationNoneFile.Config"),
                    field_name: "unchecked".to_owned(),
                }]
            }))
        )
    }

    #[gtest]
    fn each_file_of_another_edition_is_reported_once() -> Result<()> {
        verify_that!(
            schema_error("OlderEditionsFile")?,
            some(eq(&SchemaError::BreaksRestrictions {
                violations: vec![
                    SchemaViolation::UnsupportedEdition {
                        file: "defcl/testdata/invalid/schemas/edition_2023.proto".to_owned(),
                        edition: "EDITION_2023".to_owned(),
                    },
                    SchemaViolation::UnsupportedEdition {
                        file: "defcl/testdata/invalid/schemas/proto3_config.proto".to_owned(),
                        edition: "proto3".to_owned(),
                    },
                    SchemaViolation::UnsupportedEdition {
                        file: "defcl/testdata/invalid/schemas/proto2_config.proto".to_owned(),
                        edition: "proto2".to_owned(),
                    },
                ]
            }))
        )
    }
}
