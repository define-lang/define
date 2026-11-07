//! The schema that a DCL file is checked against: the message types of a
//! `FileDescriptorSet`, with lookup tables over their descriptors.

use crate::schema_restrictions::{self, SchemaFile, SchemaViolation};
use derive_more::{Display, Error};
use descriptor_proto::google::protobuf::field_descriptor_proto::{Label, Type};
use descriptor_proto::google::protobuf::{
    DescriptorProto, FieldDescriptorProto, FileDescriptorSet,
};
use rustc_hash::{FxBuildHasher, FxHashMap};
use std::fmt::Write as _;

/// A schema that the crate cannot check a DCL file against.
#[derive(Debug, PartialEq, Eq, Display, Error)]
pub enum SchemaError {
    /// The `FileDescriptorSet` has no message type named `message_type`, the
    /// requested top-level message type.
    #[display(
        "Cannot create a DCL schema: the FileDescriptorSet has no message type named {message_type} to use as the top-level message type"
    )]
    MissingMessageType { message_type: String },
    /// A message field's type is not a message type in the
    /// `FileDescriptorSet`, which protoc never writes.
    #[display(
        "Cannot create a DCL schema: the field {message_type}.{field_name} has the type {type_name}, which the FileDescriptorSet does not define"
    )]
    UnknownFieldType {
        /// The full name of the message type that has the field.
        message_type: String,
        field_name: String,
        /// The field's type name, as the descriptor set has it.
        type_name: String,
    },
    /// The top-level message type, or a message type that its fields lead
    /// to, breaks DCL's rules for schemas.
    #[display("Cannot create a DCL schema:{}", violation_list(violations))]
    BreaksRestrictions { violations: Vec<SchemaViolation> },
}

fn violation_list(violations: &[SchemaViolation]) -> String {
    let mut list = String::new();
    for violation in violations {
        // Writing to a String cannot fail.
        let _ = write!(list, "\n  - {violation}");
    }
    list
}

/// The message types of a `FileDescriptorSet`, and which of them is the
/// type of a whole DCL file.
pub struct Schema {
    message_types: Vec<MessageType>,
    top_level_message_type: usize,
}

/// A message type's descriptor, with its fields by name.
pub(crate) struct MessageType {
    /// The full name, without a leading `.`.
    pub(crate) full_name: String,
    /// The index in the descriptor set of the file that defines it.
    pub(crate) file: usize,
    pub(crate) descriptor: DescriptorProto,
    fields_by_name: FxHashMap<String, FieldLookup>,
}

struct FieldLookup {
    /// The index of the field in its message type's descriptor.
    index: usize,
    /// The index of the field's message type, for a message field.
    message_type: Option<usize>,
}

/// A field of a message type in the schema.
pub(crate) struct SchemaField<'schema> {
    pub(crate) descriptor: &'schema FieldDescriptorProto,
    pub(crate) message_type: Option<&'schema MessageType>,
}

impl SchemaField<'_> {
    pub(crate) fn is_repeated(&self) -> bool {
        self.descriptor.label() == Label::Repeated
    }

    pub(crate) fn is_enum(&self) -> bool {
        self.descriptor.r#type() == Type::Enum
    }
}

impl MessageType {
    /// The index of the message type of this message type's field `name`, if
    /// it is a message field. `name` must be the name of one of its fields.
    pub(crate) fn field_message_type(&self, name: &str) -> Option<usize> {
        self.fields_by_name[name].message_type
    }
}

impl Schema {
    /// Indexes `file_descriptor_set` for checking DCL files whose top-level
    /// message type is the one with the full name `top_level_message_type`.
    ///
    /// `file_descriptor_set` must be as protoc writes it, with every file that
    /// its files import.
    ///
    /// # Errors
    ///
    /// Returns an error if a message field's type is not a message type in
    /// the set, if the set does not have the top-level message type, or if
    /// that message type or the message types that its fields lead to break
    /// DCL's rules for schemas. The error has every way that they break them.
    pub fn from_descriptor_set(
        file_descriptor_set: FileDescriptorSet,
        top_level_message_type: &str,
    ) -> Result<Self, SchemaError> {
        let mut message_types = Vec::new();
        let mut files = Vec::with_capacity(file_descriptor_set.file.len());
        for (file_index, mut file) in file_descriptor_set.file.into_iter().enumerate() {
            let scope = file.package.take().unwrap_or_default();
            for descriptor in std::mem::take(&mut file.message_type) {
                add_message_type(&mut message_types, file_index, &scope, descriptor);
            }
            files.push(SchemaFile::new(&file));
        }
        let mut indices_by_name =
            FxHashMap::with_capacity_and_hasher(message_types.len(), FxBuildHasher);
        for (index, message_type) in message_types.iter().enumerate() {
            indices_by_name.insert(message_type.full_name.clone(), index);
        }
        for message_type in &mut message_types {
            index_fields(message_type, &indices_by_name)?;
        }
        let Some(&top_level_message_type) = indices_by_name.get(top_level_message_type) else {
            return Err(SchemaError::MissingMessageType {
                message_type: top_level_message_type.to_owned(),
            });
        };
        let violations =
            schema_restrictions::violations(&message_types, &files, top_level_message_type);
        if !violations.is_empty() {
            return Err(SchemaError::BreaksRestrictions { violations });
        }
        Ok(Self {
            message_types,
            top_level_message_type,
        })
    }

    pub(crate) fn top_level_message_type(&self) -> &MessageType {
        &self.message_types[self.top_level_message_type]
    }

    /// The field of `message_type` named `name`, if it has one.
    pub(crate) fn field<'schema>(
        &'schema self,
        message_type: &'schema MessageType,
        name: &str,
    ) -> Option<SchemaField<'schema>> {
        let lookup = message_type.fields_by_name.get(name)?;
        Some(SchemaField {
            descriptor: &message_type.descriptor.field[lookup.index],
            message_type: lookup.message_type.map(|index| &self.message_types[index]),
        })
    }
}

/// Adds the message type `descriptor`, declared in `scope` in the file at
/// `file`, and the message types declared in it.
fn add_message_type(
    message_types: &mut Vec<MessageType>,
    file: usize,
    scope: &str,
    mut descriptor: DescriptorProto,
) {
    let name = descriptor.name();
    let full_name = if scope.is_empty() {
        name.to_owned()
    } else {
        format!("{scope}.{name}")
    };
    let nested_types = std::mem::take(&mut descriptor.nested_type);
    for nested_type in nested_types {
        add_message_type(message_types, file, &full_name, nested_type);
    }
    message_types.push(MessageType {
        full_name,
        file,
        descriptor,
        fields_by_name: FxHashMap::default(),
    });
}

fn index_fields(
    message_type: &mut MessageType,
    indices_by_name: &FxHashMap<String, usize>,
) -> Result<(), SchemaError> {
    let mut fields_by_name =
        FxHashMap::with_capacity_and_hasher(message_type.descriptor.field.len(), FxBuildHasher);
    for (index, field) in message_type.descriptor.field.iter().enumerate() {
        let message_field_type = match field.r#type() {
            Type::Message | Type::Group => {
                // A descriptor set from protoc has only fully-qualified type
                // names, which start with a `.`.
                let Some(&message_field_type) = field
                    .type_name()
                    .strip_prefix('.')
                    .and_then(|full_name| indices_by_name.get(full_name))
                else {
                    return Err(SchemaError::UnknownFieldType {
                        message_type: message_type.full_name.clone(),
                        field_name: field.name().to_owned(),
                        type_name: field.type_name().to_owned(),
                    });
                };
                Some(message_field_type)
            }
            _ => None,
        };
        fields_by_name.insert(
            field.name().to_owned(),
            FieldLookup {
                index,
                message_type: message_field_type,
            },
        );
    }
    message_type.fields_by_name = fields_by_name;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::{Schema, SchemaError};
    use crate::test_support::valid_schemas;
    use descriptor_proto::google::protobuf::field_descriptor_proto::Type;
    use descriptor_proto::google::protobuf::{
        DescriptorProto, Edition, FieldDescriptorProto, FileDescriptorProto, FileDescriptorSet,
    };
    use googletest::prelude::*;

    #[gtest]
    fn missing_message_type() -> Result<()> {
        verify_that!(
            Schema::from_descriptor_set(
                valid_schemas()?,
                "defcl.testdata.valid.schemas.NoSuchFile"
            )
            .err(),
            some(eq(&SchemaError::MissingMessageType {
                message_type: "defcl.testdata.valid.schemas.NoSuchFile".to_owned()
            }))
        )
    }

    #[gtest]
    fn message_field_whose_type_is_not_in_the_set() -> Result<()> {
        let file_descriptor_set = FileDescriptorSet {
            file: vec![FileDescriptorProto {
                name: Some("file.proto".to_owned()),
                package: Some("package".to_owned()),
                syntax: Some("editions".to_owned()),
                edition: Some(Edition::Edition2024.into()),
                message_type: vec![DescriptorProto {
                    name: Some("File".to_owned()),
                    field: vec![FieldDescriptorProto {
                        name: Some("config".to_owned()),
                        number: Some(1),
                        r#type: Some(Type::Message.into()),
                        type_name: Some(".package.Missing".to_owned()),
                        ..FieldDescriptorProto::default()
                    }],
                    ..DescriptorProto::default()
                }],
                ..FileDescriptorProto::default()
            }],
        };
        verify_that!(
            Schema::from_descriptor_set(file_descriptor_set, "package.File").err(),
            some(eq(&SchemaError::UnknownFieldType {
                message_type: "package.File".to_owned(),
                field_name: "config".to_owned(),
                type_name: ".package.Missing".to_owned(),
            }))
        )
    }

    #[gtest]
    fn nested_message_type_is_not_found_by_its_short_name() -> Result<()> {
        verify_that!(
            Schema::from_descriptor_set(valid_schemas()?, "Project").err(),
            some(eq(&SchemaError::MissingMessageType {
                message_type: "Project".to_owned()
            }))
        )
    }
}
