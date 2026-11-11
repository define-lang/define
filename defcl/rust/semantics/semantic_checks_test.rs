use crate::test_support::{invalid_semantics_schemas, valid_schemas};
use crate::{FileDescriptorSet, Schema, SemanticError, SemanticErrorKind, check_semantics};
use defcl_parser::parse;
use googletest::prelude::*;
use source_rendering::{Position, SourceLocation};

/// Parses `source` and checks it against the schema in `descriptor_set` whose
/// top-level message type is `top_level_message_type`.
fn check_semantics_of_source(
    source: &str,
    descriptor_set: FileDescriptorSet,
    top_level_message_type: &str,
) -> Result<Vec<SemanticError>> {
    let schema = Schema::from_descriptor_set(descriptor_set, top_level_message_type).or_fail()?;
    let parsed = parse(source);
    verify_that!(parsed.errors, is_empty())?;
    Ok(check_semantics(&parsed.file.or_fail()?, &schema))
}

mod valid_files {
    use super::*;

    #[gtest]
    fn single_toplevel() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!("../../testdata/valid/single_toplevel.defcl"),
                valid_schemas()?,
                "defcl.testdata.valid.schemas.SingleToplevelFile",
            )?,
            is_empty()
        )
    }

    #[gtest]
    fn integers() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!("../../testdata/valid/integers.defcl"),
                valid_schemas()?,
                "defcl.testdata.valid.schemas.IntegersFile",
            )?,
            is_empty()
        )
    }

    #[gtest]
    fn number_ranges() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!("../../testdata/valid/number_ranges.defcl"),
                valid_schemas()?,
                "defcl.testdata.valid.schemas.NumberRangesFile",
            )?,
            is_empty()
        )
    }

    #[gtest]
    fn oneofs() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!("../../testdata/valid/oneofs.defcl"),
                valid_schemas()?,
                "defcl.testdata.valid.schemas.OneofsFile",
            )?,
            is_empty()
        )
    }

    #[gtest]
    fn nested_messages() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!("../../testdata/valid/nested_messages.defcl"),
                valid_schemas()?,
                "defcl.testdata.valid.schemas.NestedMessagesFile",
            )?,
            is_empty()
        )
    }

    #[gtest]
    fn repeated_messages() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!("../../testdata/valid/repeated_messages.defcl"),
                valid_schemas()?,
                "defcl.testdata.valid.schemas.RepeatedMessagesFile",
            )?,
            is_empty()
        )
    }

    #[gtest]
    fn strings() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!("../../testdata/valid/strings.defcl"),
                valid_schemas()?,
                "defcl.testdata.valid.schemas.StringsFile",
            )?,
            is_empty()
        )
    }

    #[gtest]
    fn enums() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!("../../testdata/valid/enums.defcl"),
                valid_schemas()?,
                "defcl.testdata.valid.schemas.EnumsFile",
            )?,
            is_empty()
        )
    }

    #[gtest]
    fn floats() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!("../../testdata/valid/floats.defcl"),
                valid_schemas()?,
                "defcl.testdata.valid.schemas.FloatsFile",
            )?,
            is_empty()
        )
    }

    #[gtest]
    fn repeated_scalars() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!("../../testdata/valid/repeated_scalars.defcl"),
                valid_schemas()?,
                "defcl.testdata.valid.schemas.RepeatedScalarsFile",
            )?,
            is_empty()
        )
    }
}

mod non_repeated_fields_with_brackets {
    use super::*;

    #[gtest]
    fn scalar_field() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/non_repeated_fields_with_brackets/scalar_field.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.NonRepeatedFieldsWithBracketsFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::NonRepeatedFieldWithBrackets,
                location: SourceLocation {
                    start: Position { line: 2, column: 9 },
                    end: Position { line: 4, column: 3 }
                },
                field_name: "name".to_owned(),
            }])
        )
    }

    #[gtest]
    fn message_field() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/non_repeated_fields_with_brackets/message_field.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.NonRepeatedFieldsWithBracketsFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::NonRepeatedFieldWithBrackets,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 13
                    },
                    end: Position { line: 6, column: 3 }
                },
                field_name: "database".to_owned(),
            }])
        )
    }
}

mod message_values_for_scalar_fields {
    use super::*;

    #[gtest]
    fn nested_field() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/message_values_for_scalar_fields/nested_field.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.MessageValuesForScalarFieldsFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::MessageValueForScalarField,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 10
                    },
                    end: Position { line: 4, column: 3 }
                },
                field_name: "basic".to_owned(),
            }])
        )
    }

    #[gtest]
    fn element_of_repeated_field() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/message_values_for_scalar_fields/repeated_field.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.MessageValuesForScalarFieldsFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::MessageValueForScalarField,
                location: SourceLocation {
                    start: Position { line: 4, column: 5 },
                    end: Position { line: 6, column: 5 }
                },
                field_name: "tags".to_owned(),
            }])
        )
    }
}

mod scalars_for_message_fields {
    use super::*;

    #[gtest]
    fn string() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/scalars_for_message_fields/string.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.ScalarsForMessageFieldsFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::ScalarForMessageField,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 13
                    },
                    end: Position {
                        line: 2,
                        column: 23
                    }
                },
                field_name: "database".to_owned(),
            }])
        )
    }

    #[gtest]
    fn integer() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/scalars_for_message_fields/integer.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.ScalarsForMessageFieldsFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::ScalarForMessageField,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 13
                    },
                    end: Position {
                        line: 2,
                        column: 16
                    }
                },
                field_name: "database".to_owned(),
            }])
        )
    }

    #[gtest]
    fn float() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/scalars_for_message_fields/float.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.ScalarsForMessageFieldsFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::ScalarForMessageField,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 13
                    },
                    end: Position {
                        line: 2,
                        column: 15
                    }
                },
                field_name: "database".to_owned(),
            }])
        )
    }

    #[gtest]
    fn enum_value() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/scalars_for_message_fields/enum_value.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.ScalarsForMessageFieldsFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::ScalarForMessageField,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 13
                    },
                    end: Position {
                        line: 2,
                        column: 19
                    }
                },
                field_name: "database".to_owned(),
            }])
        )
    }

    #[gtest]
    fn element_of_repeated_field() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/scalars_for_message_fields/repeated_field.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.ScalarsForMessageFieldsFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::ScalarForMessageField,
                location: SourceLocation {
                    start: Position { line: 6, column: 5 },
                    end: Position {
                        line: 6,
                        column: 15
                    }
                },
                field_name: "replicas".to_owned(),
            }])
        )
    }
}

mod integer_enums {
    use super::*;

    #[gtest]
    fn integer_enum_in_second_top_level_message() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!("../../testdata/invalid/semantics/enums/second_top_level.defcl"),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.IntegerEnumFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::IntegerEnum,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 11
                    },
                    end: Position {
                        line: 2,
                        column: 11
                    }
                },
                field_name: "status".to_owned(),
            }])
        )
    }

    #[gtest]
    fn integer_enum_value() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!("../../testdata/invalid/semantics/enums/integer_enum.defcl"),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.IntegerEnumFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::IntegerEnum,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 11
                    },
                    end: Position {
                        line: 2,
                        column: 11
                    }
                },
                field_name: "status".to_owned(),
            }])
        )
    }

    #[gtest]
    fn integer_enum_in_repeated_message() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!("../../testdata/invalid/semantics/enums/repeated_integer_enum.defcl"),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.RepeatedIntegerEnumFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::IntegerEnum,
                location: SourceLocation {
                    start: Position {
                        line: 7,
                        column: 15
                    },
                    end: Position {
                        line: 7,
                        column: 15
                    }
                },
                field_name: "status".to_owned(),
            }])
        )
    }

    #[gtest]
    fn nested_integer_enum_value() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!("../../testdata/invalid/semantics/enums/nested_integer_enum.defcl"),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.NestedIntegerEnumFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::IntegerEnum,
                location: SourceLocation {
                    start: Position {
                        line: 3,
                        column: 13
                    },
                    end: Position {
                        line: 3,
                        column: 13
                    }
                },
                field_name: "status".to_owned(),
            }])
        )
    }
}

mod wrong_value_kinds {
    use super::*;

    #[gtest]
    fn non_string_for_string_field() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/wrong_value_kinds/string_field.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.WrongValueKindsFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::NonStringForStringField,
                location: SourceLocation {
                    start: Position { line: 2, column: 9 },
                    end: Position { line: 2, column: 9 }
                },
                field_name: "name".to_owned(),
            }])
        )
    }

    #[gtest]
    fn non_integer_for_integer_field() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/wrong_value_kinds/integer_field.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.WrongValueKindsFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::NonIntegerForIntegerField,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 10
                    },
                    end: Position {
                        line: 2,
                        column: 12
                    }
                },
                field_name: "count".to_owned(),
            }])
        )
    }

    #[gtest]
    fn integer_for_float_field() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/wrong_value_kinds/float_field.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.WrongValueKindsFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::NonFloatForFloatField,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 10
                    },
                    end: Position {
                        line: 2,
                        column: 10
                    }
                },
                field_name: "ratio".to_owned(),
            }])
        )
    }

    #[gtest]
    fn string_for_enum_field() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!("../../testdata/invalid/semantics/wrong_value_kinds/enum_field.defcl"),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.WrongValueKindsFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::NonEnumValueForEnumField,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 11
                    },
                    end: Position {
                        line: 2,
                        column: 25
                    }
                },
                field_name: "status".to_owned(),
            }])
        )
    }

    #[gtest]
    fn unknown_enum_value() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/wrong_value_kinds/unknown_enum_value.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.WrongValueKindsFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::UnknownEnumValue {
                    enum_type:
                        "defcl.testdata.invalid.semantics.schemas.WrongValueKindsFile.Status"
                            .to_owned()
                },
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 11
                    },
                    end: Position {
                        line: 2,
                        column: 16
                    }
                },
                field_name: "status".to_owned(),
            }])
        )
    }

    #[gtest]
    fn element_of_repeated_field() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/wrong_value_kinds/repeated_field.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.WrongValueKindsFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::NonStringForStringField,
                location: SourceLocation {
                    start: Position { line: 4, column: 5 },
                    end: Position {
                        line: 4,
                        column: 17
                    }
                },
                field_name: "tags".to_owned(),
            }])
        )
    }
}

mod values_out_of_range {
    use super::*;
    use crate::{FloatFieldType, IntegerFieldType};

    #[gtest]
    fn int32_above_maximum() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/out_of_range/int32_above_maximum.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.OutOfRangeFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::IntegerOutOfRange {
                    field_type: IntegerFieldType::Int32
                },
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 16
                    },
                    end: Position {
                        line: 2,
                        column: 25
                    }
                },
                field_name: "int32_value".to_owned(),
            }])
        )
    }

    #[gtest]
    fn int64_below_minimum() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/out_of_range/int64_below_minimum.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.OutOfRangeFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::IntegerOutOfRange {
                    field_type: IntegerFieldType::Int64
                },
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 16
                    },
                    end: Position {
                        line: 2,
                        column: 35
                    }
                },
                field_name: "int64_value".to_owned(),
            }])
        )
    }

    #[gtest]
    fn negative_in_unsigned_field() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/out_of_range/negative_in_unsigned_field.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.OutOfRangeFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::IntegerOutOfRange {
                    field_type: IntegerFieldType::Uint32
                },
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 17
                    },
                    end: Position {
                        line: 2,
                        column: 18
                    }
                },
                field_name: "uint32_value".to_owned(),
            }])
        )
    }

    #[gtest]
    fn uint64_above_maximum() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/out_of_range/uint64_above_maximum.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.OutOfRangeFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::IntegerOutOfRange {
                    field_type: IntegerFieldType::Uint64
                },
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 17
                    },
                    end: Position {
                        line: 2,
                        column: 36
                    }
                },
                field_name: "uint64_value".to_owned(),
            }])
        )
    }

    #[gtest]
    fn beyond_every_integer_type() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/out_of_range/beyond_every_integer_type.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.OutOfRangeFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::IntegerOutOfRange {
                    field_type: IntegerFieldType::Int64
                },
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 16
                    },
                    end: Position {
                        line: 2,
                        column: 55
                    }
                },
                field_name: "int64_value".to_owned(),
            }])
        )
    }

    #[gtest]
    fn float_rounding_to_infinity() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/out_of_range/float_rounding_to_infinity.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.OutOfRangeFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::FloatOutOfRange {
                    field_type: FloatFieldType::Float
                },
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 16
                    },
                    end: Position {
                        line: 2,
                        column: 56
                    }
                },
                field_name: "float_value".to_owned(),
            }])
        )
    }

    #[gtest]
    fn negative_double_rounding_to_infinity() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/out_of_range/negative_double_rounding_to_infinity.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.OutOfRangeFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::FloatOutOfRange {
                    field_type: FloatFieldType::Double
                },
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 17
                    },
                    end: Position {
                        line: 2,
                        column: 329
                    }
                },
                field_name: "double_value".to_owned(),
            }])
        )
    }

    #[gtest]
    fn element_of_repeated_field() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/out_of_range/element_of_repeated_field.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.OutOfRangeFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::IntegerOutOfRange {
                    field_type: IntegerFieldType::Int32
                },
                location: SourceLocation {
                    start: Position { line: 4, column: 5 },
                    end: Position {
                        line: 4,
                        column: 15
                    }
                },
                field_name: "int32_values".to_owned(),
            }])
        )
    }
}

mod oneofs {
    use super::*;

    #[gtest]
    fn second_field() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!("../../testdata/invalid/semantics/oneofs/second_field.defcl"),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.OneofsFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::SecondFieldOfOneof {
                    oneof: "defcl.testdata.invalid.semantics.schemas.OneofsFile.Config.source"
                        .to_owned()
                },
                location: SourceLocation {
                    start: Position { line: 3, column: 3 },
                    end: Position { line: 3, column: 5 }
                },
                field_name: "url".to_owned(),
            }])
        )
    }

    #[gtest]
    fn second_top_level_message() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/oneofs/second_top_level_message.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.OneofsFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::SecondFieldOfOneof {
                    oneof: "defcl.testdata.invalid.semantics.schemas.OneofsFile.target".to_owned()
                },
                location: SourceLocation {
                    start: Position { line: 4, column: 1 },
                    end: Position { line: 4, column: 8 }
                },
                field_name: "fallback".to_owned(),
            }])
        )
    }

    #[gtest]
    fn same_field_written_twice() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/oneofs/same_field_written_twice.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.OneofsFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::FieldWrittenTwice,
                location: SourceLocation {
                    start: Position { line: 3, column: 3 },
                    end: Position { line: 3, column: 6 }
                },
                field_name: "path".to_owned(),
            }])
        )
    }

    #[gtest]
    fn value_of_second_field() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!("../../testdata/invalid/semantics/oneofs/value_of_second_field.defcl"),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.OneofsFile",
            )?,
            eq(&vec![
                SemanticError {
                    kind: SemanticErrorKind::SecondFieldOfOneof {
                        oneof: "defcl.testdata.invalid.semantics.schemas.OneofsFile.Config.source"
                            .to_owned()
                    },
                    location: SourceLocation {
                        start: Position { line: 3, column: 3 },
                        end: Position { line: 3, column: 5 }
                    },
                    field_name: "url".to_owned(),
                },
                SemanticError {
                    kind: SemanticErrorKind::NonStringForStringField,
                    location: SourceLocation {
                        start: Position { line: 3, column: 8 },
                        end: Position { line: 3, column: 8 }
                    },
                    field_name: "url".to_owned(),
                }
            ])
        )
    }
}

mod repeated_fields_without_brackets {
    use super::*;

    #[gtest]
    fn repeated_scalar_without_brackets() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!("../../testdata/invalid/semantics/repeated/no_brackets_scalar.defcl"),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.NoBracketsScalarFile",
            )?,
            eq(&vec![
                SemanticError {
                    kind: SemanticErrorKind::RepeatedFieldWithoutBrackets,
                    location: SourceLocation {
                        start: Position { line: 2, column: 9 },
                        end: Position {
                            line: 2,
                            column: 14
                        }
                    },
                    field_name: "tags".to_owned(),
                },
                SemanticError {
                    kind: SemanticErrorKind::FieldWrittenTwice,
                    location: SourceLocation {
                        start: Position { line: 3, column: 3 },
                        end: Position { line: 3, column: 6 }
                    },
                    field_name: "tags".to_owned(),
                },
                SemanticError {
                    kind: SemanticErrorKind::RepeatedFieldWithoutBrackets,
                    location: SourceLocation {
                        start: Position { line: 3, column: 9 },
                        end: Position {
                            line: 3,
                            column: 14
                        }
                    },
                    field_name: "tags".to_owned(),
                },
            ])
        )
    }

    #[gtest]
    fn nested_repeated_message_without_brackets() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/repeated/nested_no_brackets_message.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.NestedNoBracketsMessageFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::RepeatedFieldWithoutBrackets,
                location: SourceLocation {
                    start: Position {
                        line: 3,
                        column: 19
                    },
                    end: Position { line: 5, column: 5 }
                },
                field_name: "dependencies".to_owned(),
            }])
        )
    }

    #[gtest]
    fn nested_repeated_scalar_without_brackets() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/repeated/nested_no_brackets_scalar.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.NestedNoBracketsScalarFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::RepeatedFieldWithoutBrackets,
                location: SourceLocation {
                    start: Position {
                        line: 3,
                        column: 11
                    },
                    end: Position {
                        line: 3,
                        column: 16
                    }
                },
                field_name: "tags".to_owned(),
            }])
        )
    }

    #[gtest]
    fn repeated_message_without_brackets() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!("../../testdata/invalid/semantics/repeated/no_brackets_message.defcl"),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.NoBracketsMessageFile",
            )?,
            eq(&vec![
                SemanticError {
                    kind: SemanticErrorKind::RepeatedFieldWithoutBrackets,
                    location: SourceLocation {
                        start: Position {
                            line: 2,
                            column: 17
                        },
                        end: Position { line: 4, column: 3 }
                    },
                    field_name: "dependencies".to_owned(),
                },
                SemanticError {
                    kind: SemanticErrorKind::FieldWrittenTwice,
                    location: SourceLocation {
                        start: Position { line: 5, column: 3 },
                        end: Position {
                            line: 5,
                            column: 14
                        }
                    },
                    field_name: "dependencies".to_owned(),
                },
                SemanticError {
                    kind: SemanticErrorKind::RepeatedFieldWithoutBrackets,
                    location: SourceLocation {
                        start: Position {
                            line: 5,
                            column: 17
                        },
                        end: Position { line: 7, column: 3 }
                    },
                    field_name: "dependencies".to_owned(),
                },
            ])
        )
    }
}

mod field_order {
    use super::*;

    #[gtest]
    fn field_after_higher_number() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/field_order/field_after_higher_number.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.WrongValueKindsFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::FieldOutOfOrder {
                    later_field: "count".to_owned(),
                },
                location: SourceLocation {
                    start: Position { line: 3, column: 3 },
                    end: Position { line: 3, column: 6 }
                },
                field_name: "name".to_owned(),
            },])
        )
    }

    #[gtest]
    fn two_fields_after_higher_number() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/field_order/two_fields_after_higher_number.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.WrongValueKindsFile",
            )?,
            eq(&vec![
                SemanticError {
                    kind: SemanticErrorKind::FieldOutOfOrder {
                        later_field: "ratio".to_owned(),
                    },
                    location: SourceLocation {
                        start: Position { line: 3, column: 3 },
                        end: Position { line: 3, column: 6 }
                    },
                    field_name: "name".to_owned(),
                },
                SemanticError {
                    kind: SemanticErrorKind::FieldOutOfOrder {
                        later_field: "ratio".to_owned(),
                    },
                    location: SourceLocation {
                        start: Position { line: 4, column: 3 },
                        end: Position { line: 4, column: 7 }
                    },
                    field_name: "count".to_owned(),
                },
            ])
        )
    }

    #[gtest]
    fn top_level_messages() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/field_order/top_level_messages.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.IntegerEnumFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::FieldOutOfOrder {
                    later_field: "metadata".to_owned(),
                },
                location: SourceLocation {
                    start: Position { line: 4, column: 1 },
                    end: Position { line: 4, column: 6 }
                },
                field_name: "config".to_owned(),
            },])
        )
    }
}

mod fields_written_twice {
    use super::*;

    #[gtest]
    fn repeated_field_written_twice() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/field_written_twice/repeated_field.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.FieldWrittenTwiceFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::FieldWrittenTwice,
                location: SourceLocation {
                    start: Position { line: 7, column: 3 },
                    end: Position {
                        line: 7,
                        column: 14
                    }
                },
                field_name: "dependencies".to_owned(),
            }])
        )
    }

    #[gtest]
    fn scalar_field_written_twice() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/field_written_twice/scalar_field.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.FieldWrittenTwiceFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::FieldWrittenTwice,
                location: SourceLocation {
                    start: Position { line: 3, column: 3 },
                    end: Position {
                        line: 3,
                        column: 15
                    }
                },
                field_name: "universe_name".to_owned(),
            }])
        )
    }

    #[gtest]
    fn top_level_message_written_twice() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/field_written_twice/top_level_message.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.FieldWrittenTwiceFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::FieldWrittenTwice,
                location: SourceLocation {
                    start: Position { line: 4, column: 1 },
                    end: Position { line: 4, column: 7 }
                },
                field_name: "project".to_owned(),
            }])
        )
    }

    #[gtest]
    fn field_written_twice_in_repeated_message() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/field_written_twice/nested_field.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.FieldWrittenTwiceFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::FieldWrittenTwice,
                location: SourceLocation {
                    start: Position { line: 8, column: 7 },
                    end: Position {
                        line: 8,
                        column: 14
                    }
                },
                field_name: "universe".to_owned(),
            }])
        )
    }
}

mod unknown_field_names {
    use super::*;

    #[gtest]
    fn unknown_top_level_message() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/unknown_field_names/top_level_message.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.FieldWrittenTwiceFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::UnknownFieldName {
                    message_type: "defcl.testdata.invalid.semantics.schemas.FieldWrittenTwiceFile"
                        .to_owned()
                },
                location: SourceLocation {
                    start: Position { line: 4, column: 1 },
                    end: Position { line: 4, column: 8 }
                },
                field_name: "settings".to_owned(),
            }])
        )
    }

    #[gtest]
    fn unknown_field_in_repeated_message() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/unknown_field_names/nested_field.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.FieldWrittenTwiceFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::UnknownFieldName {
                    message_type:
                        "defcl.testdata.invalid.semantics.schemas.FieldWrittenTwiceFile.Dependency"
                            .to_owned()
                },
                location: SourceLocation {
                    start: Position { line: 5, column: 7 },
                    end: Position {
                        line: 5,
                        column: 13
                    }
                },
                field_name: "version".to_owned(),
            }])
        )
    }

    #[gtest]
    fn unknown_field_in_message_type_without_package() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/unknown_field_names/message_type_without_package.defcl"
                ),
                invalid_semantics_schemas()?,
                "NoPackageFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::UnknownFieldName {
                    message_type: "NoPackageFile.Config".to_owned()
                },
                location: SourceLocation {
                    start: Position { line: 2, column: 3 },
                    end: Position { line: 2, column: 6 }
                },
                field_name: "size".to_owned(),
            }])
        )
    }
}

mod multiple_errors {
    use super::*;

    #[gtest]
    fn errors_in_several_fields() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/multiple_errors/errors_in_several_fields.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.MultipleErrorsFile",
            )?,
            eq(&vec![
                SemanticError {
                    kind: SemanticErrorKind::IntegerEnum,
                    location: SourceLocation {
                        start: Position {
                            line: 2,
                            column: 11
                        },
                        end: Position {
                            line: 2,
                            column: 11
                        }
                    },
                    field_name: "status".to_owned(),
                },
                SemanticError {
                    kind: SemanticErrorKind::ScalarForMessageField,
                    location: SourceLocation {
                        start: Position {
                            line: 3,
                            column: 13
                        },
                        end: Position {
                            line: 3,
                            column: 23
                        }
                    },
                    field_name: "database".to_owned(),
                },
                SemanticError {
                    kind: SemanticErrorKind::MessageValueForScalarField,
                    location: SourceLocation {
                        start: Position {
                            line: 4,
                            column: 10
                        },
                        end: Position { line: 6, column: 3 }
                    },
                    field_name: "count".to_owned(),
                },
            ])
        )
    }

    #[gtest]
    fn errors_in_several_elements() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/multiple_errors/errors_in_several_elements.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.MultipleErrorsFile",
            )?,
            eq(&vec![
                SemanticError {
                    kind: SemanticErrorKind::MessageValueForScalarField,
                    location: SourceLocation {
                        start: Position { line: 3, column: 5 },
                        end: Position { line: 5, column: 5 }
                    },
                    field_name: "tags".to_owned(),
                },
                SemanticError {
                    kind: SemanticErrorKind::MessageValueForScalarField,
                    location: SourceLocation {
                        start: Position { line: 7, column: 5 },
                        end: Position { line: 9, column: 5 }
                    },
                    field_name: "tags".to_owned(),
                },
            ])
        )
    }

    #[gtest]
    fn value_of_unknown_field_is_not_checked() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/multiple_errors/value_of_unknown_field.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.MultipleErrorsFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::UnknownFieldName {
                    message_type:
                        "defcl.testdata.invalid.semantics.schemas.MultipleErrorsFile.Config"
                            .to_owned()
                },
                location: SourceLocation {
                    start: Position { line: 2, column: 3 },
                    end: Position { line: 2, column: 6 }
                },
                field_name: "size".to_owned(),
            },])
        )
    }

    #[gtest]
    fn value_of_field_written_twice_is_checked() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/multiple_errors/value_of_field_written_twice.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.MultipleErrorsFile",
            )?,
            eq(&vec![
                SemanticError {
                    kind: SemanticErrorKind::FieldWrittenTwice,
                    location: SourceLocation {
                        start: Position { line: 3, column: 3 },
                        end: Position { line: 3, column: 8 }
                    },
                    field_name: "status".to_owned(),
                },
                SemanticError {
                    kind: SemanticErrorKind::IntegerEnum,
                    location: SourceLocation {
                        start: Position {
                            line: 3,
                            column: 11
                        },
                        end: Position {
                            line: 3,
                            column: 11
                        }
                    },
                    field_name: "status".to_owned(),
                },
            ])
        )
    }

    #[gtest]
    fn unknown_field_written_twice_is_unknown_each_time() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/multiple_errors/unknown_field_written_twice.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.MultipleErrorsFile",
            )?,
            eq(&vec![
                SemanticError {
                    kind: SemanticErrorKind::UnknownFieldName {
                        message_type:
                            "defcl.testdata.invalid.semantics.schemas.MultipleErrorsFile.Config"
                                .to_owned()
                    },
                    location: SourceLocation {
                        start: Position { line: 2, column: 3 },
                        end: Position { line: 2, column: 6 }
                    },
                    field_name: "size".to_owned(),
                },
                SemanticError {
                    kind: SemanticErrorKind::UnknownFieldName {
                        message_type:
                            "defcl.testdata.invalid.semantics.schemas.MultipleErrorsFile.Config"
                                .to_owned()
                    },
                    location: SourceLocation {
                        start: Position { line: 3, column: 3 },
                        end: Position { line: 3, column: 6 }
                    },
                    field_name: "size".to_owned(),
                },
            ])
        )
    }

    #[gtest]
    fn message_value_for_scalar_field_is_not_checked() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/multiple_errors/message_value_for_scalar_field.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.MultipleErrorsFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::MessageValueForScalarField,
                location: SourceLocation {
                    start: Position { line: 2, column: 9 },
                    end: Position { line: 4, column: 3 }
                },
                field_name: "name".to_owned(),
            },])
        )
    }

    #[gtest]
    fn brackets_on_non_repeated_field_are_not_checked() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/multiple_errors/non_repeated_field_with_brackets.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.MultipleErrorsFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::NonRepeatedFieldWithBrackets,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 13
                    },
                    end: Position { line: 6, column: 3 }
                },
                field_name: "database".to_owned(),
            },])
        )
    }

    #[gtest]
    fn repeated_field_without_brackets_is_not_checked() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/multiple_errors/repeated_field_without_brackets.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.MultipleErrorsFile",
            )?,
            eq(&vec![SemanticError {
                kind: SemanticErrorKind::RepeatedFieldWithoutBrackets,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 13
                    },
                    end: Position { line: 4, column: 3 }
                },
                field_name: "replicas".to_owned(),
            },])
        )
    }
}
