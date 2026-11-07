# defcl_semantics

Checks a parsed DCL file against the protobuf schema of its top-level message
type. The input is the `ParsedFile` from `defcl_parser`, which only checks
syntax.

## Usage

1. Decode a binary `FileDescriptorSet` that holds the schema.
2. Build a `Schema` with
   `Schema::from_descriptor_set(file_descriptor_set, "pkg.TopLevelMessage")`. It
   indexes every message type and enum type, and resolves message and enum
   fields to their types. It returns every way that the top-level message type,
   and the message types that its fields lead to, break the spec's schema
   restrictions. Build it once and reuse it for every file with that top-level
   message type.
3. Call `check_semantics(&parsed_file, &schema)`. It returns every
   `SemanticError` it finds, in source order.
