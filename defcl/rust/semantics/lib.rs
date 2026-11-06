//! The checks of a parsed DCL file against its schema.

mod schema;
mod semantic_checks;
#[cfg(test)]
mod semantic_checks_test;
mod semantic_error;
#[cfg(test)]
mod test_support;

pub use descriptor_proto::google::protobuf::FileDescriptorSet;
pub use schema::{Schema, SchemaError};
pub use semantic_checks::check_semantics;
pub use semantic_error::{SemanticError, SemanticErrorKind};
