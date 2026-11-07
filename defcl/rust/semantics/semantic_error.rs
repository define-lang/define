//! The errors that checking a DCL file against its schema can end in.

use defcl_parser::{SourceLines, SourceLocation};
use derive_more::{Display, Error};
use strum::{IntoStaticStr, VariantNames};

#[derive(Debug, PartialEq, Eq, Display, Error)]
#[display("{field_name}: {kind}")]
pub struct SemanticError {
    pub kind: SemanticErrorKind,
    pub location: SourceLocation,
    /// The name of the field that the error is in.
    pub field_name: String,
}

impl SemanticError {
    /// The error as the Define compiler shows errors: the location as
    /// `SourceLocation::render` shows it in `source_lines`, the text of the
    /// file at `file_path`, then the message.
    #[must_use]
    pub fn render(&self, source_lines: &SourceLines, file_path: Option<&str>) -> String {
        format!("{}\n{self}", self.location.render(source_lines, file_path))
    }
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

#[cfg(test)]
mod tests {
    use super::{SemanticError, SemanticErrorKind};
    use defcl_parser::{SourceLines, SourceLocation};
    use googletest::prelude::*;

    #[gtest]
    fn shows_its_location_then_its_message() -> Result<()> {
        verify_that!(
            SemanticError {
                kind: SemanticErrorKind::IntegerEnum,
                location: SourceLocation {
                    line: 2,
                    column: 13,
                    end_line: 2,
                    end_column: 13
                },
                field_name: "status".to_owned(),
            }
            .render(&SourceLines::new("config: {\n    status: 1\n}\n"), None),
            eq(
                "line 2, column 13\n    status: 1\n            ^\nstatus: Integer enum values are not allowed"
            )
        )
    }
}
