//! The errors that checking a DCL file against its schema can end in.

use defcl_parser::SourceLocation;

#[derive(Debug, PartialEq, Eq)]
pub enum SemanticError {
    /// A field name that the message type has no field for.
    UnknownFieldName {
        location: SourceLocation,
        field_name: String,
        /// The full name of the message type.
        message_type: String,
    },
    /// A field written a second time in the same message. The location is the
    /// second field name.
    FieldWrittenTwice {
        location: SourceLocation,
        field_name: String,
    },
    /// A repeated field whose value is not a repeated value. The location is
    /// the value.
    RepeatedFieldWithoutBrackets {
        location: SourceLocation,
        field_name: String,
    },
    /// A repeated value for a field that is not repeated. The location is the
    /// repeated value.
    NonRepeatedFieldWithBrackets {
        location: SourceLocation,
        field_name: String,
    },
    /// A message value for a field whose type is not a message type. The
    /// location is the message value.
    MessageValueForScalarField {
        location: SourceLocation,
        field_name: String,
    },
    /// A string, number or enum value for a field whose type is a message
    /// type. The location is the value.
    ScalarForMessageField {
        location: SourceLocation,
        field_name: String,
    },
    /// An integer as the value of an enum field. The location is the integer.
    IntegerEnum {
        location: SourceLocation,
        field_name: String,
    },
}
