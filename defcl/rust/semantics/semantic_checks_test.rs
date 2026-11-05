use crate::test_support::{invalid_semantics_schemas, valid_schemas};
use crate::{FileDescriptorSet, Schema, SemanticError, check_semantics};
use defcl_parser::{SourceLocation, parse};
use googletest::prelude::*;

/// Parses `source` and checks it against the schema in `descriptor_set` whose
/// top-level message type is `top_level_message_type`.
fn check_semantics_of_source(
    source: &str,
    descriptor_set: FileDescriptorSet,
    top_level_message_type: &str,
) -> Result<std::result::Result<(), Vec<SemanticError>>> {
    let schema = Schema::from_descriptor_set(descriptor_set, top_level_message_type).or_fail()?;
    let file = parse(source).or_fail()?;
    Ok(check_semantics(&file, &schema))
}

mod valid_files {
    use super::*;

    #[gtest]
    fn single_toplevel() -> Result<()> {
        verify_ok!(check_semantics_of_source(
            include_str!("../../testdata/valid/single_toplevel.defcl"),
            valid_schemas()?,
            "defcl.testdata.valid.schemas.SingleToplevelFile",
        )?)
    }

    #[gtest]
    fn integers() -> Result<()> {
        verify_ok!(check_semantics_of_source(
            include_str!("../../testdata/valid/integers.defcl"),
            valid_schemas()?,
            "defcl.testdata.valid.schemas.IntegersFile",
        )?)
    }

    #[gtest]
    fn nested_messages() -> Result<()> {
        verify_ok!(check_semantics_of_source(
            include_str!("../../testdata/valid/nested_messages.defcl"),
            valid_schemas()?,
            "defcl.testdata.valid.schemas.NestedMessagesFile",
        )?)
    }

    #[gtest]
    fn repeated_messages() -> Result<()> {
        verify_ok!(check_semantics_of_source(
            include_str!("../../testdata/valid/repeated_messages.defcl"),
            valid_schemas()?,
            "defcl.testdata.valid.schemas.RepeatedMessagesFile",
        )?)
    }

    #[gtest]
    fn strings() -> Result<()> {
        verify_ok!(check_semantics_of_source(
            include_str!("../../testdata/valid/strings.defcl"),
            valid_schemas()?,
            "defcl.testdata.valid.schemas.StringsFile",
        )?)
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
            err(eq(&vec![SemanticError::NonRepeatedFieldWithBrackets {
                location: SourceLocation {
                    line: 2,
                    column: 11,
                    end_line: 2,
                    end_column: 15
                },
                field_name: "name".to_owned(),
            }]))
        )
    }

    #[gtest]
    fn empty_brackets() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/non_repeated_fields_with_brackets/empty_brackets.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.NonRepeatedFieldsWithBracketsFile",
            )?,
            err(eq(&vec![SemanticError::NonRepeatedFieldWithBrackets {
                location: SourceLocation {
                    line: 2,
                    column: 11,
                    end_line: 2,
                    end_column: 12
                },
                field_name: "name".to_owned(),
            }]))
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
            err(eq(&vec![SemanticError::NonRepeatedFieldWithBrackets {
                location: SourceLocation {
                    line: 2,
                    column: 15,
                    end_line: 2,
                    end_column: 18
                },
                field_name: "database".to_owned(),
            }]))
        )
    }
}

mod message_values_for_scalar_fields {
    use super::*;

    #[gtest]
    fn top_level_field() -> Result<()> {
        verify_that!(
            check_semantics_of_source(
                include_str!(
                    "../../testdata/invalid/semantics/message_values_for_scalar_fields/top_level_field.defcl"
                ),
                invalid_semantics_schemas()?,
                "defcl.testdata.invalid.semantics.schemas.MessageValuesForScalarFieldsFile",
            )?,
            err(eq(&vec![SemanticError::MessageValueForScalarField {
                location: SourceLocation {
                    line: 1,
                    column: 8,
                    end_line: 1,
                    end_column: 9
                },
                field_name: "count".to_owned(),
            }]))
        )
    }

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
            err(eq(&vec![SemanticError::MessageValueForScalarField {
                location: SourceLocation {
                    line: 2,
                    column: 12,
                    end_line: 2,
                    end_column: 13
                },
                field_name: "basic".to_owned(),
            }]))
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
            err(eq(&vec![SemanticError::MessageValueForScalarField {
                location: SourceLocation {
                    line: 2,
                    column: 17,
                    end_line: 2,
                    end_column: 18
                },
                field_name: "tags".to_owned(),
            }]))
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
            err(eq(&vec![SemanticError::ScalarForMessageField {
                location: SourceLocation {
                    line: 2,
                    column: 15,
                    end_line: 2,
                    end_column: 25
                },
                field_name: "database".to_owned(),
            }]))
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
            err(eq(&vec![SemanticError::ScalarForMessageField {
                location: SourceLocation {
                    line: 2,
                    column: 15,
                    end_line: 2,
                    end_column: 18
                },
                field_name: "database".to_owned(),
            }]))
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
            err(eq(&vec![SemanticError::ScalarForMessageField {
                location: SourceLocation {
                    line: 2,
                    column: 15,
                    end_line: 2,
                    end_column: 17
                },
                field_name: "database".to_owned(),
            }]))
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
            err(eq(&vec![SemanticError::ScalarForMessageField {
                location: SourceLocation {
                    line: 2,
                    column: 15,
                    end_line: 2,
                    end_column: 21
                },
                field_name: "database".to_owned(),
            }]))
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
            err(eq(&vec![SemanticError::ScalarForMessageField {
                location: SourceLocation {
                    line: 2,
                    column: 20,
                    end_line: 2,
                    end_column: 30
                },
                field_name: "replicas".to_owned(),
            }]))
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
            err(eq(&vec![SemanticError::IntegerEnum {
                location: SourceLocation {
                    line: 5,
                    column: 13,
                    end_line: 5,
                    end_column: 13
                },
                field_name: "status".to_owned(),
            }]))
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
            err(eq(&vec![SemanticError::IntegerEnum {
                location: SourceLocation {
                    line: 2,
                    column: 13,
                    end_line: 2,
                    end_column: 13
                },
                field_name: "status".to_owned(),
            }]))
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
            err(eq(&vec![SemanticError::IntegerEnum {
                location: SourceLocation {
                    line: 4,
                    column: 19,
                    end_line: 4,
                    end_column: 19
                },
                field_name: "status".to_owned(),
            }]))
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
            err(eq(&vec![SemanticError::IntegerEnum {
                location: SourceLocation {
                    line: 3,
                    column: 17,
                    end_line: 3,
                    end_column: 17
                },
                field_name: "status".to_owned(),
            }]))
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
            err(eq(&vec![
                SemanticError::RepeatedFieldWithoutBrackets {
                    location: SourceLocation {
                        line: 2,
                        column: 11,
                        end_line: 2,
                        end_column: 16
                    },
                    field_name: "tags".to_owned(),
                },
                SemanticError::FieldWrittenTwice {
                    location: SourceLocation {
                        line: 3,
                        column: 5,
                        end_line: 3,
                        end_column: 8
                    },
                    field_name: "tags".to_owned(),
                },
                SemanticError::RepeatedFieldWithoutBrackets {
                    location: SourceLocation {
                        line: 3,
                        column: 11,
                        end_line: 3,
                        end_column: 16
                    },
                    field_name: "tags".to_owned(),
                },
            ]))
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
            err(eq(&vec![SemanticError::RepeatedFieldWithoutBrackets {
                location: SourceLocation {
                    line: 3,
                    column: 23,
                    end_line: 3,
                    end_column: 42
                },
                field_name: "dependencies".to_owned(),
            }]))
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
            err(eq(&vec![SemanticError::RepeatedFieldWithoutBrackets {
                location: SourceLocation {
                    line: 3,
                    column: 15,
                    end_line: 3,
                    end_column: 20
                },
                field_name: "tags".to_owned(),
            }]))
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
            err(eq(&vec![
                SemanticError::RepeatedFieldWithoutBrackets {
                    location: SourceLocation {
                        line: 2,
                        column: 19,
                        end_line: 2,
                        end_column: 38
                    },
                    field_name: "dependencies".to_owned(),
                },
                SemanticError::FieldWrittenTwice {
                    location: SourceLocation {
                        line: 3,
                        column: 5,
                        end_line: 3,
                        end_column: 16
                    },
                    field_name: "dependencies".to_owned(),
                },
                SemanticError::RepeatedFieldWithoutBrackets {
                    location: SourceLocation {
                        line: 3,
                        column: 19,
                        end_line: 3,
                        end_column: 38
                    },
                    field_name: "dependencies".to_owned(),
                },
            ]))
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
            err(eq(&vec![SemanticError::FieldWrittenTwice {
                location: SourceLocation {
                    line: 3,
                    column: 5,
                    end_line: 3,
                    end_column: 16
                },
                field_name: "dependencies".to_owned(),
            }]))
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
            err(eq(&vec![SemanticError::FieldWrittenTwice {
                location: SourceLocation {
                    line: 3,
                    column: 5,
                    end_line: 3,
                    end_column: 17
                },
                field_name: "universe_name".to_owned(),
            }]))
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
            err(eq(&vec![SemanticError::FieldWrittenTwice {
                location: SourceLocation {
                    line: 4,
                    column: 1,
                    end_line: 4,
                    end_column: 7
                },
                field_name: "project".to_owned(),
            }]))
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
            err(eq(&vec![SemanticError::FieldWrittenTwice {
                location: SourceLocation {
                    line: 6,
                    column: 13,
                    end_line: 6,
                    end_column: 20
                },
                field_name: "universe".to_owned(),
            }]))
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
            err(eq(&vec![SemanticError::UnknownFieldName {
                location: SourceLocation {
                    line: 4,
                    column: 1,
                    end_line: 4,
                    end_column: 8
                },
                field_name: "settings".to_owned(),
                message_type: "defcl.testdata.invalid.semantics.schemas.FieldWrittenTwiceFile"
                    .to_owned(),
            }]))
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
            err(eq(&vec![SemanticError::UnknownFieldName {
                location: SourceLocation {
                    line: 5,
                    column: 13,
                    end_line: 5,
                    end_column: 19
                },
                field_name: "version".to_owned(),
                message_type:
                    "defcl.testdata.invalid.semantics.schemas.FieldWrittenTwiceFile.Dependency"
                        .to_owned(),
            }]))
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
            err(eq(&vec![SemanticError::UnknownFieldName {
                location: SourceLocation {
                    line: 2,
                    column: 5,
                    end_line: 2,
                    end_column: 8
                },
                field_name: "size".to_owned(),
                message_type: "NoPackageFile.Config".to_owned(),
            }]))
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
            err(eq(&vec![
                SemanticError::IntegerEnum {
                    location: SourceLocation {
                        line: 2,
                        column: 13,
                        end_line: 2,
                        end_column: 13
                    },
                    field_name: "status".to_owned(),
                },
                SemanticError::ScalarForMessageField {
                    location: SourceLocation {
                        line: 3,
                        column: 15,
                        end_line: 3,
                        end_column: 25
                    },
                    field_name: "database".to_owned(),
                },
                SemanticError::MessageValueForScalarField {
                    location: SourceLocation {
                        line: 5,
                        column: 8,
                        end_line: 5,
                        end_column: 9
                    },
                    field_name: "count".to_owned(),
                },
            ]))
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
            err(eq(&vec![
                SemanticError::MessageValueForScalarField {
                    location: SourceLocation {
                        line: 2,
                        column: 12,
                        end_line: 2,
                        end_column: 13
                    },
                    field_name: "tags".to_owned(),
                },
                SemanticError::MessageValueForScalarField {
                    location: SourceLocation {
                        line: 2,
                        column: 21,
                        end_line: 2,
                        end_column: 22
                    },
                    field_name: "tags".to_owned(),
                },
            ]))
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
            err(eq(&vec![SemanticError::UnknownFieldName {
                location: SourceLocation {
                    line: 2,
                    column: 5,
                    end_line: 2,
                    end_column: 8
                },
                field_name: "size".to_owned(),
                message_type: "defcl.testdata.invalid.semantics.schemas.MultipleErrorsFile.Config"
                    .to_owned(),
            },]))
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
            err(eq(&vec![
                SemanticError::FieldWrittenTwice {
                    location: SourceLocation {
                        line: 3,
                        column: 5,
                        end_line: 3,
                        end_column: 10
                    },
                    field_name: "status".to_owned(),
                },
                SemanticError::IntegerEnum {
                    location: SourceLocation {
                        line: 3,
                        column: 13,
                        end_line: 3,
                        end_column: 13
                    },
                    field_name: "status".to_owned(),
                },
            ]))
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
            err(eq(&vec![
                SemanticError::UnknownFieldName {
                    location: SourceLocation {
                        line: 2,
                        column: 5,
                        end_line: 2,
                        end_column: 8
                    },
                    field_name: "size".to_owned(),
                    message_type:
                        "defcl.testdata.invalid.semantics.schemas.MultipleErrorsFile.Config"
                            .to_owned(),
                },
                SemanticError::UnknownFieldName {
                    location: SourceLocation {
                        line: 3,
                        column: 5,
                        end_line: 3,
                        end_column: 8
                    },
                    field_name: "size".to_owned(),
                    message_type:
                        "defcl.testdata.invalid.semantics.schemas.MultipleErrorsFile.Config"
                            .to_owned(),
                },
            ]))
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
            err(eq(&vec![SemanticError::MessageValueForScalarField {
                location: SourceLocation {
                    line: 2,
                    column: 11,
                    end_line: 4,
                    end_column: 5
                },
                field_name: "name".to_owned(),
            },]))
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
            err(eq(&vec![SemanticError::NonRepeatedFieldWithBrackets {
                location: SourceLocation {
                    line: 2,
                    column: 15,
                    end_line: 2,
                    end_column: 27
                },
                field_name: "database".to_owned(),
            },]))
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
            err(eq(&vec![SemanticError::RepeatedFieldWithoutBrackets {
                location: SourceLocation {
                    line: 2,
                    column: 15,
                    end_line: 2,
                    end_column: 25
                },
                field_name: "replicas".to_owned(),
            },]))
        )
    }
}
