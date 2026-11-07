//! The syntax tree of a DCL file, with the location of every node.

use crate::source_location::SourceLocation;

#[derive(Debug, PartialEq, Eq)]
pub struct ParsedFile<'source> {
    pub top_level_messages: Vec<TopLevelMessage<'source>>,
}

#[derive(Debug, PartialEq, Eq)]
pub struct TopLevelMessage<'source> {
    pub name: FieldName<'source>,
    pub value: MessageValue<'source>,
    pub location: SourceLocation,
}

#[derive(Debug, PartialEq, Eq)]
pub struct Field<'source> {
    pub name: FieldName<'source>,
    pub value: Value<'source>,
    pub location: SourceLocation,
}

#[derive(Debug, PartialEq, Eq)]
pub struct FieldName<'source> {
    pub text: &'source str,
    pub location: SourceLocation,
}

#[derive(Debug, PartialEq, Eq)]
pub enum Value<'source> {
    String(Scalar<'source>),
    Integer(Scalar<'source>),
    Float(Scalar<'source>),
    Enum(Scalar<'source>),
    Message(MessageValue<'source>),
    Repeated(RepeatedValue<'source>),
}

impl Value<'_> {
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
pub struct Scalar<'source> {
    /// The source text of the value, including a string's quotes.
    pub text: &'source str,
    pub location: SourceLocation,
}

#[derive(Debug, PartialEq, Eq)]
pub struct MessageValue<'source> {
    pub fields: Vec<Field<'source>>,
    pub location: SourceLocation,
}

#[derive(Debug, PartialEq, Eq)]
pub struct RepeatedValue<'source> {
    pub values: Vec<Value<'source>>,
    pub location: SourceLocation,
}
