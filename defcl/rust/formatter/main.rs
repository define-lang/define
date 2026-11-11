//! The `defclfmt` command.

use clap::error::ErrorKind;
use clap::{CommandFactory as _, Parser};
use defcl_formatter::format;
use defcl_parser::{DecodeError, SyntaxError, decode};
use indoc::formatdoc;
use rayon::iter::{IntoParallelRefIterator as _, ParallelIterator as _};
use source_rendering::SourceLines;
use std::fmt::Write as _;
use std::io::{IsTerminal as _, Read, Write};
use std::path::{Path, PathBuf};
use std::process::ExitCode;

/// Formats DCL files in place, or standard input to standard output.
///
/// Prints the syntax errors that each file still has, and each file that
/// cannot be read or written, and exits with status 2 if there is any.
#[derive(Parser)]
struct Arguments {
    /// Don't change any files or write the formatted text. Instead, list the
    /// files that need formatting, and exit with status 1 if there are any.
    /// Errors still exit with status 2.
    #[arg(long)]
    check: bool,
    /// The DCL files to format. With none, formats standard input and writes
    /// the result to standard output.
    files: Vec<PathBuf>,
}

/// What errors and `--check` call standard input.
const STANDARD_INPUT: &str = "<standard input>";

fn main() -> std::io::Result<ExitCode> {
    let arguments = Arguments::parse();
    // No one types DCL to the formatter, so with no files and no source piped
    // in, show how to use it instead of waiting for input.
    if arguments.files.is_empty() && std::io::stdin().is_terminal() {
        Arguments::command()
            .error(
                ErrorKind::MissingRequiredArgument,
                "give the DCL files to format, or pipe DCL to standard input",
            )
            .exit();
    }
    let outcome = if arguments.files.is_empty() {
        format_standard_input(
            arguments.check,
            &mut std::io::stdin(),
            &mut std::io::stdout(),
            &mut std::io::stderr(),
        )?
    } else {
        format_files(
            &arguments.files,
            arguments.check,
            &mut std::io::stdout(),
            &mut std::io::stderr(),
        )?
    };
    Ok(ExitCode::from(outcome as u8))
}

/// What formatting found, from best to worst. Each is the exit status that
/// reports it.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
enum Outcome {
    Formatted = 0,
    Unformatted = 1,
    Errors = 2,
}

/// Formats the DCL source in `input` and writes the result to `output`, or, if
/// `check`, only writes `STANDARD_INPUT` to `output` if formatting would change
/// the source. Writes each syntax error that the source still has, or the
/// error that reading `input` ends in, to `errors`.
///
/// # Errors
///
/// Returns the error that writing to `output` or `errors` ends in.
fn format_standard_input(
    check: bool,
    input: &mut impl Read,
    output: &mut impl Write,
    errors: &mut impl Write,
) -> std::io::Result<Outcome> {
    let mut bytes = Vec::new();
    if let Err(error) = input.read_to_end(&mut bytes) {
        writeln!(errors, "File \"{STANDARD_INPUT}\"\n{error}")?;
        return Ok(Outcome::Errors);
    }
    let file = format_source(bytes, check);
    let mut outcome = Outcome::Formatted;
    if check {
        if file.changed {
            writeln!(output, "{STANDARD_INPUT}")?;
            outcome = Outcome::Unformatted;
        }
    } else {
        let text = file
            .formatted
            .as_ref()
            .map_or(file.source.as_slice(), String::as_bytes);
        output.write_all(text)?;
    }
    let rendered = render_errors(STANDARD_INPUT, file);
    if !rendered.is_empty() {
        errors.write_all(rendered.as_bytes())?;
        outcome = Outcome::Errors;
    }
    Ok(outcome)
}

/// Formats the DCL file at each of `paths`, or, if `check`, only finds each
/// file that formatting would change and writes its path to `unformatted`.
/// Writes each syntax error that a file still has, and the error for each file
/// that cannot be read or written, to `errors`, in the order of `paths`.
///
/// # Errors
///
/// Returns the error that writing to `unformatted` or `errors` ends in.
fn format_files(
    paths: &[PathBuf],
    check: bool,
    unformatted: &mut impl Write,
    errors: &mut impl Write,
) -> std::io::Result<Outcome> {
    let reports: Vec<FileReport> = paths
        .par_iter()
        .map(|path| report_file(path, check))
        .collect();
    let mut outcome = Outcome::Formatted;
    for (path, report) in paths.iter().zip(reports) {
        if report.changed && check {
            writeln!(unformatted, "{}", path.display())?;
            outcome = outcome.max(Outcome::Unformatted);
        }
        if !report.errors.is_empty() {
            errors.write_all(report.errors.as_bytes())?;
            outcome = Outcome::Errors;
        }
    }
    Ok(outcome)
}

/// What formatting a DCL file found, ready to write.
struct FileReport {
    /// Whether formatting changes the file.
    changed: bool,
    /// The rendered errors: the file's syntax errors, or why it cannot be read
    /// or written.
    errors: String,
}

/// Formats the DCL file at `path`, writing it unless `check`, and renders its
/// errors.
fn report_file(path: &Path, check: bool) -> FileReport {
    let name = path.to_string_lossy();
    match format_file(path, check) {
        Ok(file) => FileReport {
            changed: file.changed,
            errors: render_errors(&name, file),
        },
        Err(error) => FileReport {
            changed: false,
            errors: formatdoc! {"
                File \"{name}\"
                {error}
            "},
        },
    }
}

/// Formats the DCL file at `path`, writing it unless `check`.
fn format_file(path: &Path, check: bool) -> std::io::Result<FormattedSource> {
    let file = format_source(std::fs::read(path)?, check);
    if !check && let Some(formatted) = &file.formatted {
        std::fs::write(path, formatted)?;
    }
    Ok(file)
}

/// What formatting DCL source found.
struct FormattedSource {
    /// The source as it was read.
    source: Vec<u8>,
    /// Whether formatting changes the source.
    changed: bool,
    /// The formatted text, if formatting changes the source and its formatted
    /// text was asked for.
    formatted: Option<String>,
    /// The syntax errors that the formatted text still has, in the formatted
    /// text if there is one, or else at their places in the source.
    errors: Vec<SyntaxError>,
}

/// Formats `bytes`, or, if `check`, only finds whether formatting changes
/// them and the errors that the formatted text would still have.
fn format_source(bytes: Vec<u8>, check: bool) -> FormattedSource {
    let source = match decode(bytes) {
        Ok(source) => source,
        Err(DecodeError { source, error }) => {
            return FormattedSource {
                source,
                changed: false,
                formatted: None,
                errors: vec![error],
            };
        }
    };
    if check {
        let (changed, errors) = defcl_formatter::check(&source);
        return FormattedSource {
            source: source.into_bytes(),
            changed,
            formatted: None,
            errors,
        };
    }
    let (formatted, errors) = format(&source);
    FormattedSource {
        source: source.into_bytes(),
        changed: formatted.is_some(),
        formatted,
        errors,
    }
}

/// The syntax errors that `file`, which errors call `name`, still has, each
/// rendered with the line that it is on.
fn render_errors(name: &str, file: FormattedSource) -> String {
    let mut rendered = String::new();
    if file.errors.is_empty() {
        return rendered;
    }
    let text = match file.formatted {
        Some(formatted) => formatted,
        // Lossy only for source that is not valid UTF-8, and then only to show
        // the error's line.
        None => String::from_utf8(file.source)
            .unwrap_or_else(|error| String::from_utf8_lossy(error.as_bytes()).into_owned()),
    };
    let lines = SourceLines::new(text);
    for error in &file.errors {
        let header = match error.location {
            Some(location) => lines.render(location, Some(name)),
            // The error is about the whole file.
            None => format!("File \"{name}\""),
        };
        let _ = writeln!(rendered, "{header}\n{error}");
    }
    rendered
}

#[cfg(test)]
mod tests {
    use super::{Arguments, Outcome, format_files, format_standard_input};
    use clap::CommandFactory as _;
    use googletest::prelude::*;
    use indoc::{formatdoc, indoc};
    use std::fmt::Write as _;
    use std::path::PathBuf;

    /// What a line with bytes that are not valid UTF-8 shows in their place.
    const REPLACEMENT_CHARACTER: char = '\u{fffd}';

    /// A new directory for a test's files, under the test's temporary
    /// directory.
    fn test_directory(name: &str) -> Result<PathBuf> {
        let directory = PathBuf::from(std::env::var_os("TEST_TMPDIR").or_fail()?).join(name);
        std::fs::create_dir_all(&directory).or_fail()?;
        Ok(directory)
    }

    #[gtest]
    fn arguments_are_well_formed() {
        Arguments::command().debug_assert();
    }

    #[gtest]
    fn formats_each_file() -> Result<()> {
        let directory = test_directory("formats_each_file")?;
        std::fs::write(directory.join("a.defcl"), "a: { b: 1 }\n").or_fail()?;
        std::fs::write(
            directory.join("c.defcl"),
            indoc! {"
                c: {
                  d: 1
                }
            "},
        )
        .or_fail()?;
        let mut unformatted = Vec::new();
        let mut errors = Vec::new();
        let outcome = format_files(
            &[directory.join("a.defcl"), directory.join("c.defcl")],
            false,
            &mut unformatted,
            &mut errors,
        )
        .or_fail()?;
        verify_that!(outcome, eq(Outcome::Formatted))?;
        verify_that!(unformatted, is_empty())?;
        verify_that!(errors, is_empty())?;
        verify_that!(
            std::fs::read_to_string(directory.join("a.defcl")).or_fail()?,
            eq(indoc! {"
                a: {
                  b: 1
                }
            "})
        )?;
        verify_that!(
            std::fs::read_to_string(directory.join("c.defcl")).or_fail()?,
            eq(indoc! {"
                c: {
                  d: 1
                }
            "})
        )
    }

    #[gtest]
    fn reports_the_errors_that_a_file_still_has() -> Result<()> {
        let directory = test_directory("reports_the_errors_that_a_file_still_has")?;
        let path = directory.join("a.defcl");
        std::fs::write(
            &path,
            indoc! {"
                a: {
                    b: {}
                }
            "},
        )
        .or_fail()?;
        let mut unformatted = Vec::new();
        let mut errors = Vec::new();
        let outcome = format_files(
            std::slice::from_ref(&path),
            false,
            &mut unformatted,
            &mut errors,
        )
        .or_fail()?;
        verify_that!(outcome, eq(Outcome::Errors))?;
        verify_that!(unformatted, is_empty())?;
        verify_that!(
            String::from_utf8(errors).or_fail()?,
            eq(&formatdoc! {"
                File \"{}\", line 2, column 6
                    b: {{}}
                       ^^
                Empty message values not allowed - leave the field out
            ",
            path.display()})
        )?;
        verify_that!(
            std::fs::read_to_string(&path).or_fail()?,
            eq(indoc! {"
                a: {
                  b: {}
                }
            "})
        )
    }

    #[gtest]
    fn check_lists_each_unformatted_file_without_changing_it() -> Result<()> {
        let directory = test_directory("check_lists_each_unformatted_file_without_changing_it")?;
        let unformatted_path = directory.join("a.defcl");
        let formatted_path = directory.join("c.defcl");
        std::fs::write(&unformatted_path, "a: { b: 1 }\n").or_fail()?;
        std::fs::write(
            &formatted_path,
            indoc! {"
                c: {
                  d: 1
                }
            "},
        )
        .or_fail()?;
        let mut unformatted = Vec::new();
        let mut errors = Vec::new();
        let outcome = format_files(
            &[unformatted_path.clone(), formatted_path],
            true,
            &mut unformatted,
            &mut errors,
        )
        .or_fail()?;
        verify_that!(outcome, eq(Outcome::Unformatted))?;
        verify_that!(
            String::from_utf8(unformatted).or_fail()?,
            eq(&format!("{}\n", unformatted_path.display()))
        )?;
        verify_that!(errors, is_empty())?;
        verify_that!(
            std::fs::read_to_string(&unformatted_path).or_fail()?,
            eq("a: { b: 1 }\n")
        )
    }

    #[gtest]
    fn check_reports_a_syntax_error_over_an_unformatted_file() -> Result<()> {
        let directory = test_directory("check_reports_a_syntax_error_over_an_unformatted_file")?;
        let with_error = directory.join("a.defcl");
        let unformatted_path = directory.join("c.defcl");
        std::fs::write(
            &with_error,
            indoc! {"
                a: {
                  b: {}
                }
            "},
        )
        .or_fail()?;
        std::fs::write(&unformatted_path, "c: { d: 1 }\n").or_fail()?;
        let mut unformatted = Vec::new();
        let mut errors = Vec::new();
        let outcome = format_files(
            &[with_error.clone(), unformatted_path.clone()],
            true,
            &mut unformatted,
            &mut errors,
        )
        .or_fail()?;
        verify_that!(outcome, eq(Outcome::Errors))?;
        verify_that!(
            String::from_utf8(unformatted).or_fail()?,
            eq(&format!("{}\n", unformatted_path.display()))
        )?;
        verify_that!(
            String::from_utf8(errors).or_fail()?,
            eq(&formatdoc! {"
                File \"{}\", line 2, column 6
                    b: {{}}
                       ^^
                Empty message values not allowed - leave the field out
            ",
            with_error.display()})
        )
    }

    #[gtest]
    fn check_reports_errors_where_they_are_in_the_unformatted_file() -> Result<()> {
        let directory =
            test_directory("check_reports_errors_where_they_are_in_the_unformatted_file")?;
        let path = directory.join("a.defcl");
        std::fs::write(
            &path,
            indoc! {"
                a: {
                    b: {}
                }
            "},
        )
        .or_fail()?;
        let mut unformatted = Vec::new();
        let mut errors = Vec::new();
        let outcome = format_files(
            std::slice::from_ref(&path),
            true,
            &mut unformatted,
            &mut errors,
        )
        .or_fail()?;
        verify_that!(outcome, eq(Outcome::Errors))?;
        verify_that!(
            String::from_utf8(unformatted).or_fail()?,
            eq(&format!("{}\n", path.display()))
        )?;
        verify_that!(
            String::from_utf8(errors).or_fail()?,
            eq(&formatdoc! {"
                File \"{}\", line 2, column 8
                    b: {{}}
                       ^^
                Empty message values not allowed - leave the field out
            ",
            path.display()})
        )
    }

    #[gtest]
    fn reports_a_file_that_cannot_be_read_and_formats_the_rest() -> Result<()> {
        let directory = test_directory("reports_a_file_that_cannot_be_read_and_formats_the_rest")?;
        let missing = directory.join("missing.defcl");
        let present = directory.join("a.defcl");
        std::fs::write(&present, "a: { b: 1 }\n").or_fail()?;
        let mut unformatted = Vec::new();
        let mut errors = Vec::new();
        let outcome = format_files(
            &[missing.clone(), present.clone()],
            false,
            &mut unformatted,
            &mut errors,
        )
        .or_fail()?;
        verify_that!(outcome, eq(Outcome::Errors))?;
        verify_that!(unformatted, is_empty())?;
        // The operating system words the error.
        let not_found = std::fs::read(&missing).err().or_fail()?;
        verify_that!(
            String::from_utf8(errors).or_fail()?,
            eq(&formatdoc! {"
                File \"{}\"
                {not_found}
            ",
            missing.display()})
        )?;
        verify_that!(
            std::fs::read_to_string(&present).or_fail()?,
            eq(indoc! {"
                a: {
                  b: 1
                }
            "})
        )
    }

    #[gtest]
    fn reports_a_file_that_is_not_valid_utf8_without_changing_it() -> Result<()> {
        let directory =
            test_directory("reports_a_file_that_is_not_valid_utf8_without_changing_it")?;
        let path = directory.join("a.defcl");
        std::fs::write(
            &path,
            indoc! {b"
                a: {
                    b: \"\xff\"
                }
            "},
        )
        .or_fail()?;
        let mut unformatted = Vec::new();
        let mut errors = Vec::new();
        let outcome = format_files(
            std::slice::from_ref(&path),
            false,
            &mut unformatted,
            &mut errors,
        )
        .or_fail()?;
        verify_that!(outcome, eq(Outcome::Errors))?;
        verify_that!(unformatted, is_empty())?;
        verify_that!(
            String::from_utf8(errors).or_fail()?,
            eq(&formatdoc! {"
                File \"{}\", line 2, column 9
                    b: \"{REPLACEMENT_CHARACTER}\"
                        ^
                Invalid UTF-8: the byte \\xff does not start a valid character
            ",
            path.display()})
        )?;
        verify_that!(
            std::fs::read(&path).or_fail()?,
            eq(indoc! {b"
                a: {
                    b: \"\xff\"
                }
            "})
        )
    }

    #[gtest]
    fn reports_errors_in_the_order_of_the_files() -> Result<()> {
        let directory = test_directory("reports_errors_in_the_order_of_the_files")?;
        let mut paths = Vec::new();
        let mut expected = String::new();
        for index in 0..100 {
            let path = directory.join(format!("{index}.defcl"));
            std::fs::write(&path, "").or_fail()?;
            writeln!(
                expected,
                "File \"{}\"\nThe file has no top-level message",
                path.display()
            )
            .or_fail()?;
            paths.push(path);
        }
        let mut unformatted = Vec::new();
        let mut errors = Vec::new();
        let outcome = format_files(&paths, false, &mut unformatted, &mut errors).or_fail()?;
        verify_that!(outcome, eq(Outcome::Errors))?;
        verify_that!(unformatted, is_empty())?;
        verify_that!(String::from_utf8(errors).or_fail()?, eq(&expected))
    }

    #[gtest]
    fn reports_an_error_about_the_whole_file_with_only_its_path() -> Result<()> {
        let directory = test_directory("reports_an_error_about_the_whole_file_with_only_its_path")?;
        let path = directory.join("empty.defcl");
        std::fs::write(&path, "").or_fail()?;
        let mut unformatted = Vec::new();
        let mut errors = Vec::new();
        let outcome = format_files(
            std::slice::from_ref(&path),
            false,
            &mut unformatted,
            &mut errors,
        )
        .or_fail()?;
        verify_that!(outcome, eq(Outcome::Errors))?;
        verify_that!(unformatted, is_empty())?;
        verify_that!(
            String::from_utf8(errors).or_fail()?,
            eq(&formatdoc! {"
                File \"{}\"
                The file has no top-level message
            ",
            path.display()})
        )
    }

    #[gtest]
    fn formats_standard_input_to_standard_output() -> Result<()> {
        let mut output = Vec::new();
        let mut errors = Vec::new();
        let outcome = format_standard_input(
            false,
            &mut b"a: { b: 1 }\n".as_slice(),
            &mut output,
            &mut errors,
        )
        .or_fail()?;
        verify_that!(outcome, eq(Outcome::Formatted))?;
        verify_that!(
            String::from_utf8(output).or_fail()?,
            eq(indoc! {"
                a: {
                  b: 1
                }
            "})
        )?;
        verify_that!(errors, is_empty())
    }

    #[gtest]
    fn writes_formatted_standard_input_unchanged() -> Result<()> {
        let mut output = Vec::new();
        let mut errors = Vec::new();
        let outcome = format_standard_input(
            false,
            &mut indoc! {b"
                a: {
                  b: 1
                }
            "}
            .as_slice(),
            &mut output,
            &mut errors,
        )
        .or_fail()?;
        verify_that!(outcome, eq(Outcome::Formatted))?;
        verify_that!(
            String::from_utf8(output).or_fail()?,
            eq(indoc! {"
                a: {
                  b: 1
                }
            "})
        )?;
        verify_that!(errors, is_empty())
    }

    #[gtest]
    fn check_names_unformatted_standard_input() -> Result<()> {
        let mut output = Vec::new();
        let mut errors = Vec::new();
        let outcome = format_standard_input(
            true,
            &mut b"a: { b: 1 }\n".as_slice(),
            &mut output,
            &mut errors,
        )
        .or_fail()?;
        verify_that!(outcome, eq(Outcome::Unformatted))?;
        verify_that!(
            String::from_utf8(output).or_fail()?,
            eq("<standard input>\n")
        )?;
        verify_that!(errors, is_empty())
    }

    #[gtest]
    fn check_writes_nothing_for_formatted_standard_input() -> Result<()> {
        let mut output = Vec::new();
        let mut errors = Vec::new();
        let outcome = format_standard_input(
            true,
            &mut indoc! {b"
                a: {
                  b: 1
                }
            "}
            .as_slice(),
            &mut output,
            &mut errors,
        )
        .or_fail()?;
        verify_that!(outcome, eq(Outcome::Formatted))?;
        verify_that!(output, is_empty())?;
        verify_that!(errors, is_empty())
    }

    #[gtest]
    fn writes_formatted_standard_input_and_its_remaining_errors() -> Result<()> {
        let mut output = Vec::new();
        let mut errors = Vec::new();
        let outcome = format_standard_input(
            false,
            &mut indoc! {b"
                a: {
                    b: {}
                }
            "}
            .as_slice(),
            &mut output,
            &mut errors,
        )
        .or_fail()?;
        verify_that!(outcome, eq(Outcome::Errors))?;
        verify_that!(
            String::from_utf8(output).or_fail()?,
            eq(indoc! {"
                a: {
                  b: {}
                }
            "})
        )?;
        verify_that!(
            String::from_utf8(errors).or_fail()?,
            eq(indoc! {"
                File \"<standard input>\", line 2, column 6
                    b: {}
                       ^^
                Empty message values not allowed - leave the field out
            "})
        )
    }

    #[gtest]
    fn writes_standard_input_that_is_not_valid_utf8_unchanged() -> Result<()> {
        let mut output = Vec::new();
        let mut errors = Vec::new();
        let outcome = format_standard_input(
            false,
            &mut indoc! {b"
                a: {
                    b: \"\xff\"
                }
            "}
            .as_slice(),
            &mut output,
            &mut errors,
        )
        .or_fail()?;
        verify_that!(outcome, eq(Outcome::Errors))?;
        verify_that!(
            output,
            eq(indoc! {b"
                a: {
                    b: \"\xff\"
                }
            "})
        )?;
        verify_that!(
            String::from_utf8(errors).or_fail()?,
            eq(&formatdoc! {"
                File \"<standard input>\", line 2, column 9
                    b: \"{REPLACEMENT_CHARACTER}\"
                        ^
                Invalid UTF-8: the byte \\xff does not start a valid character
            "})
        )
    }

    /// Standard input that cannot be read.
    struct UnreadableInput;

    impl std::io::Read for UnreadableInput {
        fn read(&mut self, _: &mut [u8]) -> std::io::Result<usize> {
            Err(std::io::Error::from(std::io::ErrorKind::IsADirectory))
        }
    }

    #[gtest]
    fn reports_standard_input_that_cannot_be_read() -> Result<()> {
        let mut output = Vec::new();
        let mut errors = Vec::new();
        let outcome = format_standard_input(false, &mut UnreadableInput, &mut output, &mut errors)
            .or_fail()?;
        verify_that!(outcome, eq(Outcome::Errors))?;
        verify_that!(output, is_empty())?;
        verify_that!(
            String::from_utf8(errors).or_fail()?,
            eq(indoc! {"
                File \"<standard input>\"
                is a directory
            "})
        )
    }
}
