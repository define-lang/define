use crate::{
    Field, FieldName, MessageValue, ParseResult, ParsedFile, RepeatedValue, Scalar, SyntaxError,
    SyntaxErrorKind, TopLevelMessage, Value, parse,
};
use googletest::prelude::*;
use source_rendering::{Position, SourceLocation};

/// A field name written in ASCII on one line.
const fn name(text: &str, line: u32, column: u32) -> FieldName<'_> {
    FieldName {
        text,
        location: SourceLocation {
            start: Position { line, column },
            end: Position { line, column }.columns_later(text.len() - 1),
        },
    }
}

/// A scalar written in ASCII on one line.
const fn scalar(text: &str, line: u32, column: u32) -> Scalar<'_> {
    Scalar {
        text,
        location: SourceLocation {
            start: Position { line, column },
            end: Position { line, column }.columns_later(text.len() - 1),
        },
    }
}

/// A field, which covers its name through its value.
fn field<'source>(name: FieldName<'source>, value: Value<'source>) -> Field<'source> {
    let location = SourceLocation {
        start: name.location.start,
        end: value.location().end,
    };
    Field {
        name,
        value,
        location,
    }
}

/// A top-level message, which covers its name through its message value.
const fn top_level_message<'source>(
    name: FieldName<'source>,
    value: MessageValue<'source>,
) -> TopLevelMessage<'source> {
    let location = SourceLocation {
        start: name.location.start,
        end: value.location.end,
    };
    TopLevelMessage {
        name,
        value,
        location,
    }
}

/// The result of parsing a file with no syntax errors into `file`.
const fn parsed(file: ParsedFile<'_>) -> ParseResult<'_> {
    ParseResult {
        file: Some(file),
        errors: Vec::new(),
    }
}

/// The result of a parse that `error` stopped, with no errors before it.
fn stopped_by(error: SyntaxError) -> ParseResult<'static> {
    ParseResult {
        file: None,
        errors: vec![error],
    }
}

/// The location from `line`, `column` through `end_line`, `end_column`.
const fn location(line: u32, column: u32, end_line: u32, end_column: u32) -> SourceLocation {
    SourceLocation {
        start: Position { line, column },
        end: Position {
            line: end_line,
            column: end_column,
        },
    }
}

/// The syntax errors of `source`, none of which stopped its parse.
fn layout_errors(source: &str) -> Result<Vec<SyntaxError>> {
    let parsed = parse(source);
    verify_that!(parsed.file, some(anything()))?;
    Ok(parsed.errors)
}

mod valid_files {
    use super::*;

    #[gtest]
    fn single_toplevel() -> Result<()> {
        verify_that!(
            parse(include_str!("../../testdata/valid/single_toplevel.defcl")),
            eq(&parsed(ParsedFile {
                top_level_messages: vec![top_level_message(
                    name("project", 1, 1),
                    MessageValue {
                        fields: vec![field(
                            name("universe_name", 2, 3),
                            Value::String(scalar("\"example\"", 2, 18)),
                        )],
                        location: SourceLocation {
                            start: Position {
                                line: 1,
                                column: 10
                            },
                            end: Position { line: 3, column: 1 }
                        },
                    },
                )],
            }))
        )
    }

    #[gtest]
    fn multiple_toplevel() -> Result<()> {
        verify_that!(
            parse(include_str!("../../testdata/valid/multiple_toplevel.defcl")),
            eq(&parsed(ParsedFile {
                top_level_messages: vec![
                    top_level_message(
                        name("project", 1, 1),
                        MessageValue {
                            fields: vec![field(
                                name("universe_name", 2, 3),
                                Value::String(scalar("\"example\"", 2, 18)),
                            )],
                            location: SourceLocation {
                                start: Position {
                                    line: 1,
                                    column: 10
                                },
                                end: Position { line: 3, column: 1 }
                            },
                        },
                    ),
                    top_level_message(
                        name("settings", 4, 1),
                        MessageValue {
                            fields: vec![field(
                                name("log_level", 5, 3),
                                Value::Integer(scalar("3", 5, 14)),
                            )],
                            location: SourceLocation {
                                start: Position {
                                    line: 4,
                                    column: 11
                                },
                                end: Position { line: 6, column: 1 }
                            },
                        },
                    ),
                ],
            }))
        )
    }

    #[gtest]
    fn comments() -> Result<()> {
        verify_that!(
            parse(include_str!("../../testdata/valid/comments.defcl")),
            eq(&parsed(ParsedFile {
                top_level_messages: vec![
                    top_level_message(
                        name("project", 2, 1),
                        MessageValue {
                            fields: vec![field(
                                name("universe_name", 4, 3),
                                Value::String(scalar("\"example\"", 4, 18)),
                            )],
                            location: SourceLocation {
                                start: Position {
                                    line: 2,
                                    column: 10
                                },
                                end: Position { line: 5, column: 1 }
                            },
                        },
                    ),
                    top_level_message(
                        name("settings", 7, 1),
                        MessageValue {
                            fields: vec![field(
                                name("log_level", 8, 3),
                                Value::Integer(scalar("3", 8, 14)),
                            )],
                            location: SourceLocation {
                                start: Position {
                                    line: 7,
                                    column: 11
                                },
                                end: Position { line: 9, column: 1 }
                            },
                        },
                    ),
                ],
            }))
        )
    }

    #[gtest]
    fn enums() -> Result<()> {
        verify_that!(
            parse(include_str!("../../testdata/valid/enums.defcl")),
            eq(&parsed(ParsedFile {
                top_level_messages: vec![top_level_message(
                    name("config", 1, 1),
                    MessageValue {
                        fields: vec![
                            field(name("status", 2, 3), Value::Enum(scalar("ACTIVE", 2, 11))),
                            field(
                                name("mode", 3, 3),
                                Value::Enum(scalar("STATUS_ACTIVE", 3, 9)),
                            ),
                            field(name("version", 4, 3), Value::Enum(scalar("V1", 4, 12))),
                            field(name("level", 5, 3), Value::Enum(scalar("LEVEL_2", 5, 10))),
                            field(
                                name("state", 6, 3),
                                Value::Enum(scalar("UNSPECIFIED", 6, 10)),
                            ),
                        ],
                        location: SourceLocation {
                            start: Position { line: 1, column: 9 },
                            end: Position { line: 7, column: 1 }
                        },
                    },
                )],
            }))
        )
    }

    #[gtest]
    fn field_names() -> Result<()> {
        verify_that!(
            parse(include_str!("../../testdata/valid/field_names.defcl")),
            eq(&parsed(ParsedFile {
                top_level_messages: vec![top_level_message(
                    name("config", 1, 1),
                    MessageValue {
                        fields: vec![
                            field(
                                name("universe_name", 2, 3),
                                Value::String(scalar("\"example\"", 2, 18)),
                            ),
                            field(
                                name("project_id", 3, 3),
                                Value::String(scalar("\"proj1\"", 3, 15)),
                            ),
                            field(
                                name("retry_count", 4, 3),
                                Value::Integer(scalar("3", 4, 16)),
                            ),
                            field(
                                name("field2name", 5, 3),
                                Value::String(scalar("\"value\"", 5, 15)),
                            ),
                            field(
                                name("max_retries", 6, 3),
                                Value::Integer(scalar("5", 6, 16)),
                            ),
                            field(
                                name("api_v2_endpoint", 7, 3),
                                Value::String(scalar("\"http://example.com\"", 7, 20)),
                            ),
                        ],
                        location: SourceLocation {
                            start: Position { line: 1, column: 9 },
                            end: Position { line: 8, column: 1 }
                        },
                    },
                )],
            }))
        )
    }

    #[gtest]
    fn floats() -> Result<()> {
        verify_that!(
            parse(include_str!("../../testdata/valid/floats.defcl")),
            eq(&parsed(ParsedFile {
                top_level_messages: vec![top_level_message(
                    name("config", 1, 1),
                    MessageValue {
                        fields: vec![
                            field(name("pi", 2, 3), Value::Float(scalar("3.14", 2, 7))),
                            field(
                                name("negative_float", 3, 3),
                                Value::Float(scalar("-2.0", 3, 19)),
                            ),
                            field(name("small", 4, 3), Value::Float(scalar("0.5", 4, 10))),
                            field(
                                name("precise", 5, 3),
                                Value::Float(scalar("123.456789", 5, 12)),
                            ),
                        ],
                        location: SourceLocation {
                            start: Position { line: 1, column: 9 },
                            end: Position { line: 6, column: 1 }
                        },
                    },
                )],
            }))
        )
    }

    #[gtest]
    fn integers() -> Result<()> {
        verify_that!(
            parse(include_str!("../../testdata/valid/integers.defcl")),
            eq(&parsed(ParsedFile {
                top_level_messages: vec![top_level_message(
                    name("config", 1, 1),
                    MessageValue {
                        fields: vec![
                            field(name("positive", 2, 3), Value::Integer(scalar("10", 2, 13))),
                            field(name("negative", 3, 3), Value::Integer(scalar("-5", 3, 13))),
                            field(name("zero", 4, 3), Value::Integer(scalar("0", 4, 9))),
                            field(name("large", 5, 3), Value::Integer(scalar("999999", 5, 10)),),
                        ],
                        location: SourceLocation {
                            start: Position { line: 1, column: 9 },
                            end: Position { line: 6, column: 1 }
                        },
                    },
                )],
            }))
        )
    }

    #[gtest]
    fn nested_messages() -> Result<()> {
        verify_that!(
            parse(include_str!("../../testdata/valid/nested_messages.defcl")),
            eq(&parsed(ParsedFile {
                top_level_messages: vec![top_level_message(
                    name("project", 1, 1),
                    MessageValue {
                        fields: vec![
                            field(
                                name("name", 2, 3),
                                Value::String(scalar("\"my_project\"", 2, 9)),
                            ),
                            field(
                                name("database", 3, 3),
                                Value::Message(MessageValue {
                                    fields: vec![
                                        field(
                                            name("host", 4, 5),
                                            Value::String(scalar("\"localhost\"", 4, 11)),
                                        ),
                                        field(
                                            name("port", 5, 5),
                                            Value::Integer(scalar("5432", 5, 11)),
                                        ),
                                        field(
                                            name("pool", 6, 5),
                                            Value::Message(MessageValue {
                                                fields: vec![field(
                                                    name("max_connections", 7, 7),
                                                    Value::Integer(scalar("10", 7, 24)),
                                                )],
                                                location: SourceLocation {
                                                    start: Position {
                                                        line: 6,
                                                        column: 11
                                                    },
                                                    end: Position { line: 8, column: 5 }
                                                },
                                            }),
                                        ),
                                    ],
                                    location: SourceLocation {
                                        start: Position {
                                            line: 3,
                                            column: 13
                                        },
                                        end: Position { line: 9, column: 3 }
                                    },
                                }),
                            ),
                        ],
                        location: SourceLocation {
                            start: Position {
                                line: 1,
                                column: 10
                            },
                            end: Position {
                                line: 10,
                                column: 1
                            }
                        },
                    },
                )],
            }))
        )
    }

    #[gtest]
    fn repeated_messages() -> Result<()> {
        verify_that!(
            parse(include_str!("../../testdata/valid/repeated_messages.defcl")),
            eq(&parsed(ParsedFile {
                top_level_messages: vec![top_level_message(
                    name("project", 1, 1),
                    MessageValue {
                        fields: vec![field(
                            name("dependencies", 2, 3),
                            Value::Repeated(RepeatedValue {
                                values: vec![
                                    Value::Message(MessageValue {
                                        fields: vec![field(
                                            name("universe", 4, 7),
                                            Value::String(scalar("\"mv:example.com:lib1\"", 4, 17)),
                                        )],
                                        location: SourceLocation {
                                            start: Position { line: 3, column: 5 },
                                            end: Position { line: 5, column: 5 }
                                        },
                                    }),
                                    Value::Message(MessageValue {
                                        fields: vec![field(
                                            name("universe", 7, 7),
                                            Value::String(scalar("\"mv:example.com:lib2\"", 7, 17)),
                                        )],
                                        location: SourceLocation {
                                            start: Position { line: 6, column: 5 },
                                            end: Position { line: 8, column: 5 }
                                        },
                                    }),
                                ],
                                location: SourceLocation {
                                    start: Position {
                                        line: 2,
                                        column: 17
                                    },
                                    end: Position { line: 9, column: 3 }
                                },
                            }),
                        )],
                        location: SourceLocation {
                            start: Position {
                                line: 1,
                                column: 10
                            },
                            end: Position {
                                line: 10,
                                column: 1
                            }
                        },
                    },
                )],
            }))
        )
    }

    #[gtest]
    fn repeated_scalars() -> Result<()> {
        verify_that!(
            parse(include_str!("../../testdata/valid/repeated_scalars.defcl")),
            eq(&parsed(ParsedFile {
                top_level_messages: vec![top_level_message(
                    name("config", 1, 1),
                    MessageValue {
                        fields: vec![
                            field(
                                name("tags", 2, 3),
                                Value::Repeated(RepeatedValue {
                                    values: vec![
                                        Value::String(scalar("\"tag1\"", 3, 5)),
                                        Value::String(scalar("\"tag2\"", 4, 5)),
                                        Value::String(scalar("\"tag3\"", 5, 5)),
                                    ],
                                    location: SourceLocation {
                                        start: Position { line: 2, column: 9 },
                                        end: Position { line: 6, column: 3 }
                                    },
                                }),
                            ),
                            field(
                                name("counts", 7, 3),
                                Value::Repeated(RepeatedValue {
                                    values: vec![
                                        Value::Integer(scalar("1", 8, 5)),
                                        Value::Integer(scalar("2", 9, 5)),
                                        Value::Integer(scalar("3", 10, 5)),
                                    ],
                                    location: SourceLocation {
                                        start: Position {
                                            line: 7,
                                            column: 11
                                        },
                                        end: Position {
                                            line: 11,
                                            column: 3
                                        }
                                    },
                                }),
                            ),
                            field(
                                name("values", 12, 3),
                                Value::Repeated(RepeatedValue {
                                    values: vec![
                                        Value::Float(scalar("1.5", 13, 5)),
                                        Value::Float(scalar("2.5", 14, 5)),
                                    ],
                                    location: SourceLocation {
                                        start: Position {
                                            line: 12,
                                            column: 11
                                        },
                                        end: Position {
                                            line: 15,
                                            column: 3
                                        }
                                    },
                                }),
                            ),
                            field(
                                name("modes", 16, 3),
                                Value::Repeated(RepeatedValue {
                                    values: vec![
                                        Value::Enum(scalar("ACTIVE", 17, 5)),
                                        Value::Enum(scalar("INACTIVE", 18, 5)),
                                    ],
                                    location: SourceLocation {
                                        start: Position {
                                            line: 16,
                                            column: 10
                                        },
                                        end: Position {
                                            line: 19,
                                            column: 3
                                        }
                                    },
                                }),
                            ),
                        ],
                        location: SourceLocation {
                            start: Position { line: 1, column: 9 },
                            end: Position {
                                line: 20,
                                column: 1
                            }
                        },
                    },
                )],
            }))
        )
    }

    #[gtest]
    fn strings() -> Result<()> {
        verify_that!(
            parse(include_str!("../../testdata/valid/strings.defcl")),
            eq(&parsed(ParsedFile {
                top_level_messages: vec![top_level_message(
                    name("config", 1, 1),
                    MessageValue {
                        fields: vec![
                            field(
                                name("basic", 2, 3),
                                Value::String(scalar(r#""hello""#, 2, 10)),
                            ),
                            field(
                                name("with_spaces", 3, 3),
                                Value::String(scalar(r#""hello world""#, 3, 16)),
                            ),
                            field(
                                name("with_newline", 4, 3),
                                Value::String(scalar(r#""line1\nline2""#, 4, 17)),
                            ),
                            field(
                                name("with_tab", 5, 3),
                                Value::String(scalar(r#""col1\tcol2""#, 5, 13)),
                            ),
                            field(
                                name("with_backslash", 6, 3),
                                Value::String(scalar(r#""path\\to\\file""#, 6, 19)),
                            ),
                            field(
                                name("with_quote", 7, 3),
                                Value::String(scalar(r#""say \"hello\"""#, 7, 15)),
                            ),
                            field(
                                name("with_apostrophe", 8, 3),
                                Value::String(scalar(r#""it\'s fine""#, 8, 20)),
                            ),
                            field(
                                name("with_bell", 9, 3),
                                Value::String(scalar(r#""\a""#, 9, 14)),
                            ),
                            field(
                                name("with_backspace", 10, 3),
                                Value::String(scalar(r#""\b""#, 10, 19)),
                            ),
                            field(
                                name("with_formfeed", 11, 3),
                                Value::String(scalar(r#""\f""#, 11, 18)),
                            ),
                            field(
                                name("with_return", 12, 3),
                                Value::String(scalar(r#""\r""#, 12, 16)),
                            ),
                            field(
                                name("with_vtab", 13, 3),
                                Value::String(scalar(r#""\v""#, 13, 14)),
                            ),
                            field(
                                name("with_question", 14, 3),
                                Value::String(scalar(r#""\?""#, 14, 18)),
                            ),
                            field(
                                name("octal_escape", 15, 3),
                                Value::String(scalar(r#""\101""#, 15, 17)),
                            ),
                            field(
                                name("hex_escape", 16, 3),
                                Value::String(scalar(r#""\x41""#, 16, 15)),
                            ),
                            field(
                                name("unicode_bmp", 17, 3),
                                Value::String(scalar(r#""\u0041""#, 17, 16)),
                            ),
                            field(
                                name("unicode_smp", 18, 3),
                                Value::String(scalar(r#""\U00000041""#, 18, 16)),
                            ),
                            field(
                                name("unicode_spb", 19, 3),
                                Value::String(scalar(r#""\U00100000""#, 19, 16)),
                            ),
                            field(
                                name("utf8_hex_escapes", 20, 3),
                                Value::String(scalar(r#""caf\xc3\xa9""#, 20, 21)),
                            ),
                            field(
                                name("utf8_octal_escapes", 21, 3),
                                Value::String(scalar(r#""caf\303\251""#, 21, 23)),
                            ),
                        ],
                        location: SourceLocation {
                            start: Position { line: 1, column: 9 },
                            end: Position {
                                line: 22,
                                column: 1
                            }
                        },
                    },
                )],
            }))
        )
    }
}

mod valid_source {
    use super::*;

    #[gtest]
    fn columns_count_characters() -> Result<()> {
        verify_that!(
            parse("a: {\n  b: \"caf\u{e9}\"\n  # \u{e9}\n  c: 1\n}\n"),
            eq(&parsed(ParsedFile {
                top_level_messages: vec![top_level_message(
                    name("a", 1, 1),
                    MessageValue {
                        fields: vec![
                            field(
                                name("b", 2, 3),
                                Value::String(Scalar {
                                    text: "\"caf\u{e9}\"",
                                    location: location(2, 6, 2, 11),
                                }),
                            ),
                            field(name("c", 4, 3), Value::Integer(scalar("1", 4, 6))),
                        ],
                        location: location(1, 4, 5, 1),
                    },
                )],
            }))
        )
    }

    #[gtest]
    fn tabs_and_carriage_returns_in_strings_and_comments() -> Result<()> {
        verify_that!(
            parse("a: {\n  # \t\rc\n  b: \"x\t\ry\"\n}\n"),
            eq(&parsed(ParsedFile {
                top_level_messages: vec![top_level_message(
                    name("a", 1, 1),
                    MessageValue {
                        fields: vec![field(
                            name("b", 3, 3),
                            Value::String(scalar("\"x\t\ry\"", 3, 6)),
                        )],
                        location: location(1, 4, 4, 1),
                    },
                )],
            }))
        )
    }

    #[gtest]
    fn fraction_with_zero_before_last_digit() -> Result<()> {
        verify_that!(
            parse("a: {\n  b: 1.05\n}\n"),
            eq(&parsed(ParsedFile {
                top_level_messages: vec![top_level_message(
                    name("a", 1, 1),
                    MessageValue {
                        fields: vec![field(name("b", 2, 3), Value::Float(scalar("1.05", 2, 6)))],
                        location: SourceLocation {
                            start: Position { line: 1, column: 4 },
                            end: Position { line: 3, column: 1 }
                        },
                    },
                )],
            }))
        )
    }

    #[gtest]
    fn shortest_escapes() -> Result<()> {
        verify_that!(
            parse("a: {\n  b: \"\\0\\x4\"\n}\n"),
            eq(&parsed(ParsedFile {
                top_level_messages: vec![top_level_message(
                    name("a", 1, 1),
                    MessageValue {
                        fields: vec![field(
                            name("b", 2, 3),
                            Value::String(scalar("\"\\0\\x4\"", 2, 6)),
                        )],
                        location: SourceLocation {
                            start: Position { line: 1, column: 4 },
                            end: Position { line: 3, column: 1 }
                        },
                    },
                )],
            }))
        )
    }

    #[gtest]
    fn comment_after_last_element() -> Result<()> {
        verify_that!(
            parse("a: {\n  b: [\n    1\n    # one\n  ]\n}\n"),
            eq(&parsed(ParsedFile {
                top_level_messages: vec![top_level_message(
                    name("a", 1, 1),
                    MessageValue {
                        fields: vec![field(
                            name("b", 2, 3),
                            Value::Repeated(RepeatedValue {
                                values: vec![Value::Integer(scalar("1", 3, 5))],
                                location: location(2, 6, 5, 3),
                            }),
                        )],
                        location: location(1, 4, 6, 1),
                    },
                )],
            }))
        )
    }

    #[gtest]
    fn comment_text_that_starts_with_spaces() -> Result<()> {
        verify_that!(
            parse("a: {\n  #   |\n  b: 1\n}\n"),
            eq(&parsed(ParsedFile {
                top_level_messages: vec![top_level_message(
                    name("a", 1, 1),
                    MessageValue {
                        fields: vec![field(name("b", 3, 3), Value::Integer(scalar("1", 3, 6)))],
                        location: location(1, 4, 4, 1),
                    },
                )],
            }))
        )
    }

    #[gtest]
    fn comment_without_text() -> Result<()> {
        verify_that!(
            parse("a: {\n  #\n  b: 1\n}\n"),
            eq(&parsed(ParsedFile {
                top_level_messages: vec![top_level_message(
                    name("a", 1, 1),
                    MessageValue {
                        fields: vec![field(name("b", 3, 3), Value::Integer(scalar("1", 3, 6)))],
                        location: location(1, 4, 4, 1),
                    },
                )],
            }))
        )
    }
}

mod invalid_layout {
    use super::*;

    #[gtest]
    fn field_indented_too_little() -> Result<()> {
        verify_eq!(
            layout_errors("a: {\n b: 1\n}\n")?,
            vec![SyntaxError {
                kind: SyntaxErrorKind::WrongIndentation { expected_spaces: 2 },
                location: location(2, 1, 2, 1),
            },]
        )
    }

    #[gtest]
    fn field_not_indented() -> Result<()> {
        verify_eq!(
            layout_errors("a: {\nb: 1\n}\n")?,
            vec![SyntaxError {
                kind: SyntaxErrorKind::WrongIndentation { expected_spaces: 2 },
                location: location(2, 1, 2, 1),
            },]
        )
    }

    #[gtest]
    fn close_brace_indented() -> Result<()> {
        verify_eq!(
            layout_errors("a: {\n  b: 1\n  }\n")?,
            vec![SyntaxError {
                kind: SyntaxErrorKind::WrongIndentation { expected_spaces: 0 },
                location: location(3, 1, 3, 2),
            },]
        )
    }

    #[gtest]
    fn element_indented_too_little() -> Result<()> {
        verify_eq!(
            layout_errors("a: {\n  b: [\n   1\n  ]\n}\n")?,
            vec![SyntaxError {
                kind: SyntaxErrorKind::WrongIndentation { expected_spaces: 4 },
                location: location(3, 1, 3, 3),
            },]
        )
    }

    #[gtest]
    fn comment_indented_too_little() -> Result<()> {
        verify_eq!(
            layout_errors("a: {\n # c\n  b: 1\n}\n")?,
            vec![SyntaxError {
                kind: SyntaxErrorKind::WrongIndentation { expected_spaces: 2 },
                location: location(2, 1, 2, 1),
            },]
        )
    }

    #[gtest]
    fn field_on_the_line_of_the_open_brace() -> Result<()> {
        verify_eq!(
            layout_errors("a: { b: 1\n}\n")?,
            vec![SyntaxError {
                kind: SyntaxErrorKind::MissingLineBreak,
                location: location(1, 6, 1, 6),
            },]
        )
    }

    #[gtest]
    fn close_brace_on_the_line_of_the_last_field() -> Result<()> {
        verify_eq!(
            layout_errors("a: {\n  b: 1 }\n")?,
            vec![SyntaxError {
                kind: SyntaxErrorKind::MissingLineBreak,
                location: location(2, 8, 2, 8),
            },]
        )
    }

    #[gtest]
    fn two_fields_on_one_line() -> Result<()> {
        verify_eq!(
            layout_errors("a: {\n  b: 1 c: 2\n}\n")?,
            vec![SyntaxError {
                kind: SyntaxErrorKind::MissingLineBreak,
                location: location(2, 8, 2, 8),
            },]
        )
    }

    #[gtest]
    fn elements_on_one_line() -> Result<()> {
        verify_eq!(
            layout_errors("a: {\n  b: [1, 2]\n}\n")?,
            vec![
                SyntaxError {
                    kind: SyntaxErrorKind::MissingLineBreak,
                    location: location(2, 7, 2, 7),
                },
                SyntaxError {
                    kind: SyntaxErrorKind::MissingLineBreak,
                    location: location(2, 10, 2, 10),
                },
                SyntaxError {
                    kind: SyntaxErrorKind::MissingLineBreak,
                    location: location(2, 11, 2, 11),
                },
            ]
        )
    }

    #[gtest]
    fn blank_line_with_spaces() -> Result<()> {
        verify_eq!(
            layout_errors("a: {\n  b: 1\n  \n  c: 2\n}\n")?,
            vec![SyntaxError {
                kind: SyntaxErrorKind::BlankLine,
                location: location(3, 1, 3, 3),
            },]
        )
    }

    #[gtest]
    fn trailing_whitespace() -> Result<()> {
        verify_eq!(
            layout_errors("a: {\n  b: 1  \n}\n")?,
            vec![SyntaxError {
                kind: SyntaxErrorKind::TrailingWhitespace,
                location: location(2, 7, 2, 8),
            },]
        )
    }

    #[gtest]
    fn trailing_whitespace_in_comment() -> Result<()> {
        verify_eq!(
            layout_errors("a: {\n  # c \t\n  b: 1\n}\n")?,
            vec![SyntaxError {
                kind: SyntaxErrorKind::TrailingWhitespace,
                location: location(2, 6, 2, 7),
            },]
        )
    }

    #[gtest]
    fn comment_of_only_a_space() -> Result<()> {
        verify_eq!(
            layout_errors("a: {\n  # \n  b: 1\n}\n")?,
            vec![SyntaxError {
                kind: SyntaxErrorKind::TrailingWhitespace,
                location: location(2, 4, 2, 4),
            },]
        )
    }

    #[gtest]
    fn spaces_at_the_end_of_the_file() -> Result<()> {
        verify_eq!(
            layout_errors("a: {\n  b: 1\n}\n ")?,
            vec![SyntaxError {
                kind: SyntaxErrorKind::TrailingWhitespace,
                location: location(4, 1, 4, 1),
            }]
        )
    }

    #[gtest]
    fn comment_after_the_last_message_without_a_line_feed() -> Result<()> {
        verify_eq!(
            layout_errors("a: {\n  b: 1\n} # c")?,
            vec![
                SyntaxError {
                    kind: SyntaxErrorKind::CommentNotOnOwnLine,
                    location: location(3, 3, 3, 5),
                },
                SyntaxError {
                    kind: SyntaxErrorKind::MissingTrailingNewline,
                    location: location(3, 5, 3, 5),
                },
            ]
        )
    }

    #[gtest]
    fn comment_not_on_its_own_line() -> Result<()> {
        verify_eq!(
            layout_errors("a: {\n  b: 1 # c\n}\n")?,
            vec![SyntaxError {
                kind: SyntaxErrorKind::CommentNotOnOwnLine,
                location: location(2, 8, 2, 10),
            },]
        )
    }

    #[gtest]
    fn comment_without_space() -> Result<()> {
        verify_eq!(
            layout_errors("a: {\n  #c\n  b: 1\n}\n")?,
            vec![SyntaxError {
                kind: SyntaxErrorKind::CommentSpacing,
                location: location(2, 3, 2, 3),
            },]
        )
    }

    #[gtest]
    fn no_space_after_field_colon() -> Result<()> {
        verify_eq!(
            layout_errors("a: {\n  b:1\n}\n")?,
            vec![SyntaxError {
                kind: SyntaxErrorKind::WrongSpacingAfterColon,
                location: location(2, 5, 2, 5),
            },]
        )
    }

    #[gtest]
    fn empty_message_value_over_two_lines() -> Result<()> {
        verify_eq!(
            layout_errors("a: {\n  b: {\n  }\n}\n")?,
            vec![SyntaxError {
                kind: SyntaxErrorKind::EmptyMessageValue,
                location: location(2, 6, 3, 3),
            },]
        )
    }

    #[gtest]
    fn blank_line() -> Result<()> {
        verify_eq!(
            layout_errors(include_str!(
                "../../testdata/invalid/syntax/whitespace/blank_line.defcl"
            ))?,
            vec![SyntaxError {
                kind: SyntaxErrorKind::BlankLine,
                location: location(4, 1, 4, 1),
            }]
        )
    }

    #[gtest]
    fn empty_message_value() -> Result<()> {
        verify_eq!(
            layout_errors(include_str!(
                "../../testdata/invalid/syntax/messages/empty_message_value.defcl"
            ))?,
            vec![SyntaxError {
                kind: SyntaxErrorKind::EmptyMessageValue,
                location: location(1, 10, 1, 11),
            }]
        )
    }

    #[gtest]
    fn empty_repeated_value() -> Result<()> {
        verify_eq!(
            layout_errors(include_str!(
                "../../testdata/invalid/syntax/repeated_values/empty_repeated_value.defcl"
            ))?,
            vec![SyntaxError {
                kind: SyntaxErrorKind::EmptyRepeatedValue,
                location: location(2, 17, 2, 18),
            }]
        )
    }

    #[gtest]
    fn layout_errors_before_the_error_that_stops_the_parse() -> Result<()> {
        verify_that!(
            parse("a: {\n b: @\n}\n"),
            eq(&ParseResult {
                file: None,
                errors: vec![
                    SyntaxError {
                        kind: SyntaxErrorKind::WrongIndentation { expected_spaces: 2 },
                        location: location(2, 1, 2, 1),
                    },
                    SyntaxError {
                        kind: SyntaxErrorKind::UnexpectedCharacter { character: '@' },
                        location: location(2, 5, 2, 5),
                    },
                ],
            })
        )
    }
}

mod invalid_booleans {
    use super::*;

    #[gtest]
    fn false_literal() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/booleans/false_literal.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::BooleanNotSupported,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 12
                    },
                    end: Position {
                        line: 2,
                        column: 16
                    }
                }
            }))
        )
    }

    #[gtest]
    fn true_literal() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/booleans/true_literal.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::BooleanNotSupported,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 12
                    },
                    end: Position {
                        line: 2,
                        column: 15
                    }
                }
            }))
        )
    }
}

mod invalid_enums {
    use super::*;

    #[gtest]
    fn lowercase_enum() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/enums/lowercase_enum.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidEnumCase,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 11
                    },
                    end: Position {
                        line: 2,
                        column: 16
                    }
                }
            }))
        )
    }

    #[gtest]
    fn mixed_case_enum() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/enums/mixed_case_enum.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidEnumCase,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 11
                    },
                    end: Position {
                        line: 2,
                        column: 16
                    }
                }
            }))
        )
    }
}

mod invalid_field_names {
    use super::*;

    #[gtest]
    fn double_underscore() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/field_names/double_underscore.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidFieldName,
                location: SourceLocation {
                    start: Position { line: 2, column: 3 },
                    end: Position {
                        line: 2,
                        column: 15
                    }
                }
            }))
        )
    }

    #[gtest]
    fn hyphen() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/field_names/hyphen.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidFieldName,
                location: SourceLocation {
                    start: Position { line: 2, column: 3 },
                    end: Position {
                        line: 2,
                        column: 15
                    }
                }
            }))
        )
    }

    #[gtest]
    fn leading_digit() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/field_names/leading_digit.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidFieldName,
                location: SourceLocation {
                    start: Position { line: 2, column: 3 },
                    end: Position {
                        line: 2,
                        column: 10
                    }
                }
            }))
        )
    }

    #[gtest]
    fn leading_underscore() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/field_names/leading_underscore.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidFieldName,
                location: SourceLocation {
                    start: Position { line: 2, column: 3 },
                    end: Position {
                        line: 2,
                        column: 16
                    }
                }
            }))
        )
    }

    #[gtest]
    fn period() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/field_names/period.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidFieldName,
                location: SourceLocation {
                    start: Position { line: 2, column: 3 },
                    end: Position {
                        line: 2,
                        column: 15
                    }
                }
            }))
        )
    }

    #[gtest]
    fn trailing_underscore() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/field_names/trailing_underscore.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidFieldName,
                location: SourceLocation {
                    start: Position { line: 2, column: 3 },
                    end: Position {
                        line: 2,
                        column: 16
                    }
                }
            }))
        )
    }

    #[gtest]
    fn underscore_digit() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/field_names/underscore_digit.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidFieldName,
                location: SourceLocation {
                    start: Position { line: 2, column: 3 },
                    end: Position {
                        line: 2,
                        column: 10
                    }
                }
            }))
        )
    }

    #[gtest]
    fn uppercase() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/field_names/uppercase.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidFieldName,
                location: SourceLocation {
                    start: Position { line: 2, column: 3 },
                    end: Position {
                        line: 2,
                        column: 14
                    }
                }
            }))
        )
    }

    #[gtest]
    fn top_level_message_name() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/field_names/top_level_message_name.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidFieldName,
                location: SourceLocation {
                    start: Position { line: 1, column: 1 },
                    end: Position { line: 1, column: 7 }
                }
            }))
        )
    }
}

mod invalid_file_format {
    use super::*;

    #[gtest]
    fn bom() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/file_format/bom.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::ByteOrderMark,
                location: SourceLocation {
                    start: Position { line: 1, column: 1 },
                    end: Position { line: 1, column: 1 }
                }
            }))
        )
    }

    #[gtest]
    fn no_trailing_newline() -> Result<()> {
        verify_eq!(
            layout_errors(include_str!(
                "../../testdata/invalid/syntax/file_format/no_trailing_newline.defcl"
            ))?,
            vec![SyntaxError {
                kind: SyntaxErrorKind::MissingTrailingNewline,
                location: location(3, 1, 3, 1),
            },]
        )
    }

    #[gtest]
    fn no_trailing_newline_after_comment() -> Result<()> {
        verify_eq!(
            layout_errors(include_str!(
                "../../testdata/invalid/syntax/file_format/no_trailing_newline_after_comment.defcl"
            ))?,
            vec![SyntaxError {
                kind: SyntaxErrorKind::MissingTrailingNewline,
                location: location(4, 5, 4, 5),
            },]
        )
    }

    #[gtest]
    fn empty_file() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/file_format/empty_file.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::MissingTopLevelMessage,
                location: SourceLocation {
                    start: Position { line: 1, column: 1 },
                    end: Position { line: 1, column: 1 }
                }
            }))
        )
    }

    #[gtest]
    fn only_a_comment() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/file_format/only_a_comment.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::MissingTopLevelMessage,
                location: SourceLocation {
                    start: Position { line: 2, column: 1 },
                    end: Position { line: 2, column: 1 }
                }
            }))
        )
    }
}

mod invalid_messages {
    use super::*;

    #[gtest]
    fn angle_brackets() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/messages/angle_brackets.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::AngleBracketsNotAllowed,
                location: SourceLocation {
                    start: Position {
                        line: 1,
                        column: 10
                    },
                    end: Position {
                        line: 1,
                        column: 10
                    }
                }
            }))
        )
    }

    #[gtest]
    fn nested_angle_brackets() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/messages/nested_angle_brackets.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::AngleBracketsNotAllowed,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 11
                    },
                    end: Position {
                        line: 2,
                        column: 11
                    }
                }
            }))
        )
    }

    #[gtest]
    fn quoted_field_name() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/messages/quoted_field_name.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::ExpectedFieldNameOrCloseBrace,
                location: SourceLocation {
                    start: Position { line: 2, column: 3 },
                    end: Position { line: 2, column: 3 }
                }
            }))
        )
    }

    #[gtest]
    fn fields_without_whitespace_between_them() -> Result<()> {
        verify_eq!(
            layout_errors(include_str!(
                "../../testdata/invalid/syntax/messages/fields_without_whitespace_between_them.defcl"
            ))?,
            vec![SyntaxError {
                kind: SyntaxErrorKind::MissingLineBreak,
                location: location(2, 9, 2, 9),
            },]
        )
    }

    #[gtest]
    fn top_level_messages_without_whitespace_between_them() -> Result<()> {
        verify_eq!(
            layout_errors(include_str!(
                "../../testdata/invalid/syntax/messages/top_level_messages_without_whitespace_between_them.defcl"
            ))?,
            vec![SyntaxError {
                kind: SyntaxErrorKind::MissingLineBreak,
                location: location(3, 2, 3, 2),
            },]
        )
    }

    #[gtest]
    fn unclosed_message() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/messages/unclosed_message.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::UnclosedMessage,
                location: SourceLocation {
                    start: Position { line: 1, column: 4 },
                    end: Position { line: 1, column: 4 }
                }
            }))
        )
    }
}

mod invalid_numbers {
    use super::*;

    #[gtest]
    fn hex() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/numbers/hex.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidNumberFormat,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 10
                    },
                    end: Position {
                        line: 2,
                        column: 13
                    }
                }
            }))
        )
    }

    #[gtest]
    fn octal() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/numbers/octal.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidNumberFormat,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 10
                    },
                    end: Position {
                        line: 2,
                        column: 13
                    }
                }
            }))
        )
    }

    #[gtest]
    fn scientific_int() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/numbers/scientific_int.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidNumberFormat,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 10
                    },
                    end: Position {
                        line: 2,
                        column: 12
                    }
                }
            }))
        )
    }

    #[gtest]
    fn scientific_float() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/numbers/scientific_float.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidNumberFormat,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 10
                    },
                    end: Position {
                        line: 2,
                        column: 15
                    }
                }
            }))
        )
    }

    #[gtest]
    fn leading_zeros() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/numbers/leading_zeros.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidNumberFormat,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 10
                    },
                    end: Position {
                        line: 2,
                        column: 12
                    }
                }
            }))
        )
    }

    #[gtest]
    fn leading_decimal() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/numbers/leading_decimal.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidNumberFormat,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 10
                    },
                    end: Position {
                        line: 2,
                        column: 11
                    }
                }
            }))
        )
    }

    #[gtest]
    fn trailing_decimal() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/numbers/trailing_decimal.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidNumberFormat,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 10
                    },
                    end: Position {
                        line: 2,
                        column: 12
                    }
                }
            }))
        )
    }

    #[gtest]
    fn negative_zero_integer() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/numbers/negative_zero_integer.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::NegativeZero,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 10
                    },
                    end: Position {
                        line: 2,
                        column: 11
                    }
                }
            }))
        )
    }

    #[gtest]
    fn negative_zero_float() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/numbers/negative_zero_float.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::NegativeZero,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 10
                    },
                    end: Position {
                        line: 2,
                        column: 13
                    }
                }
            }))
        )
    }

    #[gtest]
    fn plus_sign() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/numbers/plus_sign.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidNumberFormat,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 10
                    },
                    end: Position {
                        line: 2,
                        column: 12
                    }
                }
            }))
        )
    }

    #[gtest]
    fn space_after_sign() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/numbers/space_after_sign.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidNumberFormat,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 10
                    },
                    end: Position {
                        line: 2,
                        column: 10
                    }
                }
            }))
        )
    }

    #[gtest]
    fn type_suffix_f() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/numbers/type_suffix_f.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidNumberFormat,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 10
                    },
                    end: Position {
                        line: 2,
                        column: 12
                    }
                }
            }))
        )
    }

    #[gtest]
    fn type_suffix_upper_f() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/numbers/type_suffix_upper_f.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidNumberFormat,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 10
                    },
                    end: Position {
                        line: 2,
                        column: 12
                    }
                }
            }))
        )
    }

    #[gtest]
    fn type_suffix_d() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/numbers/type_suffix_d.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidNumberFormat,
                location: SourceLocation {
                    start: Position { line: 2, column: 6 },
                    end: Position { line: 2, column: 9 }
                }
            }))
        )
    }

    #[gtest]
    fn type_suffix_l() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/numbers/type_suffix_l.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidNumberFormat,
                location: SourceLocation {
                    start: Position { line: 2, column: 6 },
                    end: Position { line: 2, column: 9 }
                }
            }))
        )
    }

    #[gtest]
    fn bare_e_suffix() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/numbers/bare_e_suffix.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidNumberFormat,
                location: SourceLocation {
                    start: Position { line: 2, column: 6 },
                    end: Position { line: 2, column: 9 }
                }
            }))
        )
    }

    #[gtest]
    fn fraction_with_trailing_zero() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/numbers/fraction_with_trailing_zero.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidNumberFormat,
                location: SourceLocation {
                    start: Position { line: 2, column: 6 },
                    end: Position { line: 2, column: 9 }
                }
            }))
        )
    }

    #[gtest]
    fn fraction_of_only_zeros() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/numbers/fraction_of_only_zeros.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidNumberFormat,
                location: SourceLocation {
                    start: Position { line: 2, column: 6 },
                    end: Position { line: 2, column: 9 }
                }
            }))
        )
    }

    #[gtest]
    fn extra_decimal_after_float() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/numbers/extra_decimal_after_float.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidNumberFormat,
                location: SourceLocation {
                    start: Position { line: 2, column: 6 },
                    end: Position {
                        line: 2,
                        column: 11
                    }
                }
            }))
        )
    }
}

mod invalid_characters {
    use super::*;

    #[gtest]
    fn at_sign() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/characters/at_sign.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::UnexpectedCharacter { character: '@' },
                location: SourceLocation {
                    start: Position { line: 2, column: 6 },
                    end: Position { line: 2, column: 6 }
                },
            }))
        )
    }

    #[gtest]
    fn non_ascii_character_outside_strings_and_comments() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/characters/non_ascii_character_outside_strings_and_comments.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::UnexpectedCharacter {
                    character: '\u{e9}'
                },
                location: SourceLocation {
                    start: Position { line: 2, column: 6 },
                    end: Position { line: 2, column: 6 }
                },
            }))
        )
    }

    #[gtest]
    fn nul_in_string() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/characters/nul_in_string.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::UnexpectedCharacter { character: '\0' },
                location: SourceLocation {
                    start: Position { line: 2, column: 8 },
                    end: Position { line: 2, column: 8 }
                },
            }))
        )
    }

    #[gtest]
    fn nul_in_comment() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/characters/nul_in_comment.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::UnexpectedCharacter { character: '\0' },
                location: location(4, 4, 4, 4),
            }))
        )
    }

    #[gtest]
    fn nul_in_comment_at_start_of_file() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/characters/nul_in_comment_at_start_of_file.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::UnexpectedCharacter { character: '\0' },
                location: SourceLocation {
                    start: Position { line: 1, column: 2 },
                    end: Position { line: 1, column: 2 }
                },
            }))
        )
    }

    #[gtest]
    fn nul_in_comment_after_top_level_colon() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/characters/nul_in_comment_after_top_level_colon.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::UnexpectedCharacter { character: '\0' },
                location: SourceLocation {
                    start: Position { line: 1, column: 5 },
                    end: Position { line: 1, column: 5 }
                },
            }))
        )
    }

    #[gtest]
    fn nul_in_comment_after_field_colon() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/characters/nul_in_comment_after_field_colon.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::UnexpectedCharacter { character: '\0' },
                location: SourceLocation {
                    start: Position { line: 2, column: 7 },
                    end: Position { line: 2, column: 7 }
                },
            }))
        )
    }

    #[gtest]
    fn nul_in_comment_at_start_of_message_value() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/characters/nul_in_comment_at_start_of_message_value.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::UnexpectedCharacter { character: '\0' },
                location: SourceLocation {
                    start: Position { line: 1, column: 7 },
                    end: Position { line: 1, column: 7 }
                },
            }))
        )
    }

    #[gtest]
    fn nul_in_comment_after_field() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/characters/nul_in_comment_after_field.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::UnexpectedCharacter { character: '\0' },
                location: SourceLocation {
                    start: Position { line: 2, column: 9 },
                    end: Position { line: 2, column: 9 }
                },
            }))
        )
    }

    #[gtest]
    fn nul_in_comment_at_start_of_repeated_value() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/characters/nul_in_comment_at_start_of_repeated_value.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::UnexpectedCharacter { character: '\0' },
                location: SourceLocation {
                    start: Position { line: 2, column: 9 },
                    end: Position { line: 2, column: 9 }
                },
            }))
        )
    }

    #[gtest]
    fn nul_in_comment_after_comma() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/characters/nul_in_comment_after_comma.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::UnexpectedCharacter { character: '\0' },
                location: location(4, 6, 4, 6),
            }))
        )
    }

    #[gtest]
    fn nul_in_comment_after_repeated_element() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/characters/nul_in_comment_after_repeated_element.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::UnexpectedCharacter { character: '\0' },
                location: location(4, 6, 4, 6),
            }))
        )
    }

    #[gtest]
    fn nul_in_comment_after_field_name() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/characters/nul_in_comment_after_field_name.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::UnexpectedCharacter { character: '\0' },
                location: SourceLocation {
                    start: Position { line: 1, column: 4 },
                    end: Position { line: 1, column: 4 }
                },
            }))
        )
    }
}

mod invalid_separators {
    use super::*;

    #[gtest]
    fn comma_separator() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/separators/comma_separator.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidSeparator,
                location: SourceLocation {
                    start: Position { line: 2, column: 7 },
                    end: Position { line: 2, column: 7 }
                }
            }))
        )
    }

    #[gtest]
    fn trailing_comma_in_message() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/separators/trailing_comma_in_message.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidSeparator,
                location: SourceLocation {
                    start: Position { line: 2, column: 7 },
                    end: Position { line: 2, column: 7 }
                }
            }))
        )
    }

    #[gtest]
    fn comma_between_top_level_messages() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/separators/comma_between_top_level_messages.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidSeparator,
                location: location(3, 2, 3, 2),
            }))
        )
    }

    #[gtest]
    fn missing_colon() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/separators/missing_colon.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::MissingColon,
                location: SourceLocation {
                    start: Position { line: 2, column: 8 },
                    end: Position { line: 2, column: 8 }
                }
            }))
        )
    }

    #[gtest]
    fn field_named_f_missing_colon() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/separators/field_named_f_missing_colon.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::MissingColon,
                location: SourceLocation {
                    start: Position { line: 2, column: 4 },
                    end: Position { line: 2, column: 4 }
                }
            }))
        )
    }

    #[gtest]
    fn missing_colon_at_end_of_source() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/separators/missing_colon_at_end_of_source.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::MissingColon,
                location: SourceLocation {
                    start: Position { line: 1, column: 2 },
                    end: Position { line: 1, column: 2 }
                }
            }))
        )
    }

    #[gtest]
    fn whitespace_before_colon() -> Result<()> {
        verify_eq!(
            layout_errors(include_str!(
                "../../testdata/invalid/syntax/separators/whitespace_before_colon.defcl"
            ))?,
            vec![SyntaxError {
                kind: SyntaxErrorKind::WhitespaceBeforeColon,
                location: location(2, 4, 2, 4),
            },]
        )
    }

    #[gtest]
    fn comment_before_top_level_colon() -> Result<()> {
        verify_eq!(
            layout_errors(include_str!(
                "../../testdata/invalid/syntax/separators/comment_before_top_level_colon.defcl"
            ))?,
            vec![SyntaxError {
                kind: SyntaxErrorKind::MisplacedComment,
                location: location(1, 3, 1, 5),
            },]
        )
    }

    #[gtest]
    fn semicolon() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/separators/semicolon.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidSeparator,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 16
                    },
                    end: Position {
                        line: 2,
                        column: 16
                    }
                }
            }))
        )
    }
}

mod invalid_repeated_values {
    use super::*;

    #[gtest]
    fn missing_comma() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/repeated_values/missing_comma.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::ExpectedCommaOrCloseBracket,
                location: location(4, 5, 4, 5),
            }))
        )
    }

    #[gtest]
    fn whitespace_before_comma() -> Result<()> {
        verify_eq!(
            layout_errors(include_str!(
                "../../testdata/invalid/syntax/repeated_values/whitespace_before_comma.defcl"
            ))?,
            vec![SyntaxError {
                kind: SyntaxErrorKind::WhitespaceBeforeComma,
                location: location(3, 6, 3, 6),
            },]
        )
    }

    #[gtest]
    fn comment_before_comma() -> Result<()> {
        verify_eq!(
            layout_errors(include_str!(
                "../../testdata/invalid/syntax/repeated_values/comment_before_comma.defcl"
            ))?,
            vec![SyntaxError {
                kind: SyntaxErrorKind::MisplacedComment,
                location: location(3, 7, 4, 7),
            },]
        )
    }

    #[gtest]
    fn trailing_comma() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/repeated_values/trailing_comma.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::ExpectedValue,
                location: location(4, 3, 4, 3),
            }))
        )
    }

    #[gtest]
    fn unclosed_empty_repeated_value() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/repeated_values/unclosed_empty_repeated_value.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::UnclosedRepeatedValue,
                location: SourceLocation {
                    start: Position { line: 2, column: 6 },
                    end: Position { line: 2, column: 6 }
                }
            }))
        )
    }

    #[gtest]
    fn unclosed_repeated_value() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/repeated_values/unclosed_repeated_value.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::UnclosedRepeatedValue,
                location: location(2, 6, 2, 6),
            }))
        )
    }

    #[gtest]
    fn semicolon_between_values() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/repeated_values/semicolon_between_values.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidSeparator,
                location: location(3, 6, 3, 6),
            }))
        )
    }

    #[gtest]
    fn repeated_value_in_repeated_value() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/repeated_values/repeated_value_in_repeated_value.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::RepeatedValueInRepeatedValue,
                location: location(4, 5, 4, 5),
            }))
        )
    }
}

mod invalid_values {
    use super::*;

    #[gtest]
    fn close_brace_where_value_belongs() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/values/close_brace_where_value_belongs.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::ExpectedValue,
                location: SourceLocation {
                    start: Position { line: 2, column: 6 },
                    end: Position { line: 2, column: 6 }
                }
            }))
        )
    }

    #[gtest]
    fn end_of_source_where_value_belongs() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/values/end_of_source_where_value_belongs.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::ExpectedValue,
                location: SourceLocation {
                    start: Position { line: 2, column: 5 },
                    end: Position { line: 2, column: 5 }
                }
            }))
        )
    }
}

mod invalid_strings {
    use super::*;

    #[gtest]
    fn raw_newline() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/strings/raw_newline.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::UnterminatedString,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 10
                    },
                    end: Position {
                        line: 2,
                        column: 15
                    }
                }
            }))
        )
    }

    #[gtest]
    fn unterminated_at_end_of_source() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/strings/unterminated_at_end_of_source.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::UnterminatedString,
                location: SourceLocation {
                    start: Position { line: 2, column: 6 },
                    end: Position { line: 2, column: 7 }
                }
            }))
        )
    }

    #[gtest]
    fn backslash_at_end_of_line() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/strings/backslash_at_end_of_line.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::UnterminatedString,
                location: SourceLocation {
                    start: Position { line: 2, column: 6 },
                    end: Position { line: 2, column: 8 }
                }
            }))
        )
    }

    #[gtest]
    fn backslash_at_end_of_source() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/strings/backslash_at_end_of_source.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::UnterminatedString,
                location: SourceLocation {
                    start: Position { line: 2, column: 6 },
                    end: Position { line: 2, column: 8 }
                }
            }))
        )
    }

    #[gtest]
    fn single_quotes() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/strings/single_quotes.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::SingleQuotesNotAllowed,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 10
                    },
                    end: Position {
                        line: 2,
                        column: 16
                    }
                }
            }))
        )
    }

    #[gtest]
    fn single_quote_without_closing_quote() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/strings/single_quote_without_closing_quote.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::SingleQuotesNotAllowed,
                location: SourceLocation {
                    start: Position { line: 2, column: 6 },
                    end: Position { line: 2, column: 6 }
                }
            }))
        )
    }

    #[gtest]
    fn hex_escape_of_invalid_utf8_byte() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/strings/hex_escape_of_invalid_utf8_byte.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidUtf8,
                location: SourceLocation {
                    start: Position { line: 2, column: 7 },
                    end: Position {
                        line: 2,
                        column: 10
                    }
                }
            }))
        )
    }

    #[gtest]
    fn octal_escape_of_incomplete_utf8_sequence() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/strings/octal_escape_of_incomplete_utf8_sequence.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidUtf8,
                location: SourceLocation {
                    start: Position { line: 2, column: 7 },
                    end: Position {
                        line: 2,
                        column: 10
                    }
                }
            }))
        )
    }

    #[gtest]
    fn invalid_utf8_between_characters() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/strings/invalid_utf8_between_characters.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidUtf8,
                location: SourceLocation {
                    start: Position { line: 2, column: 8 },
                    end: Position {
                        line: 2,
                        column: 15
                    }
                }
            }))
        )
    }

    #[gtest]
    fn utf8_sequence_split_by_escape() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/strings/utf8_sequence_split_by_escape.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidUtf8,
                location: SourceLocation {
                    start: Position { line: 2, column: 7 },
                    end: Position {
                        line: 2,
                        column: 10
                    }
                }
            }))
        )
    }

    #[gtest]
    fn overlong_utf8_sequence() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/strings/overlong_utf8_sequence.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidUtf8,
                location: SourceLocation {
                    start: Position { line: 2, column: 7 },
                    end: Position {
                        line: 2,
                        column: 14
                    }
                }
            }))
        )
    }

    #[gtest]
    fn surrogate_escape() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/strings/surrogate_escape.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::SurrogateEscape,
                location: SourceLocation {
                    start: Position { line: 2, column: 7 },
                    end: Position {
                        line: 2,
                        column: 12
                    }
                }
            }))
        )
    }

    #[gtest]
    fn octal_escape_past_last_byte() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/strings/octal_escape_past_last_byte.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidEscapeSequence,
                location: SourceLocation {
                    start: Position { line: 2, column: 7 },
                    end: Position {
                        line: 2,
                        column: 10
                    }
                }
            }))
        )
    }

    #[gtest]
    fn byte_escape_before_backslash_at_end_of_line() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/strings/byte_escape_before_backslash_at_end_of_line.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::UnterminatedString,
                location: SourceLocation {
                    start: Position { line: 2, column: 6 },
                    end: Position {
                        line: 2,
                        column: 11
                    }
                }
            }))
        )
    }

    #[gtest]
    fn unknown_escape() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/strings/unknown_escape.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidEscapeSequence,
                location: SourceLocation {
                    start: Position { line: 2, column: 7 },
                    end: Position { line: 2, column: 8 }
                }
            }))
        )
    }

    #[gtest]
    fn non_octal_digit_escape() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/strings/non_octal_digit_escape.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidEscapeSequence,
                location: SourceLocation {
                    start: Position { line: 2, column: 7 },
                    end: Position { line: 2, column: 8 }
                }
            }))
        )
    }

    #[gtest]
    fn hex_escape_without_digits() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/strings/hex_escape_without_digits.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidEscapeSequence,
                location: SourceLocation {
                    start: Position { line: 2, column: 7 },
                    end: Position { line: 2, column: 8 }
                }
            }))
        )
    }

    #[gtest]
    fn short_unicode_escape() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/strings/short_unicode_escape.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidEscapeSequence,
                location: SourceLocation {
                    start: Position { line: 2, column: 7 },
                    end: Position {
                        line: 2,
                        column: 10
                    }
                }
            }))
        )
    }

    #[gtest]
    fn unicode_escape_past_last_code_point() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/strings/unicode_escape_past_last_code_point.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidEscapeSequence,
                location: SourceLocation {
                    start: Position { line: 2, column: 7 },
                    end: Position {
                        line: 2,
                        column: 16
                    }
                }
            }))
        )
    }

    #[gtest]
    fn short_long_unicode_escape() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/strings/short_long_unicode_escape.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::InvalidEscapeSequence,
                location: SourceLocation {
                    start: Position { line: 2, column: 7 },
                    end: Position {
                        line: 2,
                        column: 15
                    }
                }
            }))
        )
    }
}

mod invalid_toplevel {
    use super::*;

    #[gtest]
    fn unmatched_close_brace() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/toplevel/unmatched_close_brace.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::ExpectedFieldName,
                location: SourceLocation {
                    start: Position { line: 1, column: 1 },
                    end: Position { line: 1, column: 1 }
                }
            }))
        )
    }

    #[gtest]
    fn missing_toplevel_colon() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/toplevel/missing_toplevel_colon.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::MissingColon,
                location: SourceLocation {
                    start: Position { line: 1, column: 8 },
                    end: Position { line: 1, column: 8 }
                }
            }))
        )
    }

    #[gtest]
    fn scalar_toplevel() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/toplevel/scalar_toplevel.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::ScalarAtToplevel,
                location: SourceLocation {
                    start: Position { line: 1, column: 7 },
                    end: Position {
                        line: 1,
                        column: 13
                    }
                }
            }))
        )
    }

    #[gtest]
    fn repeated_value_at_toplevel() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/toplevel/repeated_value_at_toplevel.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::ScalarAtToplevel,
                location: location(1, 4, 3, 1),
            }))
        )
    }

    #[gtest]
    fn no_space_after_top_level_colon() -> Result<()> {
        verify_eq!(
            layout_errors(include_str!(
                "../../testdata/invalid/syntax/toplevel/no_space_after_top_level_colon.defcl"
            ))?,
            vec![SyntaxError {
                kind: SyntaxErrorKind::WrongSpacingAfterColon,
                location: location(1, 3, 1, 3),
            },]
        )
    }

    #[gtest]
    fn line_feed_after_top_level_colon() -> Result<()> {
        verify_eq!(
            layout_errors(include_str!(
                "../../testdata/invalid/syntax/toplevel/line_feed_after_top_level_colon.defcl"
            ))?,
            vec![SyntaxError {
                kind: SyntaxErrorKind::WrongSpacingAfterColon,
                location: location(1, 3, 1, 3),
            },]
        )
    }

    #[gtest]
    fn end_of_source_after_top_level_colon() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/toplevel/end_of_source_after_top_level_colon.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::ExpectedValue,
                location: SourceLocation {
                    start: Position { line: 1, column: 3 },
                    end: Position { line: 1, column: 3 }
                }
            }))
        )
    }

    #[gtest]
    fn tab_after_top_level_colon() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/toplevel/tab_after_top_level_colon.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::TabNotAllowed,
                location: SourceLocation {
                    start: Position { line: 1, column: 3 },
                    end: Position { line: 1, column: 3 }
                }
            }))
        )
    }

    #[gtest]
    fn two_spaces_after_top_level_colon() -> Result<()> {
        verify_eq!(
            layout_errors(include_str!(
                "../../testdata/invalid/syntax/toplevel/two_spaces_after_top_level_colon.defcl"
            ))?,
            vec![SyntaxError {
                kind: SyntaxErrorKind::WrongSpacingAfterColon,
                location: location(1, 3, 1, 4),
            },]
        )
    }

    #[gtest]
    fn trailing_space_after_top_level_colon() -> Result<()> {
        verify_eq!(
            layout_errors(include_str!(
                "../../testdata/invalid/syntax/toplevel/trailing_space_after_top_level_colon.defcl"
            ))?,
            vec![SyntaxError {
                kind: SyntaxErrorKind::WrongSpacingAfterColon,
                location: location(1, 3, 1, 4),
            },]
        )
    }

    #[gtest]
    fn comment_after_space_after_top_level_colon() -> Result<()> {
        verify_eq!(
            layout_errors(include_str!(
                "../../testdata/invalid/syntax/toplevel/comment_after_space_after_top_level_colon.defcl"
            ))?,
            vec![SyntaxError {
                kind: SyntaxErrorKind::MisplacedComment,
                location: location(1, 4, 1, 6),
            },]
        )
    }
}

mod invalid_whitespace {
    use super::*;

    #[gtest]
    fn carriage_return() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/whitespace/carriage_return.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::CarriageReturnNotAllowed,
                location: SourceLocation {
                    start: Position {
                        line: 1,
                        column: 10
                    },
                    end: Position {
                        line: 1,
                        column: 10
                    }
                }
            }))
        )
    }

    #[gtest]
    fn tab_char() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/whitespace/tab_char.defcl"
            )),
            eq(&stopped_by(SyntaxError {
                kind: SyntaxErrorKind::TabNotAllowed,
                location: SourceLocation {
                    start: Position { line: 2, column: 1 },
                    end: Position { line: 2, column: 1 }
                }
            }))
        )
    }
}
