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

/// Where a DCL file writes the field that a field path names, or, if the file
/// does not write it, the nearest field on the path that it does write.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct FieldPathLocation {
    /// The field's name, or `None` for an element of a repeated field, which
    /// has no name.
    pub name: Option<SourceLocation>,
    pub value: SourceLocation,
    /// Whether the location is of the whole path, rather than of the nearest
    /// field on it that the file writes.
    pub is_whole_path: bool,
}

impl ParsedFile<'_> {
    /// Where the file writes the field at `path`, whose first element is a
    /// top-level message, or the nearest field on `path` that the file writes.
    /// `None` if the file does not write the path's top-level message.
    #[must_use]
    pub fn location_of(&self, path: &[FieldPathElement]) -> Option<FieldPathLocation> {
        let (&FieldPathElement::Field(top_level_name), rest) = path.split_first()? else {
            return None;
        };
        let top_level_message = self
            .top_level_messages
            .iter()
            .find(|message| message.name.text == top_level_name)?;
        let mut location = FieldPathLocation {
            name: Some(top_level_message.name.location),
            value: top_level_message.value.location,
            is_whole_path: true,
        };
        // The fields of the value at the path so far, if it is a message
        // value, and its elements, if it is a repeated value.
        let mut fields: &[Field] = &top_level_message.value.fields;
        let mut elements: &[Value] = &[];
        for element in rest {
            let value = match *element {
                FieldPathElement::Field(name) => {
                    let Some(field) = fields.iter().find(|field| field.name.text == name) else {
                        location.is_whole_path = false;
                        return Some(location);
                    };
                    location.name = Some(field.name.location);
                    &field.value
                }
                FieldPathElement::Index(index) => {
                    let Some(element_value) = elements.get(index) else {
                        location.is_whole_path = false;
                        return Some(location);
                    };
                    location.name = None;
                    element_value
                }
            };
            location.value = value.location();
            (fields, elements) = match value {
                Value::Message(message) => (message.fields.as_slice(), [].as_slice()),
                Value::Repeated(repeated) => ([].as_slice(), repeated.values.as_slice()),
                _ => ([].as_slice(), [].as_slice()),
            };
        }
        Some(location)
    }
}

#[cfg(test)]
mod tests {
    use super::FieldPathElement::{Field, Index};
    use super::{FieldPathElement, FieldPathLocation};
    use crate::parse;
    use googletest::prelude::*;
    use source_rendering::{Position, SourceLocation};

    const SOURCE: &str = include_str!("../../testdata/valid/field_paths.defcl");

    const fn location(
        line: usize,
        column: usize,
        end_line: usize,
        end_column: usize,
    ) -> SourceLocation {
        SourceLocation {
            start: Position { line, column },
            end: Position {
                line: end_line,
                column: end_column,
            },
        }
    }

    fn location_of(path: &[FieldPathElement]) -> Result<Option<FieldPathLocation>> {
        Ok(parse(SOURCE).or_fail()?.location_of(path))
    }

    #[gtest]
    fn top_level_message() -> Result<()> {
        verify_that!(
            location_of(&[Field("project")])?,
            some(eq(FieldPathLocation {
                name: Some(location(1, 1, 1, 7)),
                value: location(1, 10, 13, 1),
                is_whole_path: true,
            }))
        )
    }

    #[gtest]
    fn field_of_a_second_top_level_message() -> Result<()> {
        verify_that!(
            location_of(&[Field("settings"), Field("log_level")])?,
            some(eq(FieldPathLocation {
                name: Some(location(15, 5, 15, 13)),
                value: location(15, 16, 15, 16),
                is_whole_path: true,
            }))
        )
    }

    #[gtest]
    fn field_of_a_nested_message() -> Result<()> {
        verify_that!(
            location_of(&[Field("project"), Field("database"), Field("host")])?,
            some(eq(FieldPathLocation {
                name: Some(location(4, 9, 4, 12)),
                value: location(4, 15, 4, 25),
                is_whole_path: true,
            }))
        )
    }

    #[gtest]
    fn element_of_a_repeated_field_has_no_name() -> Result<()> {
        verify_that!(
            location_of(&[Field("project"), Field("dependencies"), Index(1)])?,
            some(eq(FieldPathLocation {
                name: None,
                value: location(8, 9, 10, 9),
                is_whole_path: true,
            }))
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
            some(eq(FieldPathLocation {
                name: Some(location(9, 13, 9, 20)),
                value: location(9, 23, 9, 25),
                is_whole_path: true,
            }))
        )
    }

    #[gtest]
    fn scalar_element_of_a_repeated_field() -> Result<()> {
        verify_that!(
            location_of(&[Field("project"), Field("tags"), Index(0)])?,
            some(eq(FieldPathLocation {
                name: None,
                value: location(12, 12, 12, 14),
                is_whole_path: true,
            }))
        )
    }

    #[gtest]
    fn field_that_the_file_does_not_write_finds_its_message() -> Result<()> {
        verify_that!(
            location_of(&[Field("project"), Field("owner")])?,
            some(eq(FieldPathLocation {
                name: Some(location(1, 1, 1, 7)),
                value: location(1, 10, 13, 1),
                is_whole_path: false,
            }))
        )
    }

    #[gtest]
    fn index_past_the_last_element_finds_the_repeated_field() -> Result<()> {
        verify_that!(
            location_of(&[Field("project"), Field("dependencies"), Index(2)])?,
            some(eq(FieldPathLocation {
                name: Some(location(6, 5, 6, 16)),
                value: location(6, 19, 11, 5),
                is_whole_path: false,
            }))
        )
    }

    #[gtest]
    fn index_of_a_field_that_is_not_repeated_finds_the_field() -> Result<()> {
        verify_that!(
            location_of(&[Field("project"), Field("name"), Index(0)])?,
            some(eq(FieldPathLocation {
                name: Some(location(2, 5, 2, 8)),
                value: location(2, 11, 2, 19),
                is_whole_path: false,
            }))
        )
    }

    #[gtest]
    fn field_of_a_scalar_finds_the_scalar_field() -> Result<()> {
        verify_that!(
            location_of(&[Field("project"), Field("name"), Field("length")])?,
            some(eq(FieldPathLocation {
                name: Some(location(2, 5, 2, 8)),
                value: location(2, 11, 2, 19),
                is_whole_path: false,
            }))
        )
    }

    #[gtest]
    fn index_of_a_top_level_message_finds_the_message() -> Result<()> {
        verify_that!(
            location_of(&[Field("settings"), Index(0)])?,
            some(eq(FieldPathLocation {
                name: Some(location(14, 1, 14, 8)),
                value: location(14, 11, 16, 1),
                is_whole_path: false,
            }))
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
