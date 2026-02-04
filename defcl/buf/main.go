// Package main implements a buf plugin for DCL-specific proto schema validation.
package main

import (
	"context"
	"strings"
	"unicode"

	"buf.build/go/bufplugin/check"
	"google.golang.org/protobuf/reflect/protoreflect"
)

func main() {
	check.Main(spec)
}

// spec defines all the lint rules for this plugin.
var spec = &check.Spec{
	Rules: []*check.RuleSpec{
		editionRule,
		noBoolRule,
		noBytesRule,
		noAnyRule,
		enumInMessageRule,
		enumZeroUnspecifiedRule,
		fieldNameUnderscoreRule,
		timeFieldSuffixRule,
	},
}

// Rule specifications

// TODO(https://github.com/bufbuild/buf/issues/4193): Upgrade to edition 2024 when buf supports it
var editionRule = &check.RuleSpec{
	ID:      "DEFCL_EDITION",
	Default: true,
	Purpose: "Checks that all files use the right edition.",
	Type:    check.RuleTypeLint,
	Handler: check.RuleHandlerFunc(checkEdition),
}

var noBoolRule = &check.RuleSpec{
	ID:      "DEFCL_NO_BOOL",
	Default: true,
	Purpose: "Checks that no fields use the bool type.",
	Type:    check.RuleTypeLint,
	Handler: check.RuleHandlerFunc(checkNoBool),
}

var noBytesRule = &check.RuleSpec{
	ID:      "DEFCL_NO_BYTES",
	Default: true,
	Purpose: "Checks that no fields use the bytes type.",
	Type:    check.RuleTypeLint,
	Handler: check.RuleHandlerFunc(checkNoBytes),
}

var noAnyRule = &check.RuleSpec{
	ID:      "DEFCL_NO_ANY",
	Default: true,
	Purpose: "Checks that no fields use google.protobuf.Any.",
	Type:    check.RuleTypeLint,
	Handler: check.RuleHandlerFunc(checkNoAny),
}

var enumInMessageRule = &check.RuleSpec{
	ID:      "DEFCL_ENUM_IN_MESSAGE",
	Default: true,
	Purpose: "Checks that enums are defined inside messages.",
	Type:    check.RuleTypeLint,
	Handler: check.RuleHandlerFunc(checkEnumInMessage),
}

var enumZeroUnspecifiedRule = &check.RuleSpec{
	ID:      "DEFCL_ENUM_ZERO_UNSPECIFIED",
	Default: true,
	Purpose: "Checks that enum zero values are exactly UNSPECIFIED.",
	Type:    check.RuleTypeLint,
	Handler: check.RuleHandlerFunc(checkEnumZeroUnspecified),
}

var fieldNameUnderscoreRule = &check.RuleSpec{
	ID:      "DEFCL_FIELD_NAME_UNDERSCORE",
	Default: true,
	Purpose: "Checks that underscores in field names are followed by letters and fields don't end with underscores.",
	Type:    check.RuleTypeLint,
	Handler: check.RuleHandlerFunc(checkFieldNameUnderscore),
}

var timeFieldSuffixRule = &check.RuleSpec{
	ID:      "DEFCL_TIME_FIELD_SUFFIX",
	Default: true,
	Purpose: "Checks that time-related fields have correct suffixes.",
	Type:    check.RuleTypeLint,
	Handler: check.RuleHandlerFunc(checkTimeFieldSuffix),
}

// checkEdition verifies that files use edition 2023.
// TODO(https://github.com/bufbuild/buf/issues/4193): Upgrade to edition 2024 when buf supports it
func checkEdition(_ context.Context, responseWriter check.ResponseWriter, request check.Request) error {
	for _, file := range request.FileDescriptors() {
		fd := file.ProtoreflectFileDescriptor()
		syntax := fd.Syntax()
		if syntax != protoreflect.Editions {
			responseWriter.AddAnnotation(
				check.WithMessagef("file must use edition 2023, got %v", syntax),
				check.WithDescriptor(fd),
			)
		}
	}
	return nil
}

// checkNoBool verifies that no fields use the bool type.
func checkNoBool(_ context.Context, responseWriter check.ResponseWriter, request check.Request) error {
	for _, file := range request.FileDescriptors() {
		fd := file.ProtoreflectFileDescriptor()
		checkMessagesForBool(fd.Messages(), responseWriter)
	}
	return nil
}

func checkMessagesForBool(messages protoreflect.MessageDescriptors, responseWriter check.ResponseWriter) {
	for i := 0; i < messages.Len(); i++ {
		msg := messages.Get(i)
		fields := msg.Fields()
		for j := 0; j < fields.Len(); j++ {
			field := fields.Get(j)
			if field.Kind() == protoreflect.BoolKind {
				responseWriter.AddAnnotation(
					check.WithMessagef("field %q uses bool type, which is not allowed in DCL", field.Name()),
					check.WithDescriptor(field),
				)
			}
		}
		// Check nested messages
		checkMessagesForBool(msg.Messages(), responseWriter)
	}
}

// checkNoBytes verifies that no fields use the bytes type.
func checkNoBytes(_ context.Context, responseWriter check.ResponseWriter, request check.Request) error {
	for _, file := range request.FileDescriptors() {
		fd := file.ProtoreflectFileDescriptor()
		checkMessagesForBytes(fd.Messages(), responseWriter)
	}
	return nil
}

func checkMessagesForBytes(messages protoreflect.MessageDescriptors, responseWriter check.ResponseWriter) {
	for i := 0; i < messages.Len(); i++ {
		msg := messages.Get(i)
		fields := msg.Fields()
		for j := 0; j < fields.Len(); j++ {
			field := fields.Get(j)
			if field.Kind() == protoreflect.BytesKind {
				responseWriter.AddAnnotation(
					check.WithMessagef("field %q uses bytes type, which is not allowed in DCL", field.Name()),
					check.WithDescriptor(field),
				)
			}
		}
		// Check nested messages
		checkMessagesForBytes(msg.Messages(), responseWriter)
	}
}

// checkNoAny verifies that no fields use google.protobuf.Any.
func checkNoAny(_ context.Context, responseWriter check.ResponseWriter, request check.Request) error {
	for _, file := range request.FileDescriptors() {
		fd := file.ProtoreflectFileDescriptor()
		checkMessagesForAny(fd.Messages(), responseWriter)
	}
	return nil
}

func checkMessagesForAny(messages protoreflect.MessageDescriptors, responseWriter check.ResponseWriter) {
	for i := 0; i < messages.Len(); i++ {
		msg := messages.Get(i)
		fields := msg.Fields()
		for j := 0; j < fields.Len(); j++ {
			field := fields.Get(j)
			if field.Kind() == protoreflect.MessageKind {
				msgDesc := field.Message()
				if msgDesc != nil && msgDesc.FullName() == "google.protobuf.Any" {
					responseWriter.AddAnnotation(
						check.WithMessagef("field %q uses google.protobuf.Any, which is not allowed in DCL", field.Name()),
						check.WithDescriptor(field),
					)
				}
			}
		}
		// Check nested messages
		checkMessagesForAny(msg.Messages(), responseWriter)
	}
}

// checkEnumInMessage verifies that enums are defined inside messages.
func checkEnumInMessage(_ context.Context, responseWriter check.ResponseWriter, request check.Request) error {
	for _, file := range request.FileDescriptors() {
		fd := file.ProtoreflectFileDescriptor()
		enums := fd.Enums()
		for i := 0; i < enums.Len(); i++ {
			enum := enums.Get(i)
			responseWriter.AddAnnotation(
				check.WithMessagef("enum %q must be defined inside a message", enum.Name()),
				check.WithDescriptor(enum),
			)
		}
	}
	return nil
}

// checkEnumZeroUnspecified verifies that enum zero values are exactly UNSPECIFIED.
func checkEnumZeroUnspecified(_ context.Context, responseWriter check.ResponseWriter, request check.Request) error {
	for _, file := range request.FileDescriptors() {
		fd := file.ProtoreflectFileDescriptor()
		checkFileEnumsZeroValue(fd, responseWriter)
	}
	return nil
}

func checkFileEnumsZeroValue(fd protoreflect.FileDescriptor, responseWriter check.ResponseWriter) {
	// Check top-level enums
	checkEnumsZeroValue(fd.Enums(), responseWriter)
	// Check enums in messages
	checkMessagesEnumsZeroValue(fd.Messages(), responseWriter)
}

func checkMessagesEnumsZeroValue(messages protoreflect.MessageDescriptors, responseWriter check.ResponseWriter) {
	for i := 0; i < messages.Len(); i++ {
		msg := messages.Get(i)
		checkEnumsZeroValue(msg.Enums(), responseWriter)
		// Check nested messages
		checkMessagesEnumsZeroValue(msg.Messages(), responseWriter)
	}
}

func checkEnumsZeroValue(enums protoreflect.EnumDescriptors, responseWriter check.ResponseWriter) {
	for i := 0; i < enums.Len(); i++ {
		enum := enums.Get(i)
		values := enum.Values()
		if values.Len() > 0 {
			zeroValue := values.Get(0)
			if zeroValue.Number() == 0 && string(zeroValue.Name()) != "UNSPECIFIED" {
				responseWriter.AddAnnotation(
					check.WithMessagef("enum %q zero value must be named UNSPECIFIED, got %q", enum.Name(), zeroValue.Name()),
					check.WithDescriptor(zeroValue),
				)
			}
		}
	}
}

// checkFieldNameUnderscore verifies field naming rules:
// - Underscores must be followed by letters (not digits or another underscore)
// - Fields cannot end with underscores
func checkFieldNameUnderscore(_ context.Context, responseWriter check.ResponseWriter, request check.Request) error {
	for _, file := range request.FileDescriptors() {
		fd := file.ProtoreflectFileDescriptor()
		checkMessagesFieldNames(fd.Messages(), responseWriter)
	}
	return nil
}

func checkMessagesFieldNames(messages protoreflect.MessageDescriptors, responseWriter check.ResponseWriter) {
	for i := 0; i < messages.Len(); i++ {
		msg := messages.Get(i)
		fields := msg.Fields()
		for j := 0; j < fields.Len(); j++ {
			field := fields.Get(j)
			name := string(field.Name())

			// Check if name ends with underscore
			if strings.HasSuffix(name, "_") {
				responseWriter.AddAnnotation(
					check.WithMessagef("field name %q cannot end with underscore", name),
					check.WithDescriptor(field),
				)
				continue
			}

			// Check that underscores are followed by letters
			for idx := 0; idx < len(name)-1; idx++ {
				if name[idx] == '_' {
					next := rune(name[idx+1])
					if !unicode.IsLetter(next) {
						responseWriter.AddAnnotation(
							check.WithMessagef("field name %q has underscore followed by non-letter at position %d", name, idx),
							check.WithDescriptor(field),
						)
						break
					}
				}
			}
		}
		// Check nested messages
		checkMessagesFieldNames(msg.Messages(), responseWriter)
	}
}

// Time-related types and their required suffixes
var timeTypeSuffixes = map[protoreflect.FullName]string{
	"google.protobuf.Duration":  "_duration",
	"google.protobuf.Timestamp": "_timestamp",
	"google.type.Interval":      "_interval",
	"google.type.Date":          "_date",
	"google.type.Month":         "_month",
	"google.type.DayOfWeek":     "_weekday",
	"google.type.TimeOfDay":     "_clocktime",
}

// checkTimeFieldSuffix verifies that time-related fields have correct suffixes.
func checkTimeFieldSuffix(_ context.Context, responseWriter check.ResponseWriter, request check.Request) error {
	for _, file := range request.FileDescriptors() {
		fd := file.ProtoreflectFileDescriptor()
		checkMessagesTimeFields(fd.Messages(), responseWriter)
	}
	return nil
}

func checkMessagesTimeFields(messages protoreflect.MessageDescriptors, responseWriter check.ResponseWriter) {
	for i := 0; i < messages.Len(); i++ {
		msg := messages.Get(i)
		fields := msg.Fields()
		for j := 0; j < fields.Len(); j++ {
			field := fields.Get(j)
			if field.Kind() == protoreflect.MessageKind {
				msgDesc := field.Message()
				if msgDesc != nil {
					if requiredSuffix, ok := timeTypeSuffixes[msgDesc.FullName()]; ok {
						fieldName := string(field.Name())
						if !strings.HasSuffix(fieldName, requiredSuffix) {
							responseWriter.AddAnnotation(
								check.WithMessagef("field %q of type %s must end with %q", fieldName, msgDesc.FullName(), requiredSuffix),
								check.WithDescriptor(field),
							)
						}
					}
				}
			}
		}
		// Check nested messages
		checkMessagesTimeFields(msg.Messages(), responseWriter)
	}
}
