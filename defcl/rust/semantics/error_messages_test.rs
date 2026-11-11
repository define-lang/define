//! The full message of every semantic error: its location, with its source
//! line and carets under the part that it covers, then its message; and the
//! message of every schema error, which has no location.

use crate::test_support::{invalid_schemas, invalid_semantics_schemas, valid_schemas};
use crate::{Schema, SemanticError, SemanticErrorKind, check_semantics};
use defcl_parser::parse;
use googletest::prelude::*;
use indoc::indoc;
use source_rendering::SourceLines;
use strum::VariantNames as _;

const PACKAGE: &str = "defcl.testdata.invalid.semantics.schemas";

/// Each test data file, with the name in `PACKAGE` of the top-level message
/// type of its schema, and every semantic error in it as the checks report
/// them, in order and separated by blank lines.
const CASES: [(&str, &str, &str); 16] = [
    (
        include_str!("../../testdata/invalid/semantics/unknown_field_names/nested_field.defcl"),
        "FieldWrittenTwiceFile",
        indoc! {r#"
            line 5, column 7
                version: "1.0"
                ^^^^^^^
            version: defcl.testdata.invalid.semantics.schemas.FieldWrittenTwiceFile.Dependency has no field with this name"#},
    ),
    (
        include_str!(
            "../../testdata/invalid/semantics/field_order/field_after_higher_number.defcl"
        ),
        "WrongValueKindsFile",
        indoc! {r#"
            line 3, column 3
                name: "a"
                ^^^^
            name: Fields must be written in the order of their field numbers, so this field must come before 'count'"#},
    ),
    (
        include_str!("../../testdata/invalid/semantics/field_written_twice/scalar_field.defcl"),
        "FieldWrittenTwiceFile",
        indoc! {r#"
            line 3, column 3
                universe_name: "other"
                ^^^^^^^^^^^^^
            universe_name: Each field may be specified only once, but this one is specified more than once"#},
    ),
    (
        include_str!("../../testdata/invalid/semantics/oneofs/second_field.defcl"),
        "OneofsFile",
        indoc! {r#"
            line 3, column 3
                url: "b"
                ^^^
            url: Only one field of the oneof defcl.testdata.invalid.semantics.schemas.OneofsFile.Config.source can be written in a message value"#},
    ),
    (
        include_str!(
            "../../testdata/invalid/semantics/multiple_errors/repeated_field_without_brackets.defcl"
        ),
        "MultipleErrorsFile",
        indoc! {"
            line 2, column 13
                replicas: {
                          ^
            replicas: Repeated fields must use bracket [] syntax"},
    ),
    (
        include_str!(
            "../../testdata/invalid/semantics/non_repeated_fields_with_brackets/scalar_field.defcl"
        ),
        "NonRepeatedFieldsWithBracketsFile",
        indoc! {"
            line 2, column 9
                name: [
                      ^
            name: Only repeated fields can use bracket [] syntax"},
    ),
    (
        include_str!(
            "../../testdata/invalid/semantics/message_values_for_scalar_fields/top_level_field.defcl"
        ),
        "MessageValuesForScalarFieldsFile",
        indoc! {"
            line 1, column 8
                count: {
                       ^
            count: The field is not a message field, so its value cannot be a message value"},
    ),
    (
        include_str!("../../testdata/invalid/semantics/scalars_for_message_fields/string.defcl"),
        "ScalarsForMessageFieldsFile",
        indoc! {r#"
            line 2, column 13
                database: "localhost"
                          ^^^^^^^^^^^
            database: The field is a message field, so its value must be a message value"#},
    ),
    (
        include_str!("../../testdata/invalid/semantics/wrong_value_kinds/string_field.defcl"),
        "WrongValueKindsFile",
        indoc! {"
            line 2, column 9
                name: 5
                      ^
            name: The field is a string field, so its value must be a string"},
    ),
    (
        include_str!("../../testdata/invalid/semantics/wrong_value_kinds/integer_field.defcl"),
        "WrongValueKindsFile",
        indoc! {"
            line 2, column 10
                count: 5.5
                       ^^^
            count: The field is an integer field, so its value must be an integer"},
    ),
    (
        include_str!("../../testdata/invalid/semantics/wrong_value_kinds/float_field.defcl"),
        "WrongValueKindsFile",
        indoc! {"
            line 2, column 10
                ratio: 3
                       ^
            ratio: The field is a floating-point field, so its value must be a floating-point number, such as 1.0"},
    ),
    (
        include_str!("../../testdata/invalid/semantics/wrong_value_kinds/enum_field.defcl"),
        "WrongValueKindsFile",
        indoc! {r#"
            line 2, column 11
                status: "STATUS_ACTIVE"
                        ^^^^^^^^^^^^^^^
            status: The field is an enum field, so its value must be the name of one of its enum's values"#},
    ),
    (
        include_str!("../../testdata/invalid/semantics/enums/integer_enum.defcl"),
        "IntegerEnumFile",
        indoc! {"
            line 2, column 11
                status: 0
                        ^
            status: Integer enum values are not allowed"},
    ),
    (
        include_str!("../../testdata/invalid/semantics/out_of_range/int32_above_maximum.defcl"),
        "OutOfRangeFile",
        indoc! {"
            line 2, column 16
                int32_value: 2147483648
                             ^^^^^^^^^^
            int32_value: int32 fields take integers from -2147483648 to 2147483647"},
    ),
    (
        include_str!(
            "../../testdata/invalid/semantics/out_of_range/float_rounding_to_infinity.defcl"
        ),
        "OutOfRangeFile",
        indoc! {"
            line 2, column 16
                float_value: 340282356779733661637539395458142568448.0
                             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
            float_value: The value is too large in magnitude for a float field"},
    ),
    (
        include_str!("../../testdata/invalid/semantics/wrong_value_kinds/unknown_enum_value.defcl"),
        "WrongValueKindsFile",
        indoc! {"
            line 2, column 11
                status: ACTIVE
                        ^^^^^^
            status: defcl.testdata.invalid.semantics.schemas.WrongValueKindsFile.Status has no value with this name"},
    ),
];

/// The semantic errors in `source`, checked against the schema whose
/// top-level message type is `top_level_message_type` in `PACKAGE`.
fn semantic_errors(source: &str, top_level_message_type: &str) -> Result<Vec<SemanticError>> {
    let schema = Schema::from_descriptor_set(
        invalid_semantics_schemas()?,
        &format!("{PACKAGE}.{top_level_message_type}"),
    )
    .or_fail()?;
    let parsed = parse(source);
    verify_that!(parsed.errors, is_empty())?;
    Ok(check_semantics(&parsed.file.or_fail()?, &schema))
}

/// Every semantic error in `source`, rendered as its location, its source line
/// with carets, then its message.
fn rendered_errors(source: &str, top_level_message_type: &str) -> Result<String> {
    let errors = semantic_errors(source, top_level_message_type)?;
    let lines = SourceLines::new(source);
    let mut rendered = Vec::with_capacity(errors.len());
    for error in &errors {
        rendered.push(format!("{}\n{error}", lines.render(error.location, None)));
    }
    Ok(rendered.join("\n\n"))
}

#[gtest]
fn each_file_renders_its_errors() -> Result<()> {
    for (source, top_level_message_type, expected) in CASES {
        expect_that!(
            rendered_errors(source, top_level_message_type)?,
            eq(expected)
        );
    }
    Ok(())
}

#[gtest]
fn every_kind_of_semantic_error_has_a_case() -> Result<()> {
    let mut kinds: Vec<&str> = Vec::new();
    for (source, top_level_message_type, _) in CASES {
        for error in &semantic_errors(source, top_level_message_type)? {
            kinds.push((&error.kind).into());
        }
    }
    kinds.sort_unstable();
    kinds.dedup();
    let mut variants = SemanticErrorKind::VARIANTS.to_vec();
    variants.sort_unstable();
    verify_that!(kinds, eq(&variants))
}

#[gtest]
fn each_schema_error_has_its_message() -> Result<()> {
    let cases = [
        (
            valid_schemas()?,
            "defcl.testdata.valid.schemas.NoSuchFile",
            indoc! {"
            Cannot create a DCL schema: the FileDescriptorSet has no message type named defcl.testdata.valid.schemas.NoSuchFile to use as the top-level message type"},
        ),
        (
            invalid_schemas()?,
            "defcl.testdata.invalid.schemas.ProhibitedFieldTypesFile",
            indoc! {"
                Cannot create a DCL schema:
                  - defcl.testdata.invalid.schemas.ProhibitedFieldTypesFile.Config.enabled is a bool field, which DCL does not allow
                  - defcl.testdata.invalid.schemas.ProhibitedFieldTypesFile.Config.data is a bytes field, which DCL does not allow
                  - defcl.testdata.invalid.schemas.ProhibitedFieldTypesFile.Config.extra is a google.protobuf.Any field, which DCL does not allow"},
        ),
        (
            invalid_schemas()?,
            "defcl.testdata.invalid.schemas.RequiredFieldFile",
            indoc! {"
                Cannot create a DCL schema:
                  - defcl.testdata.invalid.schemas.RequiredFieldFile.Config.name is a required field, which DCL does not allow"},
        ),
        (
            invalid_schemas()?,
            "defcl.testdata.invalid.schemas.MessageTypeWithoutFieldsFile",
            indoc! {"
                Cannot create a DCL schema:
                  - defcl.testdata.invalid.schemas.MessageTypeWithoutFieldsFile.Config.marker is a defcl.testdata.invalid.schemas.MessageTypeWithoutFieldsFile.Marker field, a message type with no fields, which DCL does not allow"},
        ),
        (
            invalid_schemas()?,
            "defcl.testdata.invalid.schemas.Utf8ValidationNoneFile",
            indoc! {"
                Cannot create a DCL schema:
                  - defcl.testdata.invalid.schemas.Utf8ValidationNoneFile.Config.unchecked does not validate UTF-8, which DCL does not allow"},
        ),
        (
            invalid_schemas()?,
            "defcl.testdata.invalid.schemas.OlderEditionsFile",
            indoc! {"
                Cannot create a DCL schema:
                  - defcl/testdata/invalid/schemas/edition_2023.proto uses EDITION_2023, but the files of a DCL schema must use edition 2024 or later
                  - defcl/testdata/invalid/schemas/proto3_config.proto uses proto3, but the files of a DCL schema must use edition 2024 or later
                  - defcl/testdata/invalid/schemas/proto2_config.proto uses proto2, but the files of a DCL schema must use edition 2024 or later"},
        ),
    ];
    for (descriptor_set, top_level_message_type, expected) in cases {
        expect_that!(
            Schema::from_descriptor_set(descriptor_set, top_level_message_type)
                .err()
                .map(|error| error.to_string()),
            some(eq(expected))
        );
    }
    Ok(())
}
