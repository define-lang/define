//! Finding the location of the field that a field path names in a defcl file.

use crate::syntax_tree::{Field, ParsedFile, Value};
use derive_more::Display;
use source_rendering::SourceLocation;

/// One element of a field path.
// TODO: Add map keys once the spec decides how defcl files write maps.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum FieldPathElement<'path> {
    /// A field of the message before it, by name.
    Field(&'path str),
    /// An element of the repeated value before it, by index.
    Index(usize),
}

/// Why a file has no location for a field path.
#[derive(Debug, PartialEq, Eq, Display)]
pub enum LocationError {
    #[display("the field path is empty")]
    EmptyPath,
    #[display("the field path starts with an index instead of a top-level message")]
    PathStartsWithIndex,
    #[display("the file does not contain the field path's top-level message")]
    TopLevelMessageNotWritten,
}

impl ParsedFile {
    /// The location of the field at `path` in the file, whose source is
    /// `source`. The first element of `path` is a top-level message. A field
    /// that appears in the file is located at its value. A field that is
    /// missing from the file is located at the name of the nearest field on
    /// `path` that appears in the file, or at that field's value if it is an
    /// element of a repeated field, which has no name.
    ///
    /// # Errors
    ///
    /// Returns why the path has no location if its top-level message does not
    /// appear in the file.
    pub fn location_of(
        &self,
        source: &str,
        path: &[FieldPathElement],
    ) -> Result<SourceLocation, LocationError> {
        let (&first, rest) = path.split_first().ok_or(LocationError::EmptyPath)?;
        let FieldPathElement::Field(top_level_name) = first else {
            return Err(LocationError::PathStartsWithIndex);
        };
        let top_level_message = self
            .top_level_messages
            .iter()
            .find(|message| message.name.text.of(source) == top_level_name)
            .ok_or(LocationError::TopLevelMessageNotWritten)?;
        // The name and value of the nearest field on the path so far.
        let mut name = Some(top_level_message.name.location);
        let mut value_location = top_level_message.value.location;
        // The fields of the value at the path so far, if it is a message
        // value, and its elements, if it is a repeated value.
        let mut fields: &[Field] = &top_level_message.value.fields;
        let mut elements: &[Value] = &[];
        for element in rest {
            let value = match *element {
                FieldPathElement::Field(field_name) => {
                    let Some(field) = fields
                        .iter()
                        .find(|field| field.name.text.of(source) == field_name)
                    else {
                        return Ok(name.unwrap_or(value_location));
                    };
                    name = Some(field.name.location);
                    &field.value
                }
                FieldPathElement::Index(index) => {
                    let Some(element_value) = elements.get(index) else {
                        return Ok(name.unwrap_or(value_location));
                    };
                    name = None;
                    element_value
                }
            };
            value_location = value.location();
            (fields, elements) = match value {
                Value::Message(message) => (message.fields.as_slice(), [].as_slice()),
                Value::Repeated(repeated) => ([].as_slice(), repeated.values.as_slice()),
                _ => ([].as_slice(), [].as_slice()),
            };
        }
        Ok(value_location)
    }
}

#[cfg(test)]
mod tests {
    use super::FieldPathElement::{Field, Index};
    use super::{FieldPathElement, LocationError};
    use crate::parse;
    use googletest::prelude::*;
    use source_rendering::{Position, SourceLocation};

    const SOURCE: &str = include_str!("../../testdata/valid/field_paths.defcl");

    const fn location(line: u32, column: u32, end_line: u32, end_column: u32) -> SourceLocation {
        SourceLocation {
            start: Position { line, column },
            end: Position {
                line: end_line,
                column: end_column,
            },
        }
    }

    fn location_of(
        path: &[FieldPathElement],
    ) -> Result<std::result::Result<SourceLocation, LocationError>> {
        let parsed = parse(SOURCE);
        verify_that!(parsed.errors, is_empty())?;
        Ok(parsed.file.or_fail()?.location_of(SOURCE, path))
    }

    #[gtest]
    fn top_level_message() -> Result<()> {
        verify_that!(
            location_of(&[Field("project")])?,
            ok(eq(&location(1, 10, 18, 1)))
        )
    }

    #[gtest]
    fn field_of_a_second_top_level_message() -> Result<()> {
        verify_that!(
            location_of(&[Field("settings"), Field("log_level")])?,
            ok(eq(&location(20, 14, 20, 14)))
        )
    }

    #[gtest]
    fn field_of_a_nested_message() -> Result<()> {
        verify_that!(
            location_of(&[Field("project"), Field("database"), Field("host")])?,
            ok(eq(&location(4, 11, 4, 21)))
        )
    }

    #[gtest]
    fn element_of_a_repeated_field_has_no_name() -> Result<()> {
        verify_that!(
            location_of(&[Field("project"), Field("dependencies"), Index(1)])?,
            ok(eq(&location(10, 5, 12, 5)))
        )
    }

    #[gtest]
    fn field_of_an_element_of_a_repeated_field() -> Result<()> {
        verify_that!(
            location_of(&[
                Field("project"),
                Field("dependencies"),
                Index(1),
                Field("universe")
            ])?,
            ok(eq(&location(11, 17, 11, 19)))
        )
    }

    #[gtest]
    fn scalar_element_of_a_repeated_field() -> Result<()> {
        verify_that!(
            location_of(&[Field("project"), Field("tags"), Index(0)])?,
            ok(eq(&location(15, 5, 15, 7)))
        )
    }

    #[gtest]
    fn field_missing_from_the_file_finds_its_message_s_name() -> Result<()> {
        verify_that!(
            location_of(&[Field("project"), Field("owner")])?,
            ok(eq(&location(1, 1, 1, 7)))
        )
    }

    #[gtest]
    fn field_missing_from_an_element_finds_the_element() -> Result<()> {
        verify_that!(
            location_of(&[
                Field("project"),
                Field("dependencies"),
                Index(1),
                Field("owner")
            ])?,
            ok(eq(&location(10, 5, 12, 5)))
        )
    }

    #[gtest]
    fn index_past_the_last_element_finds_the_repeated_field() -> Result<()> {
        verify_that!(
            location_of(&[Field("project"), Field("dependencies"), Index(2)])?,
            ok(eq(&location(6, 3, 6, 14)))
        )
    }

    #[gtest]
    fn index_of_a_field_that_is_not_repeated_finds_the_field() -> Result<()> {
        verify_that!(
            location_of(&[Field("project"), Field("name"), Index(0)])?,
            ok(eq(&location(2, 3, 2, 6)))
        )
    }

    #[gtest]
    fn field_of_a_scalar_finds_the_scalar_field() -> Result<()> {
        verify_that!(
            location_of(&[Field("project"), Field("name"), Field("length")])?,
            ok(eq(&location(2, 3, 2, 6)))
        )
    }

    #[gtest]
    fn index_of_a_top_level_message_finds_the_message() -> Result<()> {
        verify_that!(
            location_of(&[Field("settings"), Index(0)])?,
            ok(eq(&location(19, 1, 19, 8)))
        )
    }

    #[gtest]
    fn top_level_message_missing_from_the_file() -> Result<()> {
        verify_that!(
            location_of(&[Field("metadata"), Field("name")])?,
            err(eq(&LocationError::TopLevelMessageNotWritten))
        )
    }

    #[gtest]
    fn path_that_starts_with_an_index() -> Result<()> {
        verify_that!(
            location_of(&[Index(0), Field("project")])?,
            err(eq(&LocationError::PathStartsWithIndex))
        )
    }

    #[gtest]
    fn empty_path() -> Result<()> {
        verify_that!(location_of(&[])?, err(eq(&LocationError::EmptyPath)))
    }
}
