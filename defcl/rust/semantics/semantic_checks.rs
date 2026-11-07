//! The checks of a DCL file's syntax tree against its schema.

use crate::schema::{
    EnumType, FloatFieldType, IntegerFieldType, MessageType, Schema, SchemaField, ValueType,
};
use crate::semantic_error::{SemanticError, SemanticErrorKind};
use defcl_parser::{Field, FieldName, ParsedFile, SourceLocation, Value};
use rustc_hash::{FxBuildHasher, FxHashSet};

/// Checks the syntax tree of a DCL file against `schema`.
///
/// # Errors
///
/// Returns every error it finds, in source order. A value that an error leaves
/// without a type to check against is not checked further.
pub fn check_semantics(file: &ParsedFile, schema: &Schema) -> Result<(), Vec<SemanticError>> {
    let mut errors = Vec::new();
    let top_level_message_type = schema.top_level_message_type();
    let mut written_fields = WrittenFields::new(file.top_level_messages.len());
    for top_level_message in &file.top_level_messages {
        let Some(schema_field) = find_field(
            schema,
            top_level_message_type,
            &top_level_message.name,
            &mut written_fields,
            &mut errors,
        ) else {
            continue;
        };
        // The top-level message's field is not a message field.
        let ValueType::Message(message_type) = schema_field.value_type else {
            errors.push(message_value_for_scalar_field(
                &top_level_message.name,
                top_level_message.value.location,
            ));
            continue;
        };
        check_fields(
            schema,
            message_type,
            &top_level_message.value.fields,
            &mut errors,
        );
    }
    if errors.is_empty() {
        return Ok(());
    }
    Err(errors)
}

fn check_fields(
    schema: &Schema,
    message_type: &MessageType,
    fields: &[Field],
    errors: &mut Vec<SemanticError>,
) {
    let mut written_fields = WrittenFields::new(fields.len());
    for field in fields {
        if let Some(schema_field) = find_field(
            schema,
            message_type,
            &field.name,
            &mut written_fields,
            errors,
        ) {
            check_field(schema, field, &schema_field, errors);
        }
    }
}

/// The fields written so far in a message value, or in the file's top-level
/// messages.
struct WrittenFields<'source> {
    names: FxHashSet<&'source str>,
    /// The index in the message type's descriptor of each oneof that has a
    /// field written.
    oneofs: Vec<i32>,
}

impl WrittenFields<'_> {
    fn new(capacity: usize) -> Self {
        Self {
            names: FxHashSet::with_capacity_and_hasher(capacity, FxBuildHasher),
            oneofs: Vec::new(),
        }
    }
}

/// Returns the field of `message_type` that `name` names, if it has one, and
/// adds the field to `written_fields`.
fn find_field<'schema, 'source>(
    schema: &'schema Schema,
    message_type: &'schema MessageType,
    name: &FieldName<'source>,
    written_fields: &mut WrittenFields<'source>,
    errors: &mut Vec<SemanticError>,
) -> Option<SchemaField<'schema>> {
    // The message type has no field with the name.
    let Some(schema_field) = schema.field(message_type, name.text) else {
        errors.push(unknown_field_name(name, message_type));
        return None;
    };
    // The message value already has a field with this name.
    if !written_fields.names.insert(name.text) {
        errors.push(field_written_twice(name));
        return Some(schema_field);
    }
    if let Some(oneof) = schema_field.descriptor.oneof_index {
        // The message value already has another field of the field's oneof.
        if written_fields.oneofs.contains(&oneof) {
            errors.push(second_field_of_oneof(name, message_type, oneof));
        } else {
            written_fields.oneofs.push(oneof);
        }
    }
    Some(schema_field)
}

fn check_field(
    schema: &Schema,
    field: &Field,
    schema_field: &SchemaField,
    errors: &mut Vec<SemanticError>,
) {
    if !schema_field.is_repeated() {
        // The non-repeated field's value is in brackets.
        if let Value::Repeated(repeated) = &field.value {
            errors.push(non_repeated_field_with_brackets(field, repeated.location));
            return;
        }
        check_value(schema, field, schema_field, &field.value, errors);
        return;
    }
    // The repeated field's value is not in brackets.
    let Value::Repeated(repeated) = &field.value else {
        errors.push(repeated_field_without_brackets(field));
        return;
    };
    for value in &repeated.values {
        check_value(schema, field, schema_field, value, errors);
    }
}

/// Checks `value`, which is `field`'s value or an element of `field`'s
/// repeated value.
fn check_value(
    schema: &Schema,
    field: &Field,
    schema_field: &SchemaField,
    value: &Value,
    errors: &mut Vec<SemanticError>,
) {
    let kind = match (&schema_field.value_type, value) {
        // The parser does not allow a repeated value as an element, and
        // check_field checks a field's repeated value element by element.
        (_, Value::Repeated(_)) => unreachable!("a repeated value is checked by its elements"),
        (ValueType::Message(message_type), Value::Message(message)) => {
            check_fields(schema, message_type, &message.fields, errors);
            return;
        }
        (ValueType::String, Value::String(_)) => return,
        (ValueType::Integer(field_type), Value::Integer(integer)) => {
            // The integer is outside the field type's range.
            if !is_integer_in_range(integer.text, *field_type) {
                errors.push(value_error(
                    SemanticErrorKind::IntegerOutOfRange {
                        field_type: *field_type,
                    },
                    field,
                    integer.location,
                ));
            }
            return;
        }
        (ValueType::Float(field_type), Value::Float(float)) => {
            // The number rounds to infinity in the field's type.
            if !is_float_in_range(float.text, *field_type) {
                errors.push(value_error(
                    SemanticErrorKind::FloatOutOfRange {
                        field_type: *field_type,
                    },
                    field,
                    float.location,
                ));
            }
            return;
        }
        (ValueType::Enum(enum_type), Value::Enum(name)) => {
            // The enum type has no value with the name.
            if !enum_type.has_value(name.text) {
                errors.push(unknown_enum_value(field, enum_type, name.location));
            }
            return;
        }
        // The message field's value is a string, number or enum value.
        (ValueType::Message(_), _) => SemanticErrorKind::ScalarForMessageField,
        // The field is not a message field.
        (_, Value::Message(_)) => SemanticErrorKind::MessageValueForScalarField,
        // The enum field's value is an integer.
        (ValueType::Enum(_), Value::Integer(_)) => SemanticErrorKind::IntegerEnum,
        (ValueType::Enum(_), _) => SemanticErrorKind::NonEnumValueForEnumField,
        (ValueType::String, _) => SemanticErrorKind::NonStringForStringField,
        (ValueType::Integer(_), _) => SemanticErrorKind::NonIntegerForIntegerField,
        (ValueType::Float(_), _) => SemanticErrorKind::NonFloatForFloatField,
    };
    errors.push(value_error(kind, field, value.location()));
}

/// Whether the integer whose source text is `text` is within the range of
/// `field_type`.
fn is_integer_in_range(text: &str, field_type: IntegerFieldType) -> bool {
    // An integer too large for an i128 is too large for every field type.
    text.parse::<i128>()
        .is_ok_and(|value| (field_type.minimum()..=field_type.maximum()).contains(&value))
}

/// Whether the floating-point number whose source text is `text` is finite
/// once rounded to `field_type`.
fn is_float_in_range(text: &str, field_type: FloatFieldType) -> bool {
    match field_type {
        FloatFieldType::Float => text.parse::<f32>().is_ok_and(f32::is_finite),
        FloatFieldType::Double => text.parse::<f64>().is_ok_and(f64::is_finite),
    }
}

// The functions that only run on an error path.

#[cold]
#[inline(never)]
fn field_written_twice(name: &FieldName) -> SemanticError {
    SemanticError {
        kind: SemanticErrorKind::FieldWrittenTwice,
        location: name.location,
        field_name: name.text.to_owned(),
    }
}

/// The error for the field named `name`, a field of the oneof at index `oneof`
/// in `message_type`'s descriptor, which already has another field written.
#[cold]
#[inline(never)]
fn second_field_of_oneof(
    name: &FieldName,
    message_type: &MessageType,
    oneof: i32,
) -> SemanticError {
    #[expect(clippy::cast_sign_loss, reason = "a oneof's index is never negative")]
    let oneof_name = message_type.descriptor.oneof_decl[oneof as usize].name();
    SemanticError {
        kind: SemanticErrorKind::SecondFieldOfOneof {
            oneof: format!("{}.{oneof_name}", message_type.full_name),
        },
        location: name.location,
        field_name: name.text.to_owned(),
    }
}

#[cold]
#[inline(never)]
fn unknown_field_name(name: &FieldName, message_type: &MessageType) -> SemanticError {
    SemanticError {
        kind: SemanticErrorKind::UnknownFieldName {
            message_type: message_type.full_name.clone(),
        },
        location: name.location,
        field_name: name.text.to_owned(),
    }
}

#[cold]
#[inline(never)]
fn repeated_field_without_brackets(field: &Field) -> SemanticError {
    SemanticError {
        kind: SemanticErrorKind::RepeatedFieldWithoutBrackets,
        location: field.value.location(),
        field_name: field.name.text.to_owned(),
    }
}

/// The error for the repeated value at `location`, which is the value of
/// `field`, a field that is not repeated.
#[cold]
#[inline(never)]
fn non_repeated_field_with_brackets(field: &Field, location: SourceLocation) -> SemanticError {
    SemanticError {
        kind: SemanticErrorKind::NonRepeatedFieldWithBrackets,
        location,
        field_name: field.name.text.to_owned(),
    }
}

/// The error for the message value at `location`, which is the value of the
/// field named `name`.
#[cold]
#[inline(never)]
fn message_value_for_scalar_field(name: &FieldName, location: SourceLocation) -> SemanticError {
    SemanticError {
        kind: SemanticErrorKind::MessageValueForScalarField,
        location,
        field_name: name.text.to_owned(),
    }
}

/// The error of the kind `kind` for the value at `location`, which is the
/// value of `field` or an element of it.
#[cold]
#[inline(never)]
fn value_error(kind: SemanticErrorKind, field: &Field, location: SourceLocation) -> SemanticError {
    SemanticError {
        kind,
        location,
        field_name: field.name.text.to_owned(),
    }
}

/// The error for the enum value at `location`, which is the value of
/// `field` or an element of it, and whose name `enum_type` has no value for.
#[cold]
#[inline(never)]
fn unknown_enum_value(
    field: &Field,
    enum_type: &EnumType,
    location: SourceLocation,
) -> SemanticError {
    SemanticError {
        kind: SemanticErrorKind::UnknownEnumValue {
            enum_type: enum_type.full_name.clone(),
        },
        location,
        field_name: field.name.text.to_owned(),
    }
}
