//! The errors that checking a DCL file against its schema can end in.

use crate::schema::{FloatFieldType, IntegerFieldType};
use derive_more::{Display, Error};
use source_rendering::SourceLocation;
use strum::{IntoStaticStr, VariantNames};

#[derive(Debug, PartialEq, Eq, Display, Error)]
#[display("{field_name}: {kind}")]
pub struct SemanticError {
    pub kind: SemanticErrorKind,
    pub location: SourceLocation,
    /// The name of the field that the error is in.
    pub field_name: String,
}

/// Which semantic error a `SemanticError` is. Its message does not include the
/// location or the field name.
#[derive(Debug, PartialEq, Eq, Display, IntoStaticStr, VariantNames)]
#[strum(serialize_all = "SCREAMING_SNAKE_CASE")]
pub enum SemanticErrorKind {
    /// A field name that the message type has no field for.
    #[display("{message_type} has no field with this name")]
    UnknownFieldName {
        /// The full name of the message type.
        message_type: String,
    },
    /// A field written after a field of the same message value, or after a
    /// top-level message, with a higher field number. The location is the
    /// field's name.
    #[display(
        "Fields must be written in the order of their field numbers, so this field must come before {later_field}"
    )]
    FieldOutOfOrder {
        /// The name of the field with the highest field number that is written
        /// before it.
        later_field: String,
    },
    /// A field written a second time in the same message. The location is the
    /// second field name.
    #[display("A message value can have each field only once")]
    FieldWrittenTwice,
    /// A field of a oneof that the message value already has another field
    /// of. The location is the second field's name.
    #[display("Only one field of the oneof {oneof} can be written in a message value")]
    SecondFieldOfOneof {
        /// The oneof's full name: its message type's full name, then its own.
        oneof: String,
    },
    /// A repeated field whose value is not a repeated value. The location is
    /// the value.
    #[display("Repeated fields must use bracket [] syntax")]
    RepeatedFieldWithoutBrackets,
    /// A repeated value for a field that is not repeated. The location is the
    /// repeated value.
    #[display("Only repeated fields can use bracket [] syntax")]
    NonRepeatedFieldWithBrackets,
    /// A message value for a field whose type is not a message type. The
    /// location is the message value.
    #[display("The field is not a message field, so its value cannot be a message value")]
    MessageValueForScalarField,
    /// A string, number or enum value for a field whose type is a message
    /// type. The location is the value.
    #[display("The field is a message field, so its value must be a message value")]
    ScalarForMessageField,
    /// A value other than a string for a string field. The location is the
    /// value.
    #[display("The field is a string field, so its value must be a string")]
    NonStringForStringField,
    /// A value other than an integer for an integer field. The location is the
    /// value.
    #[display("The field is an integer field, so its value must be an integer")]
    NonIntegerForIntegerField,
    /// A value other than a floating-point number for a floating-point field,
    /// including an integer. The location is the value.
    #[display(
        "The field is a floating-point field, so its value must be a floating-point number, such as 1.0"
    )]
    NonFloatForFloatField,
    /// A string or floating-point number for an enum field. The location is
    /// the value.
    #[display(
        "The field is an enum field, so its value must be the name of one of its enum's values"
    )]
    NonEnumValueForEnumField,
    /// An integer as the value of an enum field. The location is the integer.
    #[display("Integer enum values are not allowed")]
    IntegerEnum,
    /// An integer outside the range of the field's type. The location is
    /// the integer.
    #[display(
        "{field_type} fields take integers from {} to {}",
        field_type.minimum(),
        field_type.maximum()
    )]
    IntegerOutOfRange { field_type: IntegerFieldType },
    /// A floating-point number too large in magnitude for the field's type,
    /// which rounds to infinity in it. The location is the number.
    #[display("The value is too large in magnitude for a {field_type} field")]
    FloatOutOfRange { field_type: FloatFieldType },
    /// An enum value whose name is not a value of the field's enum type. The
    /// location is the enum value.
    #[display("{enum_type} has no value with this name")]
    UnknownEnumValue {
        /// The full name of the enum type.
        enum_type: String,
    },
}
