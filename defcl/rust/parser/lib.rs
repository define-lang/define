//! The Define Configuration Language (defcl) parser, which tracks the source
//! location of every part of a file.

#[cfg(test)]
mod error_messages_test;
mod field_path;
mod parser;
#[cfg(test)]
mod parser_test;
mod scanner;
mod syntax_error;
mod syntax_tree;
mod vector_scan;

pub use field_path::{FieldPathElement, LocationError};
pub use parser::{DecodeError, LayoutFix, ParseResult, decode, parse, parse_with_layout_fixes};
pub use syntax_error::{SyntaxError, SyntaxErrorKind};
pub use syntax_tree::{
    Field, FieldName, MessageValue, ParsedFile, RepeatedValue, Scalar, TextRange, TopLevelMessage,
    Value,
};
