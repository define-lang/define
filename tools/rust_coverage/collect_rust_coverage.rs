//! Collects the coverage of the Rust code that a test runs, in a Rust test
//! binary or in the Rust extensions that a Python test loads.
//!
//! Bazel runs this after a test under `bazel coverage`, as the test's
//! `CC_CODE_COVERAGE_SCRIPT`. Rust code built for coverage writes an LLVM
//! profile into `COVERAGE_DIR` when the test's process exits. This merges the
//! profiles and writes LCOV for the test binary and every extension in the
//! test's runfiles that is instrumented into `COVERAGE_DIR`, where Bazel's LCOV
//! merger combines it with a copy of any Python coverage of the test.
//!
//! Stable Rust has no branch coverage, so the LCOV also has a branch record for
//! each code region that LLVM counts, such as each arm of an `if` and each side
//! of a `||`. A region that never ran is a branch that was never taken.

use serde_json::Value;
use std::collections::BTreeMap;
use std::env;
use std::error::Error;
use std::fmt::Write;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

/// The section that LLVM puts coverage mappings in, which only an
/// instrumented binary has.
const COVERAGE_MAP_SECTION: &[u8] = b"__llvm_covmap";
/// The kind of region in `llvm-cov`'s JSON export that covers code, rather
/// than an expansion, skipped code, or a gap.
const CODE_REGION: u64 = 0;
/// The source files whose coverage is not ours.
const EXTERNAL_SOURCES: &str = ".*external/.+";

fn main() -> Result<(), Box<dyn Error>> {
    let coverage_dir = PathBuf::from(env::var("COVERAGE_DIR")?);
    let profiles = files_with_extension(&coverage_dir, "profraw")?;
    // The test ran no instrumented Rust code.
    if profiles.is_empty() {
        return Ok(());
    }
    // rules_rust sets these for a Rust test, and //tools/bzl:py_test.bzl for
    // a Python test.
    let runfiles_dir = PathBuf::from(env::var("RUNFILES_DIR")?);
    let llvm_profdata = tool_path(&runfiles_dir, "RUST_LLVM_PROFDATA")?;
    let llvm_cov = tool_path(&runfiles_dir, "RUST_LLVM_COV")?;

    let profile = coverage_dir.join("rust_coverage.profdata");
    run(Command::new(llvm_profdata)
        .arg("merge")
        .arg("--sparse")
        .args(&profiles)
        .arg("--output")
        .arg(&profile))?;

    let workspace_runfiles = runfiles_dir.join(env::var("TEST_WORKSPACE")?);
    let mut binaries = Vec::new();
    let test_binary = workspace_runfiles.join(env::var("TEST_BINARY")?);
    if is_instrumented(&test_binary)? {
        binaries.push(fs::canonicalize(&test_binary)?);
    }
    find_instrumented_extensions(&workspace_runfiles, &mut binaries)?;
    binaries.sort();
    binaries.dedup();
    let lines = export(&llvm_cov, &profile, &binaries, "lcov")?;
    fs::write(coverage_dir.join("rust_coverage.dat"), lines)?;
    let regions = export(&llvm_cov, &profile, &binaries, "text")?;
    fs::write(
        coverage_dir.join("rust_coverage_regions.dat"),
        regions_as_lcov_branches(&serde_json::from_slice(&regions)?)?,
    )?;
    // Bazel's LCOV merger reads every file in `COVERAGE_DIR`, and it cannot
    // read this one.
    fs::remove_file(profile)?;
    // A Python test writes its Python coverage straight to the test's output
    // file, which the LCOV merger then replaces with the merge of
    // `COVERAGE_DIR`, so a copy in `COVERAGE_DIR` keeps it in the merge.
    fs::copy(
        env::var("COVERAGE_OUTPUT_FILE")?,
        coverage_dir.join("test_output_coverage.dat"),
    )?;
    Ok(())
}

/// Returns the path of the tool in the environment variable `variable`, which
/// is relative to the execution root that Bazel runs this in, or else to
/// `runfiles_dir`, as in rules_rust's own coverage collector.
fn tool_path(runfiles_dir: &Path, variable: &str) -> Result<PathBuf, Box<dyn Error>> {
    let path = PathBuf::from(env::var(variable)?);
    if path.exists() {
        return Ok(path);
    }
    Ok(runfiles_dir.join(path))
}

/// Returns `llvm-cov`'s export of the coverage of `binaries` from `profile`,
/// in `format`.
fn export(
    llvm_cov: &Path,
    profile: &Path,
    binaries: &[PathBuf],
    format: &str,
) -> Result<Vec<u8>, Box<dyn Error>> {
    let Some((first, rest)) = binaries.split_first() else {
        return Err("the test has no instrumented binary or extension".into());
    };
    let mut command = Command::new(llvm_cov);
    command
        .arg("export")
        .arg(format!("-format={format}"))
        .arg("-instr-profile")
        .arg(profile)
        .arg(format!("-ignore-filename-regex={EXTERNAL_SOURCES}"))
        .arg(first);
    for binary in rest {
        command.arg("-object").arg(binary);
    }
    let output = command
        .output()
        .map_err(|error| format!("{}: {error}", llvm_cov.display()))?;
    if !output.status.success() {
        return Err(format!(
            "llvm-cov export failed:\n{}",
            String::from_utf8_lossy(&output.stderr)
        )
        .into());
    }
    Ok(output.stdout)
}

/// The start and end, as line and column, of a code region.
type RegionSpan = (u64, u64, u64, u64);

/// Returns LCOV with a branch record for each code region in `export`, the
/// JSON export of `llvm-cov`, whose count is the number of times the region
/// ran.
fn regions_as_lcov_branches(export: &Value) -> Result<String, Box<dyn Error>> {
    // A generic function has a copy of its regions in each of its
    // instantiations, so the counts of the same region are added together.
    let mut counts_by_file: BTreeMap<String, BTreeMap<RegionSpan, u64>> = BTreeMap::new();
    for function in json_array(&export["data"][0]["functions"])? {
        let filenames = json_array(&function["filenames"])?;
        for region in json_array(&function["regions"])? {
            let numbers = json_array(region)?
                .iter()
                .map(|number| number.as_u64().ok_or("a region field is not a number"))
                .collect::<Result<Vec<u64>, _>>()?;
            let &[
                start_line,
                start_column,
                end_line,
                end_column,
                count,
                file,
                _,
                kind,
            ] = numbers.as_slice()
            else {
                return Err("a region does not have eight fields".into());
            };
            if kind != CODE_REGION {
                continue;
            }
            let filename = filenames
                .get(usize::try_from(file)?)
                .and_then(Value::as_str)
                .ok_or("a region's file is not in its function's filenames")?;
            if filename.contains("external/") {
                continue;
            }
            *counts_by_file
                .entry(filename.to_owned())
                .or_default()
                .entry((start_line, start_column, end_line, end_column))
                .or_default() += count;
        }
    }
    let mut lcov = String::new();
    for (filename, counts) in counts_by_file {
        writeln!(lcov, "SF:{filename}")?;
        for ((start_line, start_column, end_line, end_column), count) in counts {
            writeln!(
                lcov,
                "BRDA:{start_line},0,region from {start_line}:{start_column} to \
                 {end_line}:{end_column},{count}"
            )?;
        }
        writeln!(lcov, "end_of_record")?;
    }
    Ok(lcov)
}

/// Returns `value` as a JSON array.
fn json_array(value: &Value) -> Result<&Vec<Value>, Box<dyn Error>> {
    value
        .as_array()
        .ok_or_else(|| "llvm-cov's export is not shaped as expected".into())
}

/// Returns the files directly in `directory` whose extension is `extension`.
fn files_with_extension(directory: &Path, extension: &str) -> Result<Vec<PathBuf>, Box<dyn Error>> {
    let mut files = Vec::new();
    for entry in fs::read_dir(directory)? {
        let path = entry?.path();
        if path.extension().is_some_and(|found| found == extension) {
            files.push(path);
        }
    }
    Ok(files)
}

/// Adds the canonical path of every shared library under `directory` that is
/// instrumented for coverage to `extensions`.
fn find_instrumented_extensions(
    directory: &Path,
    extensions: &mut Vec<PathBuf>,
) -> Result<(), Box<dyn Error>> {
    for entry in fs::read_dir(directory)? {
        let path = entry?.path();
        // Runfiles are symlinks, so this follows them.
        let metadata = fs::metadata(&path)?;
        if metadata.is_dir() {
            find_instrumented_extensions(&path, extensions)?;
        } else if path.extension().is_some_and(|found| found == "so") && is_instrumented(&path)? {
            extensions.push(fs::canonicalize(&path)?);
        }
    }
    Ok(())
}

/// Whether the binary at `path` is instrumented for coverage.
fn is_instrumented(path: &Path) -> Result<bool, Box<dyn Error>> {
    let contents = fs::read(path).map_err(|error| format!("{}: {error}", path.display()))?;
    Ok(contents
        .windows(COVERAGE_MAP_SECTION.len())
        .any(|window| window == COVERAGE_MAP_SECTION))
}

/// Runs `command` and returns an error if it fails.
fn run(command: &mut Command) -> Result<(), Box<dyn Error>> {
    let status = command
        .status()
        .map_err(|error| format!("{command:?}: {error}"))?;
    if !status.success() {
        return Err(format!("{command:?} failed with {status}").into());
    }
    Ok(())
}
