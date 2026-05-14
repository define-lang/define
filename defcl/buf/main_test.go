package main

import (
	"testing"

	"buf.build/go/bufplugin/check/checktest"
)

// TestSpecValid verifies the spec is valid.
func TestSpecValid(t *testing.T) {
	checktest.SpecTest(t, spec)
}

// TODO: Remove skipUntilEdition2024Supported (and all calls to it) once
// github.com/bufbuild/protocompile bumps MaxSupportedEdition to EDITION_2024.
// checktest compiles sources through protocompile, which still has
// MaxSupportedEdition = EDITION_2023 (both at the latest release v0.14.1 and
// on main as of this writing). Parsing an edition 2024 file therefore fails
// with "edition \"2024\" not yet fully supported" before any rule runs. The
// production buf CLI is not affected (it parses via protoc and hands us
// pre-built descriptors).
func skipUntilEdition2024Supported(t *testing.T) {
	t.Helper()
	t.Skip("protocompile does not yet support edition 2024; see skipUntilEdition2024Supported")
}

// Tests for DEFCL_EDITION

func TestEdition_Valid(t *testing.T) {
	skipUntilEdition2024Supported(t)
	checktest.CheckTest{
		Request: &checktest.RequestSpec{
			Files: &checktest.ProtoFileSpec{
				DirPaths:  []string{"testdata/valid"},
				FilePaths: []string{"edition_2024.proto"},
			},
			RuleIDs: []string{"DEFCL_EDITION"},
		},
		Spec:                spec,
		ExpectedAnnotations: nil,
	}.Run(t)
}

func TestEdition_InvalidProto3(t *testing.T) {
	checktest.CheckTest{
		Request: &checktest.RequestSpec{
			Files: &checktest.ProtoFileSpec{
				DirPaths:  []string{"testdata/invalid/edition"},
				FilePaths: []string{"proto3.proto"},
			},
			RuleIDs: []string{"DEFCL_EDITION"},
		},
		Spec: spec,
		ExpectedAnnotations: []checktest.ExpectedAnnotation{
			{
				RuleID:       "DEFCL_EDITION",
				FileLocation: &checktest.ExpectedFileLocation{FileName: "proto3.proto"},
			},
		},
	}.Run(t)
}

func TestEdition_InvalidEdition2023(t *testing.T) {
	checktest.CheckTest{
		Request: &checktest.RequestSpec{
			Files: &checktest.ProtoFileSpec{
				DirPaths:  []string{"testdata/invalid/edition"},
				FilePaths: []string{"edition_2023.proto"},
			},
			RuleIDs: []string{"DEFCL_EDITION"},
		},
		Spec: spec,
		ExpectedAnnotations: []checktest.ExpectedAnnotation{
			{
				RuleID:       "DEFCL_EDITION",
				FileLocation: &checktest.ExpectedFileLocation{FileName: "edition_2023.proto"},
			},
		},
	}.Run(t)
}

// Tests for DEFCL_NO_BOOL

func TestNoBool_Valid(t *testing.T) {
	checktest.CheckTest{
		Request: &checktest.RequestSpec{
			Files: &checktest.ProtoFileSpec{
				DirPaths:  []string{"testdata/valid"},
				FilePaths: []string{"valid.proto"},
			},
			RuleIDs: []string{"DEFCL_NO_BOOL"},
		},
		Spec:                spec,
		ExpectedAnnotations: nil,
	}.Run(t)
}

func TestNoBool_Invalid(t *testing.T) {
	checktest.CheckTest{
		Request: &checktest.RequestSpec{
			Files: &checktest.ProtoFileSpec{
				DirPaths:  []string{"testdata/invalid/bool"},
				FilePaths: []string{"bool_field.proto"},
			},
			RuleIDs: []string{"DEFCL_NO_BOOL"},
		},
		Spec: spec,
		ExpectedAnnotations: []checktest.ExpectedAnnotation{
			{
				RuleID:       "DEFCL_NO_BOOL",
				FileLocation: &checktest.ExpectedFileLocation{FileName: "bool_field.proto", StartLine: 5, StartColumn: 2, EndLine: 5, EndColumn: 19},
			},
		},
	}.Run(t)
}

// Tests for DEFCL_NO_BYTES

func TestNoBytes_Valid(t *testing.T) {
	checktest.CheckTest{
		Request: &checktest.RequestSpec{
			Files: &checktest.ProtoFileSpec{
				DirPaths:  []string{"testdata/valid"},
				FilePaths: []string{"valid.proto"},
			},
			RuleIDs: []string{"DEFCL_NO_BYTES"},
		},
		Spec:                spec,
		ExpectedAnnotations: nil,
	}.Run(t)
}

func TestNoBytes_Invalid(t *testing.T) {
	checktest.CheckTest{
		Request: &checktest.RequestSpec{
			Files: &checktest.ProtoFileSpec{
				DirPaths:  []string{"testdata/invalid/bytes"},
				FilePaths: []string{"bytes_field.proto"},
			},
			RuleIDs: []string{"DEFCL_NO_BYTES"},
		},
		Spec: spec,
		ExpectedAnnotations: []checktest.ExpectedAnnotation{
			{
				RuleID:       "DEFCL_NO_BYTES",
				FileLocation: &checktest.ExpectedFileLocation{FileName: "bytes_field.proto", StartLine: 5, StartColumn: 2, EndLine: 5, EndColumn: 17},
			},
		},
	}.Run(t)
}

// Tests for DEFCL_NO_ANY

func TestNoAny_Valid(t *testing.T) {
	checktest.CheckTest{
		Request: &checktest.RequestSpec{
			Files: &checktest.ProtoFileSpec{
				DirPaths:  []string{"testdata/valid"},
				FilePaths: []string{"valid.proto"},
			},
			RuleIDs: []string{"DEFCL_NO_ANY"},
		},
		Spec:                spec,
		ExpectedAnnotations: nil,
	}.Run(t)
}

func TestNoAny_Invalid(t *testing.T) {
	checktest.CheckTest{
		Request: &checktest.RequestSpec{
			Files: &checktest.ProtoFileSpec{
				DirPaths:  []string{"testdata/invalid/any"},
				FilePaths: []string{"any_field.proto"},
			},
			RuleIDs: []string{"DEFCL_NO_ANY"},
		},
		Spec: spec,
		ExpectedAnnotations: []checktest.ExpectedAnnotation{
			{
				RuleID:       "DEFCL_NO_ANY",
				FileLocation: &checktest.ExpectedFileLocation{FileName: "any_field.proto", StartLine: 7, StartColumn: 2, EndLine: 7, EndColumn: 34},
			},
		},
	}.Run(t)
}

// Tests for DEFCL_ENUM_IN_MESSAGE

func TestEnumInMessage_Valid(t *testing.T) {
	checktest.CheckTest{
		Request: &checktest.RequestSpec{
			Files: &checktest.ProtoFileSpec{
				DirPaths:  []string{"testdata/valid"},
				FilePaths: []string{"valid.proto"},
			},
			RuleIDs: []string{"DEFCL_ENUM_IN_MESSAGE"},
		},
		Spec:                spec,
		ExpectedAnnotations: nil,
	}.Run(t)
}

func TestEnumInMessage_Invalid(t *testing.T) {
	checktest.CheckTest{
		Request: &checktest.RequestSpec{
			Files: &checktest.ProtoFileSpec{
				DirPaths:  []string{"testdata/invalid/enum_in_message"},
				FilePaths: []string{"top_level_enum.proto"},
			},
			RuleIDs: []string{"DEFCL_ENUM_IN_MESSAGE"},
		},
		Spec: spec,
		ExpectedAnnotations: []checktest.ExpectedAnnotation{
			{
				RuleID:       "DEFCL_ENUM_IN_MESSAGE",
				FileLocation: &checktest.ExpectedFileLocation{FileName: "top_level_enum.proto", StartLine: 4, StartColumn: 0, EndLine: 7, EndColumn: 1},
			},
		},
	}.Run(t)
}

// Tests for DEFCL_ENUM_ZERO_UNSPECIFIED

func TestEnumZeroUnspecified_Valid(t *testing.T) {
	checktest.CheckTest{
		Request: &checktest.RequestSpec{
			Files: &checktest.ProtoFileSpec{
				DirPaths:  []string{"testdata/valid"},
				FilePaths: []string{"valid.proto"},
			},
			RuleIDs: []string{"DEFCL_ENUM_ZERO_UNSPECIFIED"},
		},
		Spec:                spec,
		ExpectedAnnotations: nil,
	}.Run(t)
}

func TestEnumZeroUnspecified_InvalidWrongName(t *testing.T) {
	checktest.CheckTest{
		Request: &checktest.RequestSpec{
			Files: &checktest.ProtoFileSpec{
				DirPaths:  []string{"testdata/invalid/enum_zero"},
				FilePaths: []string{"wrong_zero_name.proto"},
			},
			RuleIDs: []string{"DEFCL_ENUM_ZERO_UNSPECIFIED"},
		},
		Spec: spec,
		ExpectedAnnotations: []checktest.ExpectedAnnotation{
			{
				RuleID:       "DEFCL_ENUM_ZERO_UNSPECIFIED",
				FileLocation: &checktest.ExpectedFileLocation{FileName: "wrong_zero_name.proto", StartLine: 6, StartColumn: 4, EndLine: 6, EndColumn: 16},
			},
		},
	}.Run(t)
}

func TestEnumZeroUnspecified_InvalidPrefixed(t *testing.T) {
	checktest.CheckTest{
		Request: &checktest.RequestSpec{
			Files: &checktest.ProtoFileSpec{
				DirPaths:  []string{"testdata/invalid/enum_zero"},
				FilePaths: []string{"prefixed_unspecified.proto"},
			},
			RuleIDs: []string{"DEFCL_ENUM_ZERO_UNSPECIFIED"},
		},
		Spec: spec,
		ExpectedAnnotations: []checktest.ExpectedAnnotation{
			{
				RuleID:       "DEFCL_ENUM_ZERO_UNSPECIFIED",
				FileLocation: &checktest.ExpectedFileLocation{FileName: "prefixed_unspecified.proto", StartLine: 6, StartColumn: 4, EndLine: 6, EndColumn: 27},
			},
		},
	}.Run(t)
}

// Tests for DEFCL_FIELD_NAME_UNDERSCORE

func TestFieldNameUnderscore_Valid(t *testing.T) {
	checktest.CheckTest{
		Request: &checktest.RequestSpec{
			Files: &checktest.ProtoFileSpec{
				DirPaths:  []string{"testdata/valid"},
				FilePaths: []string{"valid.proto"},
			},
			RuleIDs: []string{"DEFCL_FIELD_NAME_UNDERSCORE"},
		},
		Spec:                spec,
		ExpectedAnnotations: nil,
	}.Run(t)
}

func TestFieldNameUnderscore_InvalidUnderscoreDigit(t *testing.T) {
	checktest.CheckTest{
		Request: &checktest.RequestSpec{
			Files: &checktest.ProtoFileSpec{
				DirPaths:  []string{"testdata/invalid/field_underscore"},
				FilePaths: []string{"underscore_digit.proto"},
			},
			RuleIDs: []string{"DEFCL_FIELD_NAME_UNDERSCORE"},
		},
		Spec: spec,
		ExpectedAnnotations: []checktest.ExpectedAnnotation{
			{
				RuleID:       "DEFCL_FIELD_NAME_UNDERSCORE",
				FileLocation: &checktest.ExpectedFileLocation{FileName: "underscore_digit.proto", StartLine: 5, StartColumn: 2, EndLine: 5, EndColumn: 20},
			},
		},
	}.Run(t)
}

func TestFieldNameUnderscore_InvalidTrailing(t *testing.T) {
	checktest.CheckTest{
		Request: &checktest.RequestSpec{
			Files: &checktest.ProtoFileSpec{
				DirPaths:  []string{"testdata/invalid/field_underscore"},
				FilePaths: []string{"trailing_underscore.proto"},
			},
			RuleIDs: []string{"DEFCL_FIELD_NAME_UNDERSCORE"},
		},
		Spec: spec,
		ExpectedAnnotations: []checktest.ExpectedAnnotation{
			{
				RuleID:       "DEFCL_FIELD_NAME_UNDERSCORE",
				FileLocation: &checktest.ExpectedFileLocation{FileName: "trailing_underscore.proto", StartLine: 5, StartColumn: 2, EndLine: 5, EndColumn: 19},
			},
		},
	}.Run(t)
}

func TestFieldNameUnderscore_InvalidDouble(t *testing.T) {
	checktest.CheckTest{
		Request: &checktest.RequestSpec{
			Files: &checktest.ProtoFileSpec{
				DirPaths:  []string{"testdata/invalid/field_underscore"},
				FilePaths: []string{"double_underscore.proto"},
			},
			RuleIDs: []string{"DEFCL_FIELD_NAME_UNDERSCORE"},
		},
		Spec: spec,
		ExpectedAnnotations: []checktest.ExpectedAnnotation{
			{
				RuleID:       "DEFCL_FIELD_NAME_UNDERSCORE",
				FileLocation: &checktest.ExpectedFileLocation{FileName: "double_underscore.proto", StartLine: 5, StartColumn: 2, EndLine: 5, EndColumn: 24},
			},
		},
	}.Run(t)
}

// Tests for DEFCL_TIME_FIELD_SUFFIX

func TestTimeFieldSuffix_Valid(t *testing.T) {
	checktest.CheckTest{
		Request: &checktest.RequestSpec{
			Files: &checktest.ProtoFileSpec{
				DirPaths:  []string{"testdata/valid"},
				FilePaths: []string{"valid.proto"},
			},
			RuleIDs: []string{"DEFCL_TIME_FIELD_SUFFIX"},
		},
		Spec:                spec,
		ExpectedAnnotations: nil,
	}.Run(t)
}

func TestTimeFieldSuffix_InvalidDuration(t *testing.T) {
	checktest.CheckTest{
		Request: &checktest.RequestSpec{
			Files: &checktest.ProtoFileSpec{
				DirPaths:  []string{"testdata/invalid/time_suffix"},
				FilePaths: []string{"duration_wrong_suffix.proto"},
			},
			RuleIDs: []string{"DEFCL_TIME_FIELD_SUFFIX"},
		},
		Spec: spec,
		ExpectedAnnotations: []checktest.ExpectedAnnotation{
			{
				RuleID:       "DEFCL_TIME_FIELD_SUFFIX",
				FileLocation: &checktest.ExpectedFileLocation{FileName: "duration_wrong_suffix.proto", StartLine: 7, StartColumn: 2, EndLine: 7, EndColumn: 39},
			},
		},
	}.Run(t)
}

func TestTimeFieldSuffix_InvalidTimestamp(t *testing.T) {
	checktest.CheckTest{
		Request: &checktest.RequestSpec{
			Files: &checktest.ProtoFileSpec{
				DirPaths:  []string{"testdata/invalid/time_suffix"},
				FilePaths: []string{"timestamp_wrong_suffix.proto"},
			},
			RuleIDs: []string{"DEFCL_TIME_FIELD_SUFFIX"},
		},
		Spec: spec,
		ExpectedAnnotations: []checktest.ExpectedAnnotation{
			{
				RuleID:       "DEFCL_TIME_FIELD_SUFFIX",
				FileLocation: &checktest.ExpectedFileLocation{FileName: "timestamp_wrong_suffix.proto", StartLine: 7, StartColumn: 2, EndLine: 7, EndColumn: 40},
			},
		},
	}.Run(t)
}

func TestRulesIgnoreImportedFiles(t *testing.T) {
	skipUntilEdition2024Supported(t)
	checktest.CheckTest{
		Request: &checktest.RequestSpec{
			Files: &checktest.ProtoFileSpec{
				DirPaths:  []string{".."},
				FilePaths: []string{"buf/testdata/import_only/root.proto"},
			},
			RuleIDs: []string{
				"DEFCL_EDITION",
				"DEFCL_NO_BOOL",
				"DEFCL_NO_BYTES",
				"DEFCL_ENUM_IN_MESSAGE",
				"DEFCL_ENUM_ZERO_UNSPECIFIED",
				"DEFCL_FIELD_NAME_UNDERSCORE",
			},
		},
		Spec:                spec,
		ExpectedAnnotations: nil,
	}.Run(t)
}

// TestRulesIgnoreImportedFilesEdition2023 covers the IsImport-skip branches
// without depending on edition 2024 support in protocompile. The root file
// itself uses edition 2023, so DEFCL_EDITION reports a single annotation on
// it; every other rule expects zero annotations even though the imported
// files contain violations of each rule.
func TestRulesIgnoreImportedFilesEdition2023(t *testing.T) {
	checktest.CheckTest{
		Request: &checktest.RequestSpec{
			Files: &checktest.ProtoFileSpec{
				DirPaths:  []string{".."},
				FilePaths: []string{"buf/testdata/import_only_edition_2023/root.proto"},
			},
			RuleIDs: []string{
				"DEFCL_EDITION",
				"DEFCL_NO_BOOL",
				"DEFCL_NO_BYTES",
				"DEFCL_ENUM_IN_MESSAGE",
				"DEFCL_ENUM_ZERO_UNSPECIFIED",
				"DEFCL_FIELD_NAME_UNDERSCORE",
			},
		},
		Spec: spec,
		ExpectedAnnotations: []checktest.ExpectedAnnotation{
			{
				RuleID:       "DEFCL_EDITION",
				FileLocation: &checktest.ExpectedFileLocation{FileName: "buf/testdata/import_only_edition_2023/root.proto"},
			},
		},
	}.Run(t)
}
