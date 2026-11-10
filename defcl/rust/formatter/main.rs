//! Formats DCL files in place: `defclfmt FILE...`. Prints the syntax
//! errors that each file still has, and exits with status 2 if any does.

use defcl_formatter::format;
use std::ffi::OsString;
use std::io::Write;
use std::path::PathBuf;
use std::process::ExitCode;

fn main() -> std::io::Result<ExitCode> {
    let paths = std::env::args_os().skip(1);
    let all_formatted = format_files(paths, &mut std::io::stderr())?;
    Ok(if all_formatted {
        ExitCode::SUCCESS
    } else {
        ExitCode::from(2)
    })
}

/// Formats the DCL file at each of `paths`, and writes each syntax error that
/// a file still has to `errors`. Returns whether every file is free of syntax errors.
fn format_files(
    paths: impl Iterator<Item = OsString>,
    errors: &mut impl Write,
) -> std::io::Result<bool> {
    let mut all_formatted = true;
    for path in paths {
        let path = PathBuf::from(path);
        let source = std::fs::read_to_string(&path)?;
        let (formatted, file_errors) = format(&source);
        if formatted != source {
            std::fs::write(&path, formatted)?;
        }
        for error in &file_errors {
            let start = error.location.start;
            writeln!(
                errors,
                "{}:{}:{}: {error}",
                path.display(),
                start.line,
                start.column
            )?;
            all_formatted = false;
        }
    }
    Ok(all_formatted)
}

#[cfg(test)]
mod tests {
    use super::format_files;
    use googletest::prelude::*;
    use std::path::PathBuf;

    /// A new directory for a test's files, under the test's temporary
    /// directory.
    fn test_directory(name: &str) -> Result<PathBuf> {
        let directory = PathBuf::from(std::env::var_os("TEST_TMPDIR").or_fail()?).join(name);
        std::fs::create_dir_all(&directory).or_fail()?;
        Ok(directory)
    }

    #[gtest]
    fn formats_each_file() -> Result<()> {
        let directory = test_directory("formats_each_file")?;
        std::fs::write(directory.join("a.defcl"), "a: { b: 1 }\n").or_fail()?;
        std::fs::write(directory.join("c.defcl"), "c: {\n  d: 1\n}\n").or_fail()?;
        let mut errors = Vec::new();
        let all_formatted = format_files(
            [
                directory.join("a.defcl").into_os_string(),
                directory.join("c.defcl").into_os_string(),
            ]
            .into_iter(),
            &mut errors,
        )
        .or_fail()?;
        verify_that!(all_formatted, eq(true))?;
        verify_that!(errors, is_empty())?;
        verify_that!(
            std::fs::read_to_string(directory.join("a.defcl")).or_fail()?,
            eq("a: {\n  b: 1\n}\n")
        )?;
        verify_that!(
            std::fs::read_to_string(directory.join("c.defcl")).or_fail()?,
            eq("c: {\n  d: 1\n}\n")
        )
    }

    #[gtest]
    fn reports_the_errors_that_a_file_still_has() -> Result<()> {
        let directory = test_directory("reports_the_errors_that_a_file_still_has")?;
        let path = directory.join("a.defcl");
        std::fs::write(&path, "a: {\n    b: {}\n}\n").or_fail()?;
        let mut errors = Vec::new();
        let all_formatted =
            format_files([path.clone().into_os_string()].into_iter(), &mut errors).or_fail()?;
        verify_that!(all_formatted, eq(false))?;
        verify_that!(
            String::from_utf8(errors).or_fail()?,
            eq(&format!(
                "{}:2:6: Empty message values not allowed - leave the field out\n",
                path.display()
            ))
        )?;
        verify_that!(
            std::fs::read_to_string(&path).or_fail()?,
            eq("a: {\n  b: {}\n}\n")
        )
    }

    #[gtest]
    fn missing_file_is_an_error() -> Result<()> {
        let directory = test_directory("missing_file_is_an_error")?;
        verify_that!(
            format_files(
                [directory.join("missing.defcl").into_os_string()].into_iter(),
                &mut Vec::new(),
            )
            .map_err(|error| error.kind()),
            err(eq(std::io::ErrorKind::NotFound))
        )
    }
}
