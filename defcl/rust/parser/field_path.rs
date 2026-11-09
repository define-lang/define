//! Finding where a DCL file writes the field that a field path names.

use crate::syntax_tree::{Field, ParsedFile, Value};
use source_rendering::SourceLocation;

/// One element of a field path.
// TODO: Add map keys once the spec decides how DCL files write maps.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum FieldPathElement<'path> {
    /// A field of the message before it, by name.
    Field(&'path str),
    /// An element of the repeated value before it, by index.
    Index(usize),
}

impl ParsedFile<'_> {
    /// Where the file writes the field at `path`, whose first element is a
    /// top-level message: its value, or, if the file does not write it, the
    /// name of the nearest field on `path` that the file writes, or that
    /// field's value if it is an element of a repeated field, which has no
    /// name. `None` if the file does not write the path's top-level message.
    #[must_use]
    pub fn location_of(&self, path: &[FieldPathElement]) -> Option<SourceLocation> {
        let (&FieldPathElement::Field(top_level_name), rest) = path.split_first()? else {
            return None;
        };
        let top_level_message = self
            .top_level_messages
            .iter()
            .find(|message| message.name.text == top_level_name)?;
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
                    let Some(field) = fields.iter().find(|field| field.name.text == field_name)
                    else {
                        return Some(name.unwrap_or(value_location));
                    };
                    name = Some(field.name.location);
                    &field.value
                }
                FieldPathElement::Index(index) => {
                    let Some(element_value) = elements.get(index) else {
                        return Some(name.unwrap_or(value_location));
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
        Some(value_location)
    }
}

#[cfg(test)]
mod tests {
    use super::FieldPathElement;
    use super::FieldPathElement::{Field, Index};
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

    fn location_of(path: &[FieldPathElement]) -> Result<Option<SourceLocation>> {
        Ok(parse(SOURCE).or_fail()?.location_of(path))
    }

    #[gtest]
    fn top_level_message() -> Result<()> {
        verify_that!(
            location_of(&[Field("project")])?,
            some(eq(location(1, 10, 13, 1)))
        )
    }

    #[gtest]
    fn field_of_a_second_top_level_message() -> Result<()> {
        verify_that!(
            location_of(&[Field("settings"), Field("log_level")])?,
            some(eq(location(15, 16, 15, 16)))
        )
    }

    #[gtest]
    fn field_of_a_nested_message() -> Result<()> {
        verify_that!(
            location_of(&[Field("project"), Field("database"), Field("host")])?,
            some(eq(location(4, 15, 4, 25)))
        )
    }

    #[gtest]
    fn element_of_a_repeated_field_has_no_name() -> Result<()> {
        verify_that!(
            location_of(&[Field("project"), Field("dependencies"), Index(1)])?,
            some(eq(location(8, 9, 10, 9)))
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
            some(eq(location(9, 23, 9, 25)))
        )
    }

    #[gtest]
    fn scalar_element_of_a_repeated_field() -> Result<()> {
        verify_that!(
            location_of(&[Field("project"), Field("tags"), Index(0)])?,
            some(eq(location(12, 12, 12, 14)))
        )
    }

    #[gtest]
    fn field_that_the_file_does_not_write_finds_its_message_s_name() -> Result<()> {
        verify_that!(
            location_of(&[Field("project"), Field("owner")])?,
            some(eq(location(1, 1, 1, 7)))
        )
    }

    #[gtest]
    fn field_that_an_element_does_not_write_finds_the_element() -> Result<()> {
        verify_that!(
            location_of(&[
                Field("project"),
                Field("dependencies"),
                Index(1),
                Field("owner")
            ])?,
            some(eq(location(8, 9, 10, 9)))
        )
    }

    #[gtest]
    fn index_past_the_last_element_finds_the_repeated_field() -> Result<()> {
        verify_that!(
            location_of(&[Field("project"), Field("dependencies"), Index(2)])?,
            some(eq(location(6, 5, 6, 16)))
        )
    }

    #[gtest]
    fn index_of_a_field_that_is_not_repeated_finds_the_field() -> Result<()> {
        verify_that!(
            location_of(&[Field("project"), Field("name"), Index(0)])?,
            some(eq(location(2, 5, 2, 8)))
        )
    }

    #[gtest]
    fn field_of_a_scalar_finds_the_scalar_field() -> Result<()> {
        verify_that!(
            location_of(&[Field("project"), Field("name"), Field("length")])?,
            some(eq(location(2, 5, 2, 8)))
        )
    }

    #[gtest]
    fn index_of_a_top_level_message_finds_the_message() -> Result<()> {
        verify_that!(
            location_of(&[Field("settings"), Index(0)])?,
            some(eq(location(14, 1, 14, 8)))
        )
    }

    #[gtest]
    fn top_level_message_that_the_file_does_not_write() -> Result<()> {
        verify_that!(location_of(&[Field("metadata"), Field("name")])?, none())
    }

    #[gtest]
    fn path_that_starts_with_an_index() -> Result<()> {
        verify_that!(location_of(&[Index(0), Field("project")])?, none())
    }

    #[gtest]
    fn empty_path() -> Result<()> {
        verify_that!(location_of(&[])?, none())
    }
}
