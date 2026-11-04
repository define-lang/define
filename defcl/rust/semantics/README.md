# defcl_semantics

Checks a parsed DCL file against the protobuf schema of its top-level message
type. The input is the `ParsedFile` from `defcl_parser`, which only checks
syntax.

## Usage

1. Decode a binary `FileDescriptorSet` that holds the schema.
2. Build a `Schema` with
   `Schema::from_descriptor_set(file_descriptor_set, "pkg.TopLevelMessage")`. It
   indexes every message type and resolves message-typed fields to their message
   types. Build it once and reuse it for every file with that top-level message
   type.
3. Call `check_semantics(&parsed_file, &schema)`. It returns the first
   `SemanticError` it finds.
