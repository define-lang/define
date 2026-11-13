//! The syntax tree of a defcl file, with the location of every node.

use source_rendering::SourceLocation;

/// The bytes of a node's text in the source of the file, by byte offset.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct TextRange {
    pub start: usize,
    pub end: usize,
}

impl TextRange {
    /// The text in `source`, the source of the file the range is in.
    #[must_use]
    pub fn of(self, source: &str) -> &str {
        &source[self.start..self.end]
    }
}

#[derive(Debug, PartialEq, Eq)]
pub struct ParsedFile {
    pub top_level_messages: Vec<TopLevelMessage>,
}

#[derive(Debug, PartialEq, Eq)]
pub struct TopLevelMessage {
    pub name: FieldName,
    pub value: MessageValue,
    pub location: SourceLocation,
}

#[derive(Debug, PartialEq, Eq)]
pub struct Field {
    pub name: FieldName,
    pub value: Value,
    pub location: SourceLocation,
}

#[derive(Debug, PartialEq, Eq)]
pub struct FieldName {
    pub text: TextRange,
    pub location: SourceLocation,
}

#[derive(Debug, PartialEq, Eq)]
pub enum Value {
    String(Scalar),
    Integer(Scalar),
    Float(Scalar),
    Enum(Scalar),
    Message(MessageValue),
    Repeated(RepeatedValue),
}

impl Value {
    #[must_use]
    pub const fn location(&self) -> SourceLocation {
        match self {
            Self::String(scalar)
            | Self::Integer(scalar)
            | Self::Float(scalar)
            | Self::Enum(scalar) => scalar.location,
            Self::Message(message) => message.location,
            Self::Repeated(repeated) => repeated.location,
        }
    }
}

/// A string, integer, float, or enum value, as it is written in the source.
#[derive(Debug, PartialEq, Eq)]
pub struct Scalar {
    /// The source text of the value, including a string's quotes.
    pub text: TextRange,
    pub location: SourceLocation,
}

#[derive(Debug, PartialEq, Eq)]
pub struct MessageValue {
    pub fields: Vec<Field>,
    pub location: SourceLocation,
}

#[derive(Debug, PartialEq, Eq)]
pub struct RepeatedValue {
    pub values: Vec<Value>,
    pub location: SourceLocation,
}
