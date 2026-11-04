//! The schema that a DCL file is checked against: the message types of a
//! `FileDescriptorSet`, with lookup tables over their descriptors.

use descriptor_proto::google::protobuf::field_descriptor_proto::{Label, Type};
use descriptor_proto::google::protobuf::{
    DescriptorProto, FieldDescriptorProto, FileDescriptorSet,
};
use rustc_hash::{FxBuildHasher, FxHashMap};

/// A schema that the crate cannot check a DCL file against.
#[derive(Debug, PartialEq, Eq)]
pub enum SchemaError {
    /// The `FileDescriptorSet` has no message type named `message_type`, the
    /// requested top-level message type.
    MissingMessageType { message_type: String },
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
    descriptor: DescriptorProto,
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

impl Schema {
    /// Indexes `file_descriptor_set` for checking DCL files whose top-level
    /// message type is the one with the full name `top_level_message_type`.
    ///
    /// `file_descriptor_set` must be as protoc writes it, with every file that
    /// its files import.
    ///
    /// # Errors
    ///
    /// Returns an error if the set does not have the top-level message type.
    ///
    /// # Panics
    ///
    /// Panics if a message field's type name is not the full name of a
    /// message type in the set, which protoc never writes.
    pub fn from_descriptor_set(
        file_descriptor_set: FileDescriptorSet,
        top_level_message_type: &str,
    ) -> Result<Self, SchemaError> {
        let mut message_types = Vec::new();
        for mut file in file_descriptor_set.file {
            let scope = file.package.take().unwrap_or_default();
            for descriptor in file.message_type {
                add_message_type(&mut message_types, &scope, descriptor);
            }
        }
        let mut indices_by_name =
            FxHashMap::with_capacity_and_hasher(message_types.len(), FxBuildHasher);
        for (index, message_type) in message_types.iter().enumerate() {
            indices_by_name.insert(message_type.full_name.clone(), index);
        }
        for message_type in &mut message_types {
            index_fields(message_type, &indices_by_name);
        }
        let Some(&top_level_message_type) = indices_by_name.get(top_level_message_type) else {
            return Err(SchemaError::MissingMessageType {
                message_type: top_level_message_type.to_owned(),
            });
        };
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

/// Adds the message type `descriptor`, declared in `scope`, and the message
/// types declared in it.
fn add_message_type(
    message_types: &mut Vec<MessageType>,
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
        add_message_type(message_types, &full_name, nested_type);
    }
    message_types.push(MessageType {
        full_name,
        descriptor,
        fields_by_name: FxHashMap::default(),
    });
}

fn index_fields(message_type: &mut MessageType, indices_by_name: &FxHashMap<String, usize>) {
    let mut fields_by_name =
        FxHashMap::with_capacity_and_hasher(message_type.descriptor.field.len(), FxBuildHasher);
    for (index, field) in message_type.descriptor.field.iter().enumerate() {
        let message_field_type = match field.r#type() {
            Type::Message | Type::Group => {
                // A descriptor set from protoc has only fully-qualified type
                // names, which start with a `.`.
                let message_field_type = field
                    .type_name()
                    .strip_prefix('.')
                    .and_then(|full_name| indices_by_name.get(full_name))
                    .expect("protoc writes the full name of a message type in the set");
                Some(*message_field_type)
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
}

#[cfg(test)]
mod tests {
    use super::{Schema, SchemaError};
    use crate::test_support::valid_schemas;
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
    fn nested_message_type_is_not_found_by_its_short_name() -> Result<()> {
        verify_that!(
            Schema::from_descriptor_set(valid_schemas()?, "Project").err(),
            some(eq(&SchemaError::MissingMessageType {
                message_type: "Project".to_owned()
            }))
        )
    }
}
