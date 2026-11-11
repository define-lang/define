//! The Define Configuration Language (DCL) parser, which tracks the source
//! location of every part of a file.

mod field_path;
mod parser;
#[cfg(test)]
mod parser_test;
mod scanner;
mod syntax_error;
mod syntax_tree;

pub use field_path::FieldPathElement;
pub use parser::{DecodeError, LayoutFix, ParseResult, decode, parse, parse_with_layout_fixes};
pub use syntax_error::{SyntaxError, SyntaxErrorKind};
pub use syntax_tree::{
    Field, FieldName, MessageValue, ParsedFile, RepeatedValue, Scalar, TopLevelMessage, Value,
};
