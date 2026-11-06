//! The errors that checking a DCL file against its schema can end in.

use defcl_parser::SourceLocation;
use derive_more::{Display, Error};

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
#[derive(Debug, PartialEq, Eq, Display)]
pub enum SemanticErrorKind {
    /// A field name that the message type has no field for.
    #[display("{message_type} has no field with this name")]
    UnknownFieldName {
        /// The full name of the message type.
        message_type: String,
    },
    /// A field written a second time in the same message. The location is the
    /// second field name.
    #[display("A message value can have each field only once")]
    FieldWrittenTwice,
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
    /// An integer as the value of an enum field. The location is the integer.
    #[display("Integer enum values are not allowed")]
    IntegerEnum,
}
