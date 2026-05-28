# pyright: reportUnusedCallResult=false
from pathlib import Path, PurePosixPath

import pytest

from define.compiler import ast, diagnostics, parser, transformer
from define.compiler.validator.reference_graph import reference_graph_validator
from define.compiler.validator.structural import program_validator
from tools import generate_large_define_source as gen

# Diagnostic types that mean a name or constraint in the source is invalid.
# Runtime / dataflow diagnostics (occupancy, move semantics, destructor
# guarantees, etc.) are not in this set: they are allowed to fire on the
# stress-test source even when every name and constraint is well-formed.
_NAME_OR_CONSTRAINT_DIAGNOSTICS: tuple[type[diagnostics.Diagnostic], ...] = (
    diagnostics.ReservedUniverseNameDiagnostic,
    diagnostics.ReservedAuthorityDomainDiagnostic,
    diagnostics.DotlessAuthorityDomainDiagnostic,
    diagnostics.ReservedMultiverseNameDiagnostic,
    diagnostics.PathMismatchDiagnostic,
    diagnostics.UniverseWithoutAuthorityDiagnostic,
    diagnostics.DuplicateDefinitionDiagnostic,
    diagnostics.LocalNameConflictDiagnostic,
    diagnostics.DuplicatePositionConstraintDiagnostic,
    diagnostics.DuplicateQualityImplicationDiagnostic,
    diagnostics.UnusedQualityImplicationDiagnostic,
    diagnostics.FqunMismatchDiagnostic,
    diagnostics.AuthorityDomainTooShortDiagnostic,
    diagnostics.AuthorityDomainInvalidCharDiagnostic,
    diagnostics.InvalidAuthorityPathSegmentDiagnostic,
    diagnostics.AuthorityPathEmptySegmentDiagnostic,
    diagnostics.InvalidGlobalNamePathCharacterDiagnostic,
    diagnostics.GlobalNamePathMissingLeadingSlashDiagnostic,
    diagnostics.GlobalNamePathTrailingSlashDiagnostic,
    diagnostics.GlobalNamePathEmptySegmentDiagnostic,
    diagnostics.InvalidLocalNameFormatDiagnostic,
    diagnostics.MultiverseNameTooShortDiagnostic,
    diagnostics.MultiverseNameInvalidCharDiagnostic,
    diagnostics.UniverseNameTooShortDiagnostic,
    diagnostics.UniverseNameInvalidCharDiagnostic,
    diagnostics.GlobalReferenceMustUseShortFormDiagnostic,
    diagnostics.ReferencedGlobalNameWrongTypeDiagnostic,
    diagnostics.ReferencedFileNotFoundDiagnostic,
    diagnostics.ExternalUniverseNotConfiguredDiagnostic,
    diagnostics.NoProjectRootInNonFilesystemContextDiagnostic,
    diagnostics.SubRootAlreadyOccupiedDiagnostic,
    diagnostics.PathInsideOtherUniverseDiagnostic,
    diagnostics.CircularGlobalReferenceDiagnostic,
    diagnostics.UnnecessarySelfReferenceDiagnostic,
    diagnostics.PositionReferenceChainEndDiagnostic,
    diagnostics.UndefinedLocalNameDiagnostic,
    diagnostics.UnknownGlobalNameDiagnostic,
    diagnostics.LocalActionNameDiagnostic,
    diagnostics.ChainedLocalNameRequiresActionDiagnostic,
    diagnostics.ChainElementNotInConstraintsDiagnostic,
    diagnostics.ChainElementNotInActionDiagnostic,
    diagnostics.MoveViolatesConstraintsDiagnostic,
    diagnostics.MoveIntoDefiningPositionDiagnostic,
)


def _parse_and_transform(source: str) -> ast.Program:
    par = parser.Parser()
    result = par.parse(source, file_path=PurePosixPath("generated.dfn"))
    assert result.exception is None
    assert result.diagnostics == []
    assert result.tree is not None
    return transformer.DefineTransformer(
        file_path=PurePosixPath("generated.dfn")
    ).transform(result.tree)


class TestGenerateSourceLines:
    def test_minimum_target_raises(self):
        with pytest.raises(ValueError, match="target_lines must be at least"):
            gen.generate_source_lines(50)

    def test_invalid_chain_length_raises(self):
        with pytest.raises(ValueError, match="max_chain_length must be at least 2"):
            gen.generate_source_lines(500, max_chain_length=1)

    def test_invalid_fqun_raises(self):
        with pytest.raises(ValueError, match="fqun must be"):
            gen.generate_source_lines(500, fqun="just_a_path")

    def test_fqun_with_too_few_segments_raises(self):
        with pytest.raises(ValueError, match="fqun prefix must have 2 or 3"):
            gen.generate_source_lines(500, fqun="onlyone:/path")

    def test_fqun_path_must_start_with_slash(self):
        with pytest.raises(ValueError, match="fqun path component must start with"):
            gen.generate_source_lines(500, fqun="authority:universe:notapath")

    def test_small_target_produces_parseable_program(self):
        lines = gen.generate_source_lines(500)
        assert len(lines) >= 500
        program = _parse_and_transform("\n".join(lines) + "\n")
        assert len(program.definitions) >= 3

    def test_output_exercises_diverse_syntax(self):
        source = "\n".join(gen.generate_source_lines(2000)) + "\n"
        assert "define the potential position" in source
        assert "define the potential action" in source
        assert "it may only contain particles where" in source
        assert "it also assigns the" in source
        assert "after it is assigned" in source
        assert "this particle is being destroyed" in source
        assert "create a particle in " in source
        assert "move the particle in " in source
        assert "destroy the particle in " in source
        assert "::" in source
        assert "#" in source

    def test_long_chain_present_at_default_max(self):
        lines = gen.generate_source_lines(2000)
        longest_chain_elements = max(line.count("::") + 1 for line in lines)
        assert longest_chain_elements >= gen.DEFAULT_MAX_CHAIN_LENGTH

    def test_custom_max_chain_length_is_honored(self):
        lines = gen.generate_source_lines(2000, max_chain_length=50)
        longest_chain_elements = max(line.count("::") + 1 for line in lines)
        assert longest_chain_elements >= 50
        assert longest_chain_elements <= 50

    def test_multiple_definitions_emitted(self):
        program = _parse_and_transform(
            "\n".join(gen.generate_source_lines(1000)) + "\n"
        )
        assert len(program.definitions) > 5

    def test_custom_fqun_appears_in_main_action(self):
        lines = gen.generate_source_lines(500, fqun="mv:example.com:custom:/entry")
        joined = "\n".join(lines)
        assert "action<mv:example.com:custom:/entry>" in joined


class TestWriteToPath:
    def test_writes_file_with_expected_line_count(self, tmp_path: Path):
        out = tmp_path / "big.dfn"
        written = gen.write_to_path(out, 500)
        assert written >= 500
        assert out.read_text(encoding="utf-8").count("\n") == written

    def test_written_file_parses_and_transforms_cleanly(self, tmp_path: Path):
        out = tmp_path / "big.dfn"
        gen.write_to_path(out, 1000, max_chain_length=100)
        _parse_and_transform(out.read_text(encoding="utf-8"))


class TestFullDriver:
    def test_non_filesystem_validation_has_no_name_or_constraint_diagnostics(self):
        source = "\n".join(gen.generate_source_lines(500, max_chain_length=10)) + "\n"

        pv = program_validator.ProgramStructuralValidator()
        program_result = pv.validate_program_non_filesystem(source)
        reference_graph_validator.ReferenceGraphValidator(
            program_result.reference_graph,
            program_result.definition_results,
        ).validate()

        assert program_result.all_exceptions == []
        for diagnostic in program_result.all_diagnostics:
            assert not isinstance(diagnostic, _NAME_OR_CONSTRAINT_DIAGNOSTICS), (
                f"{type(diagnostic).__name__}: {diagnostic.message}"
            )
