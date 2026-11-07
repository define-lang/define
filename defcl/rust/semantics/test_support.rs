//! The descriptor sets of the test schemas.

use descriptor_proto::google::protobuf::FileDescriptorSet;
use googletest::prelude::*;
use prost::Message;
use runfiles::Runfiles;

/// The descriptor set of the schemas in `defcl/testdata/valid`.
pub fn valid_schemas() -> Result<FileDescriptorSet> {
    read_runfile(env!("VALID_SCHEMAS"))
}

/// The descriptor set of the schemas in `defcl/testdata/invalid/schemas`, which
/// break DCL's rules for schemas.
pub fn invalid_schemas() -> Result<FileDescriptorSet> {
    read_runfile(env!("INVALID_SCHEMAS"))
}

/// The descriptor set of the schemas in `defcl/testdata/invalid/semantics`.
pub fn invalid_semantics_schemas() -> Result<FileDescriptorSet> {
    read_runfile(env!("INVALID_SEMANTICS_SCHEMAS"))
}

/// Decodes the descriptor set in the runfile at `rlocation_path`.
fn read_runfile(rlocation_path: &str) -> Result<FileDescriptorSet> {
    let runfiles = Runfiles::create().or_fail()?;
    let path = runfiles::rlocation!(runfiles, rlocation_path).or_fail()?;
    FileDescriptorSet::decode(std::fs::read(path).or_fail()?.as_slice()).or_fail()
}
