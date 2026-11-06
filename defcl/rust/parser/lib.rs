//! The Define Configuration Language (DCL) parser, which tracks the source
//! location of every part of a file.

mod parser;
#[cfg(test)]
mod parser_test;
mod scanner;
mod source_location;
mod syntax_error;
mod syntax_tree;

pub use parser::parse;
pub use source_location::{SourceLines, SourceLocation};
pub use syntax_error::{SyntaxError, SyntaxErrorKind};
pub use syntax_tree::{
    Field, FieldName, MessageValue, ParsedFile, RepeatedValue, Scalar, TopLevelMessage, Value,
};
