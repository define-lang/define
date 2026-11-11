//! Writes `error_types.py`, the Python enums of the kinds of defcl diagnostics, from
//! the kinds of the Rust errors, to the path in its one argument.

use defcl_parser::SyntaxErrorKind;
use defcl_semantics::SemanticErrorKind;
use indoc::indoc;
use std::fmt::Write as _;
use strum::VariantNames as _;

/// Appends a Python enum class named `name` with the docstring `docstring` and
/// a member for each of `members`.
fn write_enum(module: &mut String, name: &str, docstring: &str, members: &[&str]) {
    module.push_str("\n\n");
    let _ = writeln!(module, "class {name}(enum.Enum):");
    let _ = writeln!(module, "    \"\"\"{docstring}\"\"\"");
    module.push('\n');
    for member in members {
        let _ = writeln!(module, "    {member} = enum.auto()");
    }
}

fn main() -> std::io::Result<()> {
    let mut module = String::from(indoc! {r#"
        """The kinds of defcl diagnostics, generated from the kinds of the Rust errors."""

        from __future__ import annotations

        import enum
    "#});
    write_enum(
        &mut module,
        "SyntaxDiagnosticKind",
        "The kinds of syntax error in a defcl file.",
        SyntaxErrorKind::VARIANTS,
    );
    write_enum(
        &mut module,
        "SemanticDiagnosticKind",
        "The kinds of error that checking a defcl file against its schema finds.",
        SemanticErrorKind::VARIANTS,
    );
    let path = std::env::args_os()
        .nth(1)
        .ok_or_else(|| std::io::Error::other("expected the output path"))?;
    std::fs::write(path, module)
}
