//! The schema that a DCL file is checked against: the message types of a
//! `FileDescriptorSet`, with lookup tables over their descriptors.

use crate::schema_restrictions::{self, SchemaFile, SchemaViolation};
use derive_more::{Display, Error};
use descriptor_proto::google::protobuf::field_descriptor_proto::{Label, Type};
use descriptor_proto::google::protobuf::{
    DescriptorProto, EnumDescriptorProto, FieldDescriptorProto, FileDescriptorSet,
};
use rustc_hash::{FxBuildHasher, FxHashMap, FxHashSet};
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
    /// A message or enum field's type is not a message type or enum type in
    /// the `FileDescriptorSet`, which protoc never writes.
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

/// The message types and enum types of a `FileDescriptorSet`, and which
/// message type is the type of a whole DCL file.
pub struct Schema {
    message_types: Vec<MessageType>,
    enum_types: Vec<EnumType>,
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

/// An enum type's full name, and the names of its values.
pub(crate) struct EnumType {
    /// The full name, without a leading `.`.
    pub(crate) full_name: String,
    value_names: FxHashSet<String>,
}

/// The type of an integer field.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Display)]
pub enum IntegerFieldType {
    #[display("int32")]
    Int32,
    #[display("int64")]
    Int64,
    #[display("uint32")]
    Uint32,
    #[display("uint64")]
    Uint64,
    #[display("sint32")]
    Sint32,
    #[display("sint64")]
    Sint64,
    #[display("fixed32")]
    Fixed32,
    #[display("fixed64")]
    Fixed64,
    #[display("sfixed32")]
    Sfixed32,
    #[display("sfixed64")]
    Sfixed64,
}

impl IntegerFieldType {
    /// The smallest value that a field of this type can have.
    #[must_use]
    pub const fn minimum(self) -> i128 {
        match self {
            Self::Int32 | Self::Sint32 | Self::Sfixed32 => i32::MIN as i128,
            Self::Int64 | Self::Sint64 | Self::Sfixed64 => i64::MIN as i128,
            Self::Uint32 | Self::Uint64 | Self::Fixed32 | Self::Fixed64 => 0,
        }
    }

    /// The largest value that a field of this type can have.
    #[must_use]
    pub const fn maximum(self) -> i128 {
        match self {
            Self::Int32 | Self::Sint32 | Self::Sfixed32 => i32::MAX as i128,
            Self::Int64 | Self::Sint64 | Self::Sfixed64 => i64::MAX as i128,
            Self::Uint32 | Self::Fixed32 => u32::MAX as i128,
            Self::Uint64 | Self::Fixed64 => u64::MAX as i128,
        }
    }
}

/// The type of a floating-point field.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Display)]
pub enum FloatFieldType {
    #[display("float")]
    Float,
    #[display("double")]
    Double,
}

/// A message type or enum type, by its index in the schema.
#[derive(Clone, Copy)]
enum NamedType {
    Message(usize),
    Enum(usize),
}

struct FieldLookup {
    /// The index of the field in its message type's descriptor.
    index: usize,
    /// The field's type, for a message or enum field.
    named_type: Option<NamedType>,
}

/// A field of a message type in the schema.
pub(crate) struct SchemaField<'schema> {
    pub(crate) descriptor: &'schema FieldDescriptorProto,
    pub(crate) value_type: ValueType<'schema>,
}

/// The kind of value that a field takes.
pub(crate) enum ValueType<'schema> {
    String,
    Integer(IntegerFieldType),
    Float(FloatFieldType),
    Enum(&'schema EnumType),
    Message(&'schema MessageType),
}

impl SchemaField<'_> {
    pub(crate) fn is_repeated(&self) -> bool {
        self.descriptor.label() == Label::Repeated
    }
}

impl MessageType {
    /// The index of the message type of this message type's field `name`, if
    /// it is a message field. `name` must be the name of one of its fields.
    pub(crate) fn field_message_type(&self, name: &str) -> Option<usize> {
        match self.fields_by_name[name].named_type {
            Some(NamedType::Message(index)) => Some(index),
            Some(NamedType::Enum(_)) | None => None,
        }
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
        let mut enum_types = Vec::new();
        let mut files = Vec::with_capacity(file_descriptor_set.file.len());
        for (file_index, mut file) in file_descriptor_set.file.into_iter().enumerate() {
            let scope = file.package.take().unwrap_or_default();
            for descriptor in std::mem::take(&mut file.message_type) {
                add_message_type(
                    &mut message_types,
                    &mut enum_types,
                    file_index,
                    &scope,
                    descriptor,
                );
            }
            for descriptor in std::mem::take(&mut file.enum_type) {
                enum_types.push(EnumType::new(&scope, &descriptor));
            }
            files.push(SchemaFile::new(&file));
        }
        // Message types and enum types share one namespace.
        let mut types_by_name = FxHashMap::with_capacity_and_hasher(
            message_types.len() + enum_types.len(),
            FxBuildHasher,
        );
        for (index, message_type) in message_types.iter().enumerate() {
            types_by_name.insert(message_type.full_name.clone(), NamedType::Message(index));
        }
        for (index, enum_type) in enum_types.iter().enumerate() {
            types_by_name.insert(enum_type.full_name.clone(), NamedType::Enum(index));
        }
        for message_type in &mut message_types {
            index_fields(message_type, &types_by_name)?;
        }
        let Some(&NamedType::Message(top_level_message_type)) =
            types_by_name.get(top_level_message_type)
        else {
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
            enum_types,
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
        let descriptor = &message_type.descriptor.field[lookup.index];
        let value_type = match lookup.named_type {
            Some(NamedType::Message(index)) => ValueType::Message(&self.message_types[index]),
            Some(NamedType::Enum(index)) => ValueType::Enum(&self.enum_types[index]),
            None => scalar_value_type(descriptor.r#type()),
        };
        Some(SchemaField {
            descriptor,
            value_type,
        })
    }
}

/// The kind of value that a field of the type `field_type` takes, for a field
/// that is neither a message field nor an enum field.
fn scalar_value_type(field_type: Type) -> ValueType<'static> {
    match field_type {
        Type::String => ValueType::String,
        Type::Int32 => ValueType::Integer(IntegerFieldType::Int32),
        Type::Int64 => ValueType::Integer(IntegerFieldType::Int64),
        Type::Uint32 => ValueType::Integer(IntegerFieldType::Uint32),
        Type::Uint64 => ValueType::Integer(IntegerFieldType::Uint64),
        Type::Sint32 => ValueType::Integer(IntegerFieldType::Sint32),
        Type::Sint64 => ValueType::Integer(IntegerFieldType::Sint64),
        Type::Fixed32 => ValueType::Integer(IntegerFieldType::Fixed32),
        Type::Fixed64 => ValueType::Integer(IntegerFieldType::Fixed64),
        Type::Sfixed32 => ValueType::Integer(IntegerFieldType::Sfixed32),
        Type::Sfixed64 => ValueType::Integer(IntegerFieldType::Sfixed64),
        Type::Float => ValueType::Float(FloatFieldType::Float),
        Type::Double => ValueType::Float(FloatFieldType::Double),
        // Message and enum fields have a named type, and the schema
        // restrictions prohibit bool and bytes fields.
        Type::Message | Type::Group | Type::Enum | Type::Bool | Type::Bytes => {
            unreachable!("a {field_type:?} field takes no scalar value")
        }
    }
}

impl EnumType {
    /// The enum type `descriptor`, declared in `scope`.
    fn new(scope: &str, descriptor: &EnumDescriptorProto) -> Self {
        let mut value_names =
            FxHashSet::with_capacity_and_hasher(descriptor.value.len(), FxBuildHasher);
        for value in &descriptor.value {
            value_names.insert(value.name().to_owned());
        }
        Self {
            full_name: full_name(scope, descriptor.name()),
            value_names,
        }
    }

    pub(crate) fn has_value(&self, name: &str) -> bool {
        self.value_names.contains(name)
    }
}

fn full_name(scope: &str, name: &str) -> String {
    if scope.is_empty() {
        name.to_owned()
    } else {
        format!("{scope}.{name}")
    }
}

/// Adds the message type `descriptor`, declared in `scope` in the file at
/// `file`, and the message types and enum types declared in it.
fn add_message_type(
    message_types: &mut Vec<MessageType>,
    enum_types: &mut Vec<EnumType>,
    file: usize,
    scope: &str,
    mut descriptor: DescriptorProto,
) {
    let full_name = full_name(scope, descriptor.name());
    for nested_type in std::mem::take(&mut descriptor.nested_type) {
        add_message_type(message_types, enum_types, file, &full_name, nested_type);
    }
    for enum_type in std::mem::take(&mut descriptor.enum_type) {
        enum_types.push(EnumType::new(&full_name, &enum_type));
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
    types_by_name: &FxHashMap<String, NamedType>,
) -> Result<(), SchemaError> {
    let mut fields_by_name =
        FxHashMap::with_capacity_and_hasher(message_type.descriptor.field.len(), FxBuildHasher);
    for (index, field) in message_type.descriptor.field.iter().enumerate() {
        let named_type = match field.r#type() {
            Type::Message | Type::Group | Type::Enum => {
                // A descriptor set from protoc has only fully-qualified type
                // names, which start with a `.`.
                let Some(&named_type) = field
                    .type_name()
                    .strip_prefix('.')
                    .and_then(|full_name| types_by_name.get(full_name))
                else {
                    return Err(SchemaError::UnknownFieldType {
                        message_type: message_type.full_name.clone(),
                        field_name: field.name().to_owned(),
                        type_name: field.type_name().to_owned(),
                    });
                };
                Some(named_type)
            }
            _ => None,
        };
        fields_by_name.insert(field.name().to_owned(), FieldLookup { index, named_type });
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
