//! The checks of a DCL file's syntax tree against its schema.

use crate::schema::{MessageType, Schema, SchemaField};
use crate::semantic_error::SemanticError;
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
    let mut written_names =
        FxHashSet::with_capacity_and_hasher(file.top_level_messages.len(), FxBuildHasher);
    for top_level_message in &file.top_level_messages {
        let Some(schema_field) = find_field(
            schema,
            top_level_message_type,
            &top_level_message.name,
            &mut written_names,
            &mut errors,
        ) else {
            continue;
        };
        // The top-level message's field is not a message field.
        let Some(message_type) = schema_field.message_type else {
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
    let mut written_names = FxHashSet::with_capacity_and_hasher(fields.len(), FxBuildHasher);
    for field in fields {
        if let Some(schema_field) = find_field(
            schema,
            message_type,
            &field.name,
            &mut written_names,
            errors,
        ) {
            check_field(schema, field, &schema_field, errors);
        }
    }
}

/// Returns the field of `message_type` that `name` names, if it has one, and
/// adds `name` to `written_names`, the field names written so far in the
/// message value.
fn find_field<'schema, 'source>(
    schema: &'schema Schema,
    message_type: &'schema MessageType,
    name: &FieldName<'source>,
    written_names: &mut FxHashSet<&'source str>,
    errors: &mut Vec<SemanticError>,
) -> Option<SchemaField<'schema>> {
    // The message type has no field with the name.
    let Some(schema_field) = schema.field(message_type, name.text) else {
        errors.push(unknown_field_name(name, message_type));
        return None;
    };
    // The message value already has a field with this name.
    if !written_names.insert(name.text) {
        errors.push(field_written_twice(name));
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
    match value {
        // The enum field's value is an integer.
        Value::Integer(integer) if schema_field.is_enum() => {
            errors.push(integer_enum(field, integer.location));
        }
        Value::Message(message) => {
            // The field is not a message field.
            let Some(message_type) = schema_field.message_type else {
                errors.push(message_value_for_scalar_field(
                    &field.name,
                    message.location,
                ));
                return;
            };
            check_fields(schema, message_type, &message.fields, errors);
        }
        // The message field's value is a string, number or enum value.
        Value::String(scalar)
        | Value::Integer(scalar)
        | Value::Float(scalar)
        | Value::Enum(scalar)
            if schema_field.message_type.is_some() =>
        {
            errors.push(scalar_for_message_field(field, scalar.location));
        }
        _ => {}
    }
}

// The functions that only run on an error path.

#[cold]
#[inline(never)]
fn field_written_twice(name: &FieldName) -> SemanticError {
    SemanticError::FieldWrittenTwice {
        location: name.location,
        field_name: name.text.to_owned(),
    }
}

#[cold]
#[inline(never)]
fn unknown_field_name(name: &FieldName, message_type: &MessageType) -> SemanticError {
    SemanticError::UnknownFieldName {
        location: name.location,
        field_name: name.text.to_owned(),
        message_type: message_type.full_name.clone(),
    }
}

#[cold]
#[inline(never)]
fn repeated_field_without_brackets(field: &Field) -> SemanticError {
    SemanticError::RepeatedFieldWithoutBrackets {
        location: field.value.location(),
        field_name: field.name.text.to_owned(),
    }
}

/// The error for the repeated value at `location`, which is the value of
/// `field`, a field that is not repeated.
#[cold]
#[inline(never)]
fn non_repeated_field_with_brackets(field: &Field, location: SourceLocation) -> SemanticError {
    SemanticError::NonRepeatedFieldWithBrackets {
        location,
        field_name: field.name.text.to_owned(),
    }
}

/// The error for the message value at `location`, which is the value of the
/// field named `name`.
#[cold]
#[inline(never)]
fn message_value_for_scalar_field(name: &FieldName, location: SourceLocation) -> SemanticError {
    SemanticError::MessageValueForScalarField {
        location,
        field_name: name.text.to_owned(),
    }
}

/// The error for the string, number or enum value at `location`, which is the
/// value of `field`, a message field.
#[cold]
#[inline(never)]
fn scalar_for_message_field(field: &Field, location: SourceLocation) -> SemanticError {
    SemanticError::ScalarForMessageField {
        location,
        field_name: field.name.text.to_owned(),
    }
}

/// The error for the integer at `location`, which is the value of `field`, an
/// enum field.
#[cold]
#[inline(never)]
fn integer_enum(field: &Field, location: SourceLocation) -> SemanticError {
    SemanticError::IntegerEnum {
        location,
        field_name: field.name.text.to_owned(),
    }
}
