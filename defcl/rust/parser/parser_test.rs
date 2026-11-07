use crate::{
    Field, FieldName, MessageValue, ParsedFile, RepeatedValue, Scalar, SyntaxError,
    SyntaxErrorKind, TopLevelMessage, Value, parse,
};
use googletest::prelude::*;
use source_rendering::{Position, SourceLocation};

/// A field name written in ASCII on one line.
const fn name(text: &str, line: usize, column: usize) -> FieldName<'_> {
    FieldName {
        text,
        location: SourceLocation {
            start: Position { line, column },
            end: Position {
                line,
                column: column + text.len() - 1,
            },
        },
    }
}

/// A scalar written in ASCII on one line.
const fn scalar(text: &str, line: usize, column: usize) -> Scalar<'_> {
    Scalar {
        text,
        location: SourceLocation {
            start: Position { line, column },
            end: Position {
                line,
                column: column + text.len() - 1,
            },
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

mod valid_files {
    use super::*;

    #[gtest]
    fn single_toplevel() -> Result<()> {
        verify_that!(
            parse(include_str!("../../testdata/valid/single_toplevel.defcl")),
            eq(&Ok(ParsedFile {
                top_level_messages: vec![top_level_message(
                    name("project", 1, 1),
                    MessageValue {
                        fields: vec![field(
                            name("universe_name", 2, 5),
                            Value::String(scalar("\"example\"", 2, 20)),
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
            eq(&Ok(ParsedFile {
                top_level_messages: vec![
                    top_level_message(
                        name("project", 1, 1),
                        MessageValue {
                            fields: vec![field(
                                name("universe_name", 2, 5),
                                Value::String(scalar("\"example\"", 2, 20)),
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
                                name("log_level", 5, 5),
                                Value::Integer(scalar("3", 5, 16)),
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
            eq(&Ok(ParsedFile {
                top_level_messages: vec![
                    top_level_message(
                        name("project", 2, 1),
                        MessageValue {
                            fields: vec![field(
                                name("universe_name", 4, 5),
                                Value::String(scalar("\"example\"", 4, 20)),
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
                                name("log_level", 8, 5),
                                Value::Integer(scalar("3", 8, 16)),
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
    fn empty_message() -> Result<()> {
        verify_that!(
            parse(include_str!("../../testdata/valid/empty_message.defcl")),
            eq(&Ok(ParsedFile {
                top_level_messages: vec![top_level_message(
                    name("project", 1, 1),
                    MessageValue {
                        fields: vec![],
                        location: SourceLocation {
                            start: Position {
                                line: 1,
                                column: 10
                            },
                            end: Position {
                                line: 1,
                                column: 11
                            }
                        },
                    },
                )],
            }))
        )
    }

    #[gtest]
    fn empty_repeated_messages() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/valid/empty_repeated_messages.defcl"
            )),
            eq(&Ok(ParsedFile {
                top_level_messages: vec![top_level_message(
                    name("project", 1, 1),
                    MessageValue {
                        fields: vec![field(
                            name("dependencies", 2, 5),
                            Value::Repeated(RepeatedValue {
                                values: vec![],
                                location: SourceLocation {
                                    start: Position {
                                        line: 2,
                                        column: 19
                                    },
                                    end: Position {
                                        line: 2,
                                        column: 20
                                    }
                                },
                            }),
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
    fn empty_repeated_scalars() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/valid/empty_repeated_scalars.defcl"
            )),
            eq(&Ok(ParsedFile {
                top_level_messages: vec![top_level_message(
                    name("config", 1, 1),
                    MessageValue {
                        fields: vec![
                            field(
                                name("tags", 2, 5),
                                Value::Repeated(RepeatedValue {
                                    values: vec![],
                                    location: SourceLocation {
                                        start: Position {
                                            line: 2,
                                            column: 11
                                        },
                                        end: Position {
                                            line: 2,
                                            column: 12
                                        }
                                    },
                                }),
                            ),
                            field(
                                name("items", 3, 5),
                                Value::Repeated(RepeatedValue {
                                    values: vec![],
                                    location: SourceLocation {
                                        start: Position {
                                            line: 3,
                                            column: 12
                                        },
                                        end: Position {
                                            line: 3,
                                            column: 13
                                        }
                                    },
                                }),
                            ),
                        ],
                        location: SourceLocation {
                            start: Position { line: 1, column: 9 },
                            end: Position { line: 4, column: 1 }
                        },
                    },
                )],
            }))
        )
    }

    #[gtest]
    fn enums() -> Result<()> {
        verify_that!(
            parse(include_str!("../../testdata/valid/enums.defcl")),
            eq(&Ok(ParsedFile {
                top_level_messages: vec![top_level_message(
                    name("config", 1, 1),
                    MessageValue {
                        fields: vec![
                            field(name("status", 2, 5), Value::Enum(scalar("ACTIVE", 2, 13))),
                            field(
                                name("mode", 3, 5),
                                Value::Enum(scalar("STATUS_ACTIVE", 3, 11)),
                            ),
                            field(name("version", 4, 5), Value::Enum(scalar("V1", 4, 14))),
                            field(name("level", 5, 5), Value::Enum(scalar("LEVEL_2", 5, 12))),
                            field(
                                name("state", 6, 5),
                                Value::Enum(scalar("UNSPECIFIED", 6, 12)),
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
            eq(&Ok(ParsedFile {
                top_level_messages: vec![top_level_message(
                    name("config", 1, 1),
                    MessageValue {
                        fields: vec![
                            field(
                                name("universe_name", 2, 5),
                                Value::String(scalar("\"example\"", 2, 20)),
                            ),
                            field(
                                name("project_id", 3, 5),
                                Value::String(scalar("\"proj1\"", 3, 17)),
                            ),
                            field(
                                name("retry_count", 4, 5),
                                Value::Integer(scalar("3", 4, 18)),
                            ),
                            field(
                                name("field2name", 5, 5),
                                Value::String(scalar("\"value\"", 5, 17)),
                            ),
                            field(
                                name("max_retries", 6, 5),
                                Value::Integer(scalar("5", 6, 18)),
                            ),
                            field(
                                name("api_v2_endpoint", 7, 5),
                                Value::String(scalar("\"http://example.com\"", 7, 22)),
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
            eq(&Ok(ParsedFile {
                top_level_messages: vec![top_level_message(
                    name("config", 1, 1),
                    MessageValue {
                        fields: vec![
                            field(name("pi", 2, 5), Value::Float(scalar("3.14", 2, 9))),
                            field(
                                name("negative_float", 3, 5),
                                Value::Float(scalar("-2.0", 3, 21)),
                            ),
                            field(name("small", 4, 5), Value::Float(scalar("0.5", 4, 12))),
                            field(
                                name("precise", 5, 5),
                                Value::Float(scalar("123.456789", 5, 14)),
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
            eq(&Ok(ParsedFile {
                top_level_messages: vec![top_level_message(
                    name("config", 1, 1),
                    MessageValue {
                        fields: vec![
                            field(name("positive", 2, 5), Value::Integer(scalar("10", 2, 15))),
                            field(name("negative", 3, 5), Value::Integer(scalar("-5", 3, 15))),
                            field(name("zero", 4, 5), Value::Integer(scalar("0", 4, 11))),
                            field(name("large", 5, 5), Value::Integer(scalar("999999", 5, 12)),),
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
            eq(&Ok(ParsedFile {
                top_level_messages: vec![top_level_message(
                    name("project", 1, 1),
                    MessageValue {
                        fields: vec![
                            field(
                                name("name", 2, 5),
                                Value::String(scalar("\"my_project\"", 2, 11)),
                            ),
                            field(
                                name("database", 3, 5),
                                Value::Message(MessageValue {
                                    fields: vec![
                                        field(
                                            name("host", 4, 9),
                                            Value::String(scalar("\"localhost\"", 4, 15)),
                                        ),
                                        field(
                                            name("port", 5, 9),
                                            Value::Integer(scalar("5432", 5, 15)),
                                        ),
                                        field(
                                            name("pool", 6, 9),
                                            Value::Message(MessageValue {
                                                fields: vec![field(
                                                    name("max_connections", 7, 13),
                                                    Value::Integer(scalar("10", 7, 30)),
                                                )],
                                                location: SourceLocation {
                                                    start: Position {
                                                        line: 6,
                                                        column: 15
                                                    },
                                                    end: Position { line: 8, column: 9 }
                                                },
                                            }),
                                        ),
                                    ],
                                    location: SourceLocation {
                                        start: Position {
                                            line: 3,
                                            column: 15
                                        },
                                        end: Position { line: 9, column: 5 }
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
            eq(&Ok(ParsedFile {
                top_level_messages: vec![top_level_message(
                    name("project", 1, 1),
                    MessageValue {
                        fields: vec![field(
                            name("dependencies", 2, 5),
                            Value::Repeated(RepeatedValue {
                                values: vec![
                                    Value::Message(MessageValue {
                                        fields: vec![field(
                                            name("universe", 3, 11),
                                            Value::String(
                                                scalar("\"mv:example.com:lib1\"", 3, 21,)
                                            ),
                                        )],
                                        location: SourceLocation {
                                            start: Position { line: 3, column: 9 },
                                            end: Position {
                                                line: 3,
                                                column: 43
                                            }
                                        },
                                    }),
                                    Value::Message(MessageValue {
                                        fields: vec![field(
                                            name("universe", 4, 11),
                                            Value::String(
                                                scalar("\"mv:example.com:lib2\"", 4, 21,)
                                            ),
                                        )],
                                        location: SourceLocation {
                                            start: Position { line: 4, column: 9 },
                                            end: Position {
                                                line: 4,
                                                column: 43
                                            }
                                        },
                                    }),
                                ],
                                location: SourceLocation {
                                    start: Position {
                                        line: 2,
                                        column: 19
                                    },
                                    end: Position { line: 5, column: 5 }
                                },
                            }),
                        )],
                        location: SourceLocation {
                            start: Position {
                                line: 1,
                                column: 10
                            },
                            end: Position { line: 6, column: 1 }
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
            eq(&Ok(ParsedFile {
                top_level_messages: vec![top_level_message(
                    name("config", 1, 1),
                    MessageValue {
                        fields: vec![
                            field(
                                name("tags", 2, 5),
                                Value::Repeated(RepeatedValue {
                                    values: vec![
                                        Value::String(scalar("\"tag1\"", 2, 12)),
                                        Value::String(scalar("\"tag2\"", 2, 20)),
                                        Value::String(scalar("\"tag3\"", 2, 28)),
                                    ],
                                    location: SourceLocation {
                                        start: Position {
                                            line: 2,
                                            column: 11
                                        },
                                        end: Position {
                                            line: 2,
                                            column: 34
                                        }
                                    },
                                }),
                            ),
                            field(
                                name("counts", 3, 5),
                                Value::Repeated(RepeatedValue {
                                    values: vec![
                                        Value::Integer(scalar("1", 3, 14)),
                                        Value::Integer(scalar("2", 3, 17)),
                                        Value::Integer(scalar("3", 3, 20)),
                                    ],
                                    location: SourceLocation {
                                        start: Position {
                                            line: 3,
                                            column: 13
                                        },
                                        end: Position {
                                            line: 3,
                                            column: 21
                                        }
                                    },
                                }),
                            ),
                            field(
                                name("values", 4, 5),
                                Value::Repeated(RepeatedValue {
                                    values: vec![
                                        Value::Float(scalar("1.5", 4, 14)),
                                        Value::Float(scalar("2.5", 4, 19)),
                                    ],
                                    location: SourceLocation {
                                        start: Position {
                                            line: 4,
                                            column: 13
                                        },
                                        end: Position {
                                            line: 4,
                                            column: 22
                                        }
                                    },
                                }),
                            ),
                            field(
                                name("modes", 5, 5),
                                Value::Repeated(RepeatedValue {
                                    values: vec![
                                        Value::Enum(scalar("ACTIVE", 5, 13)),
                                        Value::Enum(scalar("INACTIVE", 5, 21)),
                                    ],
                                    location: SourceLocation {
                                        start: Position {
                                            line: 5,
                                            column: 12
                                        },
                                        end: Position {
                                            line: 5,
                                            column: 29
                                        }
                                    },
                                }),
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
    fn strings() -> Result<()> {
        verify_that!(
            parse(include_str!("../../testdata/valid/strings.defcl")),
            eq(&Ok(ParsedFile {
                top_level_messages: vec![top_level_message(
                    name("config", 1, 1),
                    MessageValue {
                        fields: vec![
                            field(
                                name("basic", 2, 5),
                                Value::String(scalar(r#""hello""#, 2, 12)),
                            ),
                            field(
                                name("with_spaces", 3, 5),
                                Value::String(scalar(r#""hello world""#, 3, 18)),
                            ),
                            field(
                                name("with_newline", 4, 5),
                                Value::String(scalar(r#""line1\nline2""#, 4, 19)),
                            ),
                            field(
                                name("with_tab", 5, 5),
                                Value::String(scalar(r#""col1\tcol2""#, 5, 15)),
                            ),
                            field(
                                name("with_backslash", 6, 5),
                                Value::String(scalar(r#""path\\to\\file""#, 6, 21)),
                            ),
                            field(
                                name("with_quote", 7, 5),
                                Value::String(scalar(r#""say \"hello\"""#, 7, 17)),
                            ),
                            field(
                                name("with_apostrophe", 8, 5),
                                Value::String(scalar(r#""it\'s fine""#, 8, 22)),
                            ),
                            field(
                                name("with_bell", 9, 5),
                                Value::String(scalar(r#""\a""#, 9, 16)),
                            ),
                            field(
                                name("with_backspace", 10, 5),
                                Value::String(scalar(r#""\b""#, 10, 21)),
                            ),
                            field(
                                name("with_formfeed", 11, 5),
                                Value::String(scalar(r#""\f""#, 11, 20)),
                            ),
                            field(
                                name("with_return", 12, 5),
                                Value::String(scalar(r#""\r""#, 12, 18)),
                            ),
                            field(
                                name("with_vtab", 13, 5),
                                Value::String(scalar(r#""\v""#, 13, 16)),
                            ),
                            field(
                                name("with_question", 14, 5),
                                Value::String(scalar(r#""\?""#, 14, 20)),
                            ),
                            field(
                                name("octal_escape", 15, 5),
                                Value::String(scalar(r#""\101""#, 15, 19)),
                            ),
                            field(
                                name("hex_escape", 16, 5),
                                Value::String(scalar(r#""\x41""#, 16, 17)),
                            ),
                            field(
                                name("unicode_bmp", 17, 5),
                                Value::String(scalar(r#""\u0041""#, 17, 18)),
                            ),
                            field(
                                name("unicode_smp", 18, 5),
                                Value::String(scalar(r#""\U00000041""#, 18, 18)),
                            ),
                            field(
                                name("unicode_spb", 19, 5),
                                Value::String(scalar(r#""\U00100000""#, 19, 18)),
                            ),
                            field(
                                name("utf8_hex_escapes", 20, 5),
                                Value::String(scalar(r#""caf\xc3\xa9""#, 20, 23)),
                            ),
                            field(
                                name("utf8_octal_escapes", 21, 5),
                                Value::String(scalar(r#""caf\303\251""#, 21, 25)),
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

    #[gtest]
    fn whitespace() -> Result<()> {
        verify_that!(
            parse(include_str!("../../testdata/valid/whitespace.defcl")),
            eq(&Ok(ParsedFile {
                top_level_messages: vec![
                    top_level_message(
                        name("project", 1, 1),
                        MessageValue {
                            fields: vec![field(
                                name("name", 2, 5),
                                Value::String(scalar("\"test\"", 2, 11)),
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
                        name("settings", 5, 1),
                        MessageValue {
                            fields: vec![field(
                                name("level", 6, 5),
                                Value::Integer(scalar("1", 6, 12)),
                            )],
                            location: SourceLocation {
                                start: Position {
                                    line: 5,
                                    column: 11
                                },
                                end: Position { line: 7, column: 1 }
                            },
                        },
                    ),
                ],
            }))
        )
    }
}

mod valid_source {
    use super::*;

    #[gtest]
    fn columns_count_characters() -> Result<()> {
        verify_that!(
            parse("a: {\n    b: \"caf\u{e9}\" # \u{e9}\n    c: 1\n}\n"),
            eq(&Ok(ParsedFile {
                top_level_messages: vec![top_level_message(
                    name("a", 1, 1),
                    MessageValue {
                        fields: vec![
                            field(
                                name("b", 2, 5),
                                Value::String(Scalar {
                                    text: "\"caf\u{e9}\"",
                                    location: SourceLocation {
                                        start: Position { line: 2, column: 8 },
                                        end: Position {
                                            line: 2,
                                            column: 13
                                        }
                                    },
                                }),
                            ),
                            field(name("c", 3, 5), Value::Integer(scalar("1", 3, 8))),
                        ],
                        location: SourceLocation {
                            start: Position { line: 1, column: 4 },
                            end: Position { line: 4, column: 1 }
                        },
                    },
                )],
            }))
        )
    }

    #[gtest]
    fn tabs_and_carriage_returns_in_strings_and_comments() -> Result<()> {
        verify_that!(
            parse("a: { # \t\r\n    b: \"x\t\ry\"\n}\n"),
            eq(&Ok(ParsedFile {
                top_level_messages: vec![top_level_message(
                    name("a", 1, 1),
                    MessageValue {
                        fields: vec![field(
                            name("b", 2, 5),
                            Value::String(scalar("\"x\t\ry\"", 2, 8)),
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
    fn fraction_with_zero_before_last_digit() -> Result<()> {
        verify_that!(
            parse("a: {\n    b: 1.05\n}\n"),
            eq(&Ok(ParsedFile {
                top_level_messages: vec![top_level_message(
                    name("a", 1, 1),
                    MessageValue {
                        fields: vec![field(name("b", 2, 5), Value::Float(scalar("1.05", 2, 8)))],
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
            parse("a: {\n    b: \"\\0\\x4\"\n}\n"),
            eq(&Ok(ParsedFile {
                top_level_messages: vec![top_level_message(
                    name("a", 1, 1),
                    MessageValue {
                        fields: vec![field(
                            name("b", 2, 5),
                            Value::String(scalar("\"\\0\\x4\"", 2, 8)),
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
    fn no_whitespace_inside_values() -> Result<()> {
        verify_that!(
            parse("a: {b:[{c:1},2.5]}\n"),
            eq(&Ok(ParsedFile {
                top_level_messages: vec![top_level_message(
                    name("a", 1, 1),
                    MessageValue {
                        fields: vec![field(
                            name("b", 1, 5),
                            Value::Repeated(RepeatedValue {
                                values: vec![
                                    Value::Message(MessageValue {
                                        fields: vec![field(
                                            name("c", 1, 9),
                                            Value::Integer(scalar("1", 1, 11)),
                                        )],
                                        location: SourceLocation {
                                            start: Position { line: 1, column: 8 },
                                            end: Position {
                                                line: 1,
                                                column: 12
                                            }
                                        },
                                    }),
                                    Value::Float(scalar("2.5", 1, 14)),
                                ],
                                location: SourceLocation {
                                    start: Position { line: 1, column: 7 },
                                    end: Position {
                                        line: 1,
                                        column: 17
                                    }
                                },
                            }),
                        )],
                        location: SourceLocation {
                            start: Position { line: 1, column: 4 },
                            end: Position {
                                line: 1,
                                column: 18
                            }
                        },
                    },
                )],
            }))
        )
    }

    #[gtest]
    fn comment_between_value_and_close_bracket() -> Result<()> {
        verify_that!(
            parse("a: {\n    b: [1 # one\n    ]\n}\n"),
            eq(&Ok(ParsedFile {
                top_level_messages: vec![top_level_message(
                    name("a", 1, 1),
                    MessageValue {
                        fields: vec![field(
                            name("b", 2, 5),
                            Value::Repeated(RepeatedValue {
                                values: vec![Value::Integer(scalar("1", 2, 9))],
                                location: SourceLocation {
                                    start: Position { line: 2, column: 8 },
                                    end: Position { line: 3, column: 5 }
                                },
                            }),
                        )],
                        location: SourceLocation {
                            start: Position { line: 1, column: 4 },
                            end: Position { line: 4, column: 1 }
                        },
                    },
                )],
            }))
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::BooleanNotSupported,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 14
                    },
                    end: Position {
                        line: 2,
                        column: 18
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::BooleanNotSupported,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 14
                    },
                    end: Position {
                        line: 2,
                        column: 17
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidEnumCase,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 13
                    },
                    end: Position {
                        line: 2,
                        column: 18
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidEnumCase,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 13
                    },
                    end: Position {
                        line: 2,
                        column: 18
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidFieldName,
                location: SourceLocation {
                    start: Position { line: 2, column: 5 },
                    end: Position {
                        line: 2,
                        column: 17
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidFieldName,
                location: SourceLocation {
                    start: Position { line: 2, column: 5 },
                    end: Position {
                        line: 2,
                        column: 17
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidFieldName,
                location: SourceLocation {
                    start: Position { line: 2, column: 5 },
                    end: Position {
                        line: 2,
                        column: 12
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidFieldName,
                location: SourceLocation {
                    start: Position { line: 2, column: 5 },
                    end: Position {
                        line: 2,
                        column: 18
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidFieldName,
                location: SourceLocation {
                    start: Position { line: 2, column: 5 },
                    end: Position {
                        line: 2,
                        column: 17
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidFieldName,
                location: SourceLocation {
                    start: Position { line: 2, column: 5 },
                    end: Position {
                        line: 2,
                        column: 18
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidFieldName,
                location: SourceLocation {
                    start: Position { line: 2, column: 5 },
                    end: Position {
                        line: 2,
                        column: 12
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidFieldName,
                location: SourceLocation {
                    start: Position { line: 2, column: 5 },
                    end: Position {
                        line: 2,
                        column: 16
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
            eq(&Err(SyntaxError {
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
            eq(&Err(SyntaxError {
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
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/file_format/no_trailing_newline.defcl"
            )),
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::MissingTrailingNewline,
                location: SourceLocation {
                    start: Position { line: 3, column: 1 },
                    end: Position { line: 3, column: 1 }
                }
            }))
        )
    }

    #[gtest]
    fn no_trailing_newline_after_comment() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/file_format/no_trailing_newline_after_comment.defcl"
            )),
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::MissingTrailingNewline,
                location: SourceLocation {
                    start: Position { line: 2, column: 5 },
                    end: Position { line: 2, column: 5 }
                }
            }))
        )
    }

    #[gtest]
    fn empty_file() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/file_format/empty_file.defcl"
            )),
            eq(&Err(SyntaxError {
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
            eq(&Err(SyntaxError {
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
            eq(&Err(SyntaxError {
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::AngleBracketsNotAllowed,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 13
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
    fn quoted_field_name() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/messages/quoted_field_name.defcl"
            )),
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::ExpectedFieldNameOrCloseBrace,
                location: SourceLocation {
                    start: Position { line: 2, column: 5 },
                    end: Position { line: 2, column: 5 }
                }
            }))
        )
    }

    #[gtest]
    fn fields_without_whitespace_between_them() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/messages/fields_without_whitespace_between_them.defcl"
            )),
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::MissingWhitespace,
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
    fn top_level_messages_without_whitespace_between_them() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/messages/top_level_messages_without_whitespace_between_them.defcl"
            )),
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::MissingWhitespace,
                location: SourceLocation {
                    start: Position { line: 1, column: 6 },
                    end: Position { line: 1, column: 6 }
                }
            }))
        )
    }

    #[gtest]
    fn unclosed_message() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/messages/unclosed_message.defcl"
            )),
            eq(&Err(SyntaxError {
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidNumberFormat,
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

    #[gtest]
    fn octal() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/numbers/octal.defcl"
            )),
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidNumberFormat,
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

    #[gtest]
    fn scientific_int() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/numbers/scientific_int.defcl"
            )),
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidNumberFormat,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 12
                    },
                    end: Position {
                        line: 2,
                        column: 14
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidNumberFormat,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 12
                    },
                    end: Position {
                        line: 2,
                        column: 17
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidNumberFormat,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 12
                    },
                    end: Position {
                        line: 2,
                        column: 14
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidNumberFormat,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 12
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
    fn trailing_decimal() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/numbers/trailing_decimal.defcl"
            )),
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidNumberFormat,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 12
                    },
                    end: Position {
                        line: 2,
                        column: 14
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::NegativeZero,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 12
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
    fn negative_zero_float() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/numbers/negative_zero_float.defcl"
            )),
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::NegativeZero,
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

    #[gtest]
    fn plus_sign() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/numbers/plus_sign.defcl"
            )),
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidNumberFormat,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 12
                    },
                    end: Position {
                        line: 2,
                        column: 14
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidNumberFormat,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 12
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
    fn type_suffix_f() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/numbers/type_suffix_f.defcl"
            )),
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidNumberFormat,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 12
                    },
                    end: Position {
                        line: 2,
                        column: 14
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidNumberFormat,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 12
                    },
                    end: Position {
                        line: 2,
                        column: 14
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidNumberFormat,
                location: SourceLocation {
                    start: Position { line: 2, column: 8 },
                    end: Position {
                        line: 2,
                        column: 11
                    }
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidNumberFormat,
                location: SourceLocation {
                    start: Position { line: 2, column: 8 },
                    end: Position {
                        line: 2,
                        column: 11
                    }
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidNumberFormat,
                location: SourceLocation {
                    start: Position { line: 2, column: 8 },
                    end: Position {
                        line: 2,
                        column: 11
                    }
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidNumberFormat,
                location: SourceLocation {
                    start: Position { line: 2, column: 8 },
                    end: Position {
                        line: 2,
                        column: 11
                    }
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidNumberFormat,
                location: SourceLocation {
                    start: Position { line: 2, column: 8 },
                    end: Position {
                        line: 2,
                        column: 11
                    }
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidNumberFormat,
                location: SourceLocation {
                    start: Position { line: 2, column: 8 },
                    end: Position {
                        line: 2,
                        column: 13
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::UnexpectedCharacter { character: '@' },
                location: SourceLocation {
                    start: Position { line: 2, column: 8 },
                    end: Position { line: 2, column: 8 }
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::UnexpectedCharacter {
                    character: '\u{e9}'
                },
                location: SourceLocation {
                    start: Position { line: 2, column: 8 },
                    end: Position { line: 2, column: 8 }
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::UnexpectedCharacter { character: '\0' },
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
            }))
        )
    }

    #[gtest]
    fn nul_in_comment() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/characters/nul_in_comment.defcl"
            )),
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::UnexpectedCharacter { character: '\0' },
                location: SourceLocation {
                    start: Position {
                        line: 1,
                        column: 10
                    },
                    end: Position {
                        line: 1,
                        column: 10
                    }
                },
            }))
        )
    }

    #[gtest]
    fn nul_in_comment_at_start_of_file() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/characters/nul_in_comment_at_start_of_file.defcl"
            )),
            eq(&Err(SyntaxError {
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
            eq(&Err(SyntaxError {
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::UnexpectedCharacter { character: '\0' },
                location: SourceLocation {
                    start: Position { line: 2, column: 9 },
                    end: Position { line: 2, column: 9 }
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
            eq(&Err(SyntaxError {
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::UnexpectedCharacter { character: '\0' },
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
            }))
        )
    }

    #[gtest]
    fn nul_in_comment_at_start_of_repeated_value() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/characters/nul_in_comment_at_start_of_repeated_value.defcl"
            )),
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::UnexpectedCharacter { character: '\0' },
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
            }))
        )
    }

    #[gtest]
    fn nul_in_comment_after_comma() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/characters/nul_in_comment_after_comma.defcl"
            )),
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::UnexpectedCharacter { character: '\0' },
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 13
                    },
                    end: Position {
                        line: 2,
                        column: 13
                    }
                },
            }))
        )
    }

    #[gtest]
    fn nul_in_comment_after_repeated_element() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/characters/nul_in_comment_after_repeated_element.defcl"
            )),
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::UnexpectedCharacter { character: '\0' },
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 12
                    },
                    end: Position {
                        line: 2,
                        column: 12
                    }
                },
            }))
        )
    }
    #[gtest]
    fn nul_in_comment_after_field_name() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/characters/nul_in_comment_after_field_name.defcl"
            )),
            eq(&Err(SyntaxError {
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidSeparator,
                location: SourceLocation {
                    start: Position { line: 2, column: 9 },
                    end: Position { line: 2, column: 9 }
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidSeparator,
                location: SourceLocation {
                    start: Position { line: 2, column: 9 },
                    end: Position { line: 2, column: 9 }
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidSeparator,
                location: SourceLocation {
                    start: Position { line: 1, column: 6 },
                    end: Position { line: 1, column: 6 }
                }
            }))
        )
    }

    #[gtest]
    fn missing_colon() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/separators/missing_colon.defcl"
            )),
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::MissingColon,
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
    fn field_named_f_missing_colon() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/separators/field_named_f_missing_colon.defcl"
            )),
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::MissingColon,
                location: SourceLocation {
                    start: Position { line: 2, column: 6 },
                    end: Position { line: 2, column: 6 }
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
            eq(&Err(SyntaxError {
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
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/separators/whitespace_before_colon.defcl"
            )),
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::WhitespaceBeforeColon,
                location: SourceLocation {
                    start: Position { line: 2, column: 6 },
                    end: Position { line: 2, column: 6 }
                }
            }))
        )
    }

    #[gtest]
    fn comment_before_top_level_colon() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/separators/comment_before_top_level_colon.defcl"
            )),
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::WhitespaceBeforeColon,
                location: SourceLocation {
                    start: Position { line: 1, column: 2 },
                    end: Position { line: 1, column: 6 }
                }
            }))
        )
    }

    #[gtest]
    fn semicolon() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/separators/semicolon.defcl"
            )),
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidSeparator,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 18
                    },
                    end: Position {
                        line: 2,
                        column: 18
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::ExpectedCommaOrCloseBracket,
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
    fn whitespace_before_comma() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/repeated_values/whitespace_before_comma.defcl"
            )),
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::WhitespaceBeforeComma,
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
    fn trailing_comma() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/repeated_values/trailing_comma.defcl"
            )),
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::ExpectedValue,
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
    fn unclosed_empty_repeated_value() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/repeated_values/unclosed_empty_repeated_value.defcl"
            )),
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::UnclosedRepeatedValue,
                location: SourceLocation {
                    start: Position { line: 2, column: 8 },
                    end: Position { line: 2, column: 8 }
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::UnclosedRepeatedValue,
                location: SourceLocation {
                    start: Position { line: 2, column: 8 },
                    end: Position { line: 2, column: 8 }
                }
            }))
        )
    }

    #[gtest]
    fn semicolon_between_values() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/repeated_values/semicolon_between_values.defcl"
            )),
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidSeparator,
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
    fn repeated_value_in_repeated_value() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/repeated_values/repeated_value_in_repeated_value.defcl"
            )),
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::RepeatedValueInRepeatedValue,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 17
                    },
                    end: Position {
                        line: 2,
                        column: 17
                    }
                }
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::ExpectedValue,
                location: SourceLocation {
                    start: Position { line: 2, column: 8 },
                    end: Position { line: 2, column: 8 }
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::ExpectedValue,
                location: SourceLocation {
                    start: Position { line: 2, column: 7 },
                    end: Position { line: 2, column: 7 }
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::UnterminatedString,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 12
                    },
                    end: Position {
                        line: 2,
                        column: 17
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::UnterminatedString,
                location: SourceLocation {
                    start: Position { line: 2, column: 8 },
                    end: Position { line: 2, column: 9 }
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::UnterminatedString,
                location: SourceLocation {
                    start: Position { line: 2, column: 8 },
                    end: Position {
                        line: 2,
                        column: 10
                    }
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::UnterminatedString,
                location: SourceLocation {
                    start: Position { line: 2, column: 8 },
                    end: Position {
                        line: 2,
                        column: 10
                    }
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::SingleQuotesNotAllowed,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 12
                    },
                    end: Position {
                        line: 2,
                        column: 18
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::SingleQuotesNotAllowed,
                location: SourceLocation {
                    start: Position { line: 2, column: 8 },
                    end: Position { line: 2, column: 8 }
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidUtf8,
                location: SourceLocation {
                    start: Position { line: 2, column: 9 },
                    end: Position {
                        line: 2,
                        column: 12
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidUtf8,
                location: SourceLocation {
                    start: Position { line: 2, column: 9 },
                    end: Position {
                        line: 2,
                        column: 12
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidUtf8,
                location: SourceLocation {
                    start: Position {
                        line: 2,
                        column: 10
                    },
                    end: Position {
                        line: 2,
                        column: 17
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidUtf8,
                location: SourceLocation {
                    start: Position { line: 2, column: 9 },
                    end: Position {
                        line: 2,
                        column: 12
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidUtf8,
                location: SourceLocation {
                    start: Position { line: 2, column: 9 },
                    end: Position {
                        line: 2,
                        column: 16
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::SurrogateEscape,
                location: SourceLocation {
                    start: Position { line: 2, column: 9 },
                    end: Position {
                        line: 2,
                        column: 14
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidEscapeSequence,
                location: SourceLocation {
                    start: Position { line: 2, column: 9 },
                    end: Position {
                        line: 2,
                        column: 12
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::UnterminatedString,
                location: SourceLocation {
                    start: Position { line: 2, column: 8 },
                    end: Position {
                        line: 2,
                        column: 13
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidEscapeSequence,
                location: SourceLocation {
                    start: Position { line: 2, column: 9 },
                    end: Position {
                        line: 2,
                        column: 10
                    }
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidEscapeSequence,
                location: SourceLocation {
                    start: Position { line: 2, column: 9 },
                    end: Position {
                        line: 2,
                        column: 10
                    }
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidEscapeSequence,
                location: SourceLocation {
                    start: Position { line: 2, column: 9 },
                    end: Position {
                        line: 2,
                        column: 10
                    }
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidEscapeSequence,
                location: SourceLocation {
                    start: Position { line: 2, column: 9 },
                    end: Position {
                        line: 2,
                        column: 12
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidEscapeSequence,
                location: SourceLocation {
                    start: Position { line: 2, column: 9 },
                    end: Position {
                        line: 2,
                        column: 18
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::InvalidEscapeSequence,
                location: SourceLocation {
                    start: Position { line: 2, column: 9 },
                    end: Position {
                        line: 2,
                        column: 17
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
            eq(&Err(SyntaxError {
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
            eq(&Err(SyntaxError {
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
            eq(&Err(SyntaxError {
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::ScalarAtToplevel,
                location: SourceLocation {
                    start: Position { line: 1, column: 4 },
                    end: Position { line: 1, column: 6 }
                }
            }))
        )
    }
    #[gtest]
    fn no_space_after_top_level_colon() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/toplevel/no_space_after_top_level_colon.defcl"
            )),
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::MissingSpaceAfterColon,
                location: SourceLocation {
                    start: Position { line: 1, column: 3 },
                    end: Position { line: 1, column: 3 }
                }
            }))
        )
    }

    #[gtest]
    fn line_feed_after_top_level_colon() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/toplevel/line_feed_after_top_level_colon.defcl"
            )),
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::MissingSpaceAfterColon,
                location: SourceLocation {
                    start: Position { line: 1, column: 3 },
                    end: Position { line: 1, column: 3 }
                }
            }))
        )
    }

    #[gtest]
    fn end_of_source_after_top_level_colon() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/toplevel/end_of_source_after_top_level_colon.defcl"
            )),
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::MissingSpaceAfterColon,
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
            eq(&Err(SyntaxError {
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
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/toplevel/two_spaces_after_top_level_colon.defcl"
            )),
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::ExtraWhitespaceAfterColon,
                location: SourceLocation {
                    start: Position { line: 1, column: 4 },
                    end: Position { line: 1, column: 4 }
                }
            }))
        )
    }

    #[gtest]
    fn trailing_space_after_top_level_colon() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/toplevel/trailing_space_after_top_level_colon.defcl"
            )),
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::ExtraWhitespaceAfterColon,
                location: SourceLocation {
                    start: Position { line: 1, column: 4 },
                    end: Position { line: 1, column: 4 }
                }
            }))
        )
    }

    #[gtest]
    fn comment_after_space_after_top_level_colon() -> Result<()> {
        verify_that!(
            parse(include_str!(
                "../../testdata/invalid/syntax/toplevel/comment_after_space_after_top_level_colon.defcl"
            )),
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::ExtraWhitespaceAfterColon,
                location: SourceLocation {
                    start: Position { line: 1, column: 4 },
                    end: Position { line: 1, column: 7 }
                }
            }))
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
            eq(&Err(SyntaxError {
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
            eq(&Err(SyntaxError {
                kind: SyntaxErrorKind::TabNotAllowed,
                location: SourceLocation {
                    start: Position { line: 2, column: 1 },
                    end: Position { line: 2, column: 1 }
                }
            }))
        )
    }
}
