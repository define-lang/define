#!/usr/bin/env python3
"""Validate proposal files in the define/proposals/ directory."""

import re
import sys
from dataclasses import dataclass
from pathlib import Path

REQUIRED_HEADERS: list[tuple[str, ...] | str] = [
    ("Problems", "Problem"),
    "Solution",
    "A Real Program",
    "Why This is the Right Solution",
    "Forward Compatibility",
    "Refactoring Existing Systems",
]

REQUIRED_METADATA: list[str] = [
    "Author",
    "Status",
    "Date Proposed",
    "Date Finalized",
]

PROPOSAL_TITLE_PREFIX = "Define Language Proposal"
DCL_PROPOSAL_TITLE_PREFIX = "Define Configuration Language Proposal"

FILENAME_PATTERN = re.compile(r"^(\d{5})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")


@dataclass
class ValidationResult:
    """Result of a validation check."""

    is_valid: bool
    error_message: str | None = None


@dataclass
class FilenameValidationResult:
    """Result of filename validation."""

    is_valid: bool
    error_message: str | None = None
    proposal_number: int | None = None
    kebab: str | None = None


def validate_filename(filename: str) -> FilenameValidationResult:
    """Validate filename format and extract proposal number and kebab-case part."""
    # Pattern: 5 digits, hyphen, kebab-case (letters/digits/hyphens, but no consecutive hyphens)
    match = FILENAME_PATTERN.match(filename)
    if not match:
        return FilenameValidationResult(
            is_valid=False,
            error_message="Filename must match pattern: NNNNN-kebab-case.md (5 digits, hyphen, kebab-case, .md)",
            proposal_number=None,
            kebab=None,
        )

    proposal_number = match.group(1)
    kebab = filename.removeprefix(f"{proposal_number}-").removesuffix(".md")
    return FilenameValidationResult(
        is_valid=True, proposal_number=int(proposal_number), kebab=kebab
    )


def validate_title(
    content: str, filename_result: FilenameValidationResult, filepath: Path
) -> ValidationResult:
    """Validate that title matches the expected format and filename."""
    lines = content.split("\n")
    title_line = lines[0].strip() if lines else None

    if not title_line:
        return ValidationResult(
            is_valid=False, error_message="File appears to be empty"
        )

    proposal_number = filename_result.proposal_number

    is_dcl_proposal = "defcl" in filepath.parts
    expected_prefix = (
        DCL_PROPOSAL_TITLE_PREFIX if is_dcl_proposal else PROPOSAL_TITLE_PREFIX
    )

    pattern = rf"^# {re.escape(expected_prefix)} {proposal_number}: (.+)$"
    match = re.match(pattern, title_line)
    if not match:
        return ValidationResult(
            is_valid=False,
            error_message=f"Title must start with '# {expected_prefix} {proposal_number}:' (found: {title_line[:60]}...)",
        )

    title_text = match.group(1)
    title_kebab = re.sub(r"[^a-z0-9\s-]", "", title_text.lower())
    title_kebab = title_kebab.replace(" ", "-")

    if title_kebab != filename_result.kebab:
        return ValidationResult(
            is_valid=False,
            error_message=f"Title text does not match filename: expected kebab-case '{filename_result.kebab}' but got '{title_kebab}' from title '{title_text}'",
        )

    return ValidationResult(is_valid=True)


def validate_metadata(content: str) -> ValidationResult:
    """Validate that required metadata fields are present."""
    lines = content.split("\n")

    # Format: title (line 0), empty line (line 1), metadata section starts (line 2+)
    # Skip title and empty line, then collect metadata lines until first ## header
    metadata_lines: list[str] = []
    for line in lines[2:]:
        stripped = line.strip()

        # Stop at first section header
        if stripped.startswith("##"):
            break

        # Collect metadata lines (they start with "- **")
        if stripped.startswith("- **"):
            metadata_lines.append(stripped)

    if not metadata_lines:
        return ValidationResult(
            is_valid=False,
            error_message="Metadata section is missing (expected after title and empty line)",
        )

    metadata_text = "\n".join(metadata_lines)

    for field in REQUIRED_METADATA:
        pattern = rf"^- \*\*{re.escape(field)}:\*\*"
        if not re.search(pattern, metadata_text, re.MULTILINE):
            return ValidationResult(
                is_valid=False,
                error_message=f"Missing required metadata field: {field}",
            )

    return ValidationResult(is_valid=True)


def validate_headers(content: str) -> ValidationResult:
    """Validate that exactly the required headers are present."""
    lines = content.split("\n")

    valid_headers: set[str] = set()
    required_header_specs: list[tuple[str, ...]] = []
    for required in REQUIRED_HEADERS:
        if isinstance(required, tuple):
            valid_headers.update(required)
            required_header_specs.append(required)
        else:
            valid_headers.add(required)
            required_header_specs.append((required,))

    found_headers: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            header_text = stripped.removeprefix("## ").strip()
            found_headers.append(header_text)

    found_header_set: set[str] = set(found_headers)
    invalid_headers: set[str] = found_header_set - valid_headers
    if invalid_headers:
        invalid_list = ", ".join(f"'{h}'" for h in sorted(invalid_headers))
        return ValidationResult(
            is_valid=False,
            error_message=f"Invalid headers found: {invalid_list}",
        )

    for required_spec in required_header_specs:
        found = any(header in found_header_set for header in required_spec)
        if not found:
            if len(required_spec) == 1:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Missing required header: '{required_spec[0]}'",
                )
            variants_str = " or ".join(f'"{variant}"' for variant in required_spec)
            return ValidationResult(
                is_valid=False,
                error_message=f"Missing required header: {variants_str}",
            )

    return ValidationResult(is_valid=True)


def validate_proposal_file(filepath: Path) -> list[str]:
    """Validate a single proposal file.

    Returns list of error messages (empty if valid).
    """
    errors: list[str] = []
    filename = filepath.name

    if filename.startswith("00000-"):
        return errors

    filename_result = validate_filename(filename)
    if not filename_result.is_valid and filename_result.error_message is not None:
        errors.append(filename_result.error_message)
        return errors  # Can't continue validation if filename is wrong.

    try:
        content = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        errors.append(f"Error reading file: {e}")
        return errors

    for result in [
        validate_title(content, filename_result, filepath),
        validate_metadata(content),
        validate_headers(content),
    ]:
        if not result.is_valid and result.error_message is not None:
            errors.append(result.error_message)

    return errors


def main() -> int:
    """Run proposal validation and return exit code."""
    if len(sys.argv) < 2:
        print("Usage: validate_proposals.py <file1> [file2 ...]", file=sys.stderr)
        return 1

    all_errors: list[str] = []
    proposal_files = [Path(f) for f in sys.argv[1:]]

    for filepath in proposal_files:
        if not filepath.exists():
            all_errors.append(f"{filepath}: file not found")
            continue

        errors = validate_proposal_file(filepath)
        if errors:
            all_errors.append(f"{filepath.name}:")
            for error in errors:
                all_errors.append(f"  - {error}")

    if all_errors:
        print("Proposal validation failed:", file=sys.stderr)
        print("\n".join(all_errors), file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
