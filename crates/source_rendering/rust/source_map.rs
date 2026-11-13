//! Shows locations in source files with their source lines, reading each file
//! again only when a location in it is first shown.

use crate::{CODE_INDENTATION, SourceLines, SourceLocation};
use rustc_hash::{FxBuildHasher, FxHashMap};
use std::fmt;
use std::hash::BuildHasher as _;
use std::sync::{Arc, Mutex, MutexGuard, PoisonError};

/// Shows locations with their source lines.
///
/// It reads a file again only when a location in it is first shown. A file that
/// cannot be read, or that changed after it was registered, shows why in place
/// of its source lines, since a changed file's new text would put the carets
/// under the wrong code.
pub struct SourceMap {
    in_memory_lines: Option<SourceLines>,
    files: Mutex<FxHashMap<Box<str>, File>>,
}

enum File {
    /// A registered file that no location has been shown in yet, with the
    /// digest of its text when it was registered.
    Unread(u64),
    /// A file that a location has been shown in, with its lines, or why they
    /// cannot be shown.
    Read(FileLines),
}

/// A location with no file path was shown, but no source was validated without
/// a file.
#[derive(Debug)]
pub struct NoInMemorySource;

impl fmt::Display for NoInMemorySource {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .write_str("a location with no file path needs the source validated without a file")
    }
}

impl std::error::Error for NoInMemorySource {}

type FileLines = Result<Arc<SourceLines>, SourceUnavailable>;

/// Why a registered file's source lines cannot be shown.
#[derive(Clone)]
enum SourceUnavailable {
    Unreadable(Arc<std::io::Error>),
    Changed,
}

impl fmt::Display for SourceUnavailable {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Unreadable(error) => write!(formatter, "could not read the file: {error}"),
            Self::Changed => formatter.write_str("the file changed after it was validated"),
        }
    }
}

impl SourceMap {
    /// A source map for registered files, and for `in_memory_source`, the
    /// source validated without a file, if there is one.
    #[must_use]
    pub fn new(in_memory_source: Option<String>) -> Self {
        Self {
            in_memory_lines: in_memory_source.map(SourceLines::new),
            files: Mutex::default(),
        }
    }

    /// Records that the file at `path` was validated with the text `source`,
    /// without keeping the text.
    pub fn register_file(&self, path: &str, source: &[u8]) {
        let digest = source_digest(source);
        self.lock_files().insert(path.into(), File::Unread(digest));
    }

    /// `location` in the source validated without a file, with its source
    /// line.
    ///
    /// # Errors
    ///
    /// `NoInMemorySource` if no source was validated without a file.
    pub fn render_in_memory(&self, location: SourceLocation) -> Result<String, NoInMemorySource> {
        let lines = self.in_memory_lines.as_ref().ok_or(NoInMemorySource)?;
        Ok(lines.render(location, None))
    }

    /// `location` in the file at `path`, with its source line if the file was
    /// registered and still has the text it was registered with, or why not if
    /// it was registered.
    #[must_use]
    pub fn render_in_file(&self, location: SourceLocation, path: &str) -> String {
        match self.file_lines(path) {
            Some(Ok(lines)) => lines.render(location, Some(path)),
            Some(Err(reason)) => format!(
                "{}\n{CODE_INDENTATION}(source not shown: {reason})",
                location.render(None, Some(path))
            ),
            None => location.render(None, Some(path)),
        }
    }

    /// The header that names the file at `path`, then, if the file was
    /// registered but no longer has the text it was registered with, why its
    /// source lines cannot be shown.
    #[must_use]
    pub fn render_header_without_position(&self, path: &str) -> String {
        match self.file_lines(path) {
            Some(Err(reason)) => {
                format!("File \"{path}\"\n{CODE_INDENTATION}(source not shown: {reason})")
            }
            Some(Ok(_)) | None => format!("File \"{path}\""),
        }
    }

    #[expect(
        clippy::significant_drop_tightening,
        reason = "The file's entry borrows from the lock until the end."
    )]
    fn file_lines(&self, path: &str) -> Option<FileLines> {
        // Holding the lock while reading a file costs nothing in practice. The
        // compiler registers files from many threads at once while it
        // validates them, and the lock exists for those registrations. It renders
        // locations and source lines only when rendering errors, in a single thread
        // at the end of compilation, so the lock is actually just window dressing
        // there.
        let mut files = self.lock_files();
        let file = files.get_mut(path)?;
        let digest = match file {
            File::Read(lines) => return Some(lines.clone()),
            File::Unread(digest) => *digest,
        };
        let lines = read_lines(path, digest);
        *file = File::Read(lines.clone());
        Some(lines)
    }

    fn lock_files(&self) -> MutexGuard<'_, FxHashMap<Box<str>, File>> {
        self.files.lock().unwrap_or_else(PoisonError::into_inner)
    }
}

/// A digest of a source file's text, which shows whether the file changed. It
/// detects accidental changes, not deliberate ones.
fn source_digest(source: &[u8]) -> u64 {
    FxBuildHasher.hash_one(source)
}

/// The lines of the file at `path`, or why they cannot be shown if it cannot be
/// read or its digest is no longer `digest`. Bytes that are not valid UTF-8
/// show as replacement characters, since such a file is reported as a syntax
/// error.
fn read_lines(path: &str, digest: u64) -> FileLines {
    let bytes =
        std::fs::read(path).map_err(|error| SourceUnavailable::Unreadable(Arc::new(error)))?;
    if source_digest(&bytes) != digest {
        return Err(SourceUnavailable::Changed);
    }
    let text = String::from_utf8(bytes)
        .unwrap_or_else(|error| String::from_utf8_lossy(error.as_bytes()).into_owned());
    Ok(Arc::new(SourceLines::new(text)))
}

#[cfg(test)]
mod tests {
    use super::SourceMap;
    use crate::{Position, SourceLocation};
    use googletest::prelude::*;
    use indoc::{formatdoc, indoc};
    use std::path::PathBuf;

    const fn location(line: u32, column: u32, end_column: u32) -> SourceLocation {
        SourceLocation {
            start: Position { line, column },
            end: Position {
                line,
                column: end_column,
            },
        }
    }

    /// Writes `source` to a new file named `name` in the test's temporary
    /// directory and returns its path.
    fn write_file(name: &str, source: impl AsRef<[u8]>) -> Result<String> {
        let directory =
            std::env::var_os("TEST_TMPDIR").map_or_else(std::env::temp_dir, PathBuf::from);
        let path = directory.join(name);
        std::fs::write(&path, source).or_fail()?;
        Ok(path.to_str().or_fail()?.to_owned())
    }

    #[gtest]
    fn a_registered_file_shows_its_source_line() -> Result<()> {
        let path = write_file(
            "unchanged.dfn",
            indoc! {"
                first
                    second line
            "},
        )?;
        let source_map = SourceMap::new(None);
        source_map.register_file(
            &path,
            indoc! {b"
                first
                    second line
            "},
        );
        verify_that!(
            source_map.render_in_file(location(2, 5, 10), &path),
            eq(&formatdoc! {r#"
                File "{path}", line 2, column 5
                    second line
                    ^^^^^^"#})
        )
    }

    #[gtest]
    fn a_file_with_invalid_utf8_shows_replacement_characters() -> Result<()> {
        let path = write_file("invalid_utf8.dfn", b"caf\xe9\n")?;
        let source_map = SourceMap::new(None);
        source_map.register_file(&path, b"caf\xe9\n");
        verify_that!(
            source_map.render_in_file(location(1, 4, 4), &path),
            eq(&formatdoc! {r#"
                File "{path}", line 1, column 4
                    caf�
                       ^"#})
        )
    }

    #[gtest]
    fn a_changed_file_shows_that_it_changed() -> Result<()> {
        let path = write_file("changed.dfn", "changed\n")?;
        let source_map = SourceMap::new(None);
        source_map.register_file(&path, b"original\n");
        verify_that!(
            source_map.render_in_file(location(1, 1, 1), &path),
            eq(&formatdoc! {r#"
                File "{path}", line 1, column 1
                    (source not shown: the file changed after it was validated)"#})
        )
    }

    #[gtest]
    fn a_missing_file_shows_that_it_cannot_be_read() -> Result<()> {
        let source_map = SourceMap::new(None);
        source_map.register_file("no/such/file.dfn", b"text\n");
        // The operating system words the error.
        let error = std::fs::read("no/such/file.dfn").err().or_fail()?;
        verify_that!(
            source_map.render_in_file(location(1, 1, 1), "no/such/file.dfn"),
            eq(&formatdoc! {r#"
                File "no/such/file.dfn", line 1, column 1
                    (source not shown: could not read the file: {error})"#})
        )
    }

    #[gtest]
    fn an_unregistered_file_shows_no_source_line() -> Result<()> {
        let path = write_file("unregistered.dfn", "text\n")?;
        let source_map = SourceMap::new(None);
        verify_that!(
            source_map.render_in_file(location(1, 1, 1), &path),
            eq(&format!("File \"{path}\", line 1, column 1"))
        )
    }

    #[gtest]
    fn a_file_is_read_once() -> Result<()> {
        let path = write_file("read_once.dfn", "before\n")?;
        let source_map = SourceMap::new(None);
        source_map.register_file(&path, b"before\n");
        verify_that!(
            source_map.render_in_file(location(1, 1, 6), &path),
            eq(&formatdoc! {r#"
                File "{path}", line 1, column 1
                    before
                    ^^^^^^"#})
        )?;
        std::fs::write(&path, "after!\n").or_fail()?;
        verify_that!(
            source_map.render_in_file(location(1, 1, 6), &path),
            eq(&formatdoc! {r#"
                File "{path}", line 1, column 1
                    before
                    ^^^^^^"#})
        )
    }

    #[gtest]
    fn a_changed_file_s_header_shows_that_it_changed() -> Result<()> {
        let path = write_file("changed_header.dfn", "changed\n")?;
        let source_map = SourceMap::new(None);
        source_map.register_file(&path, b"original\n");
        verify_that!(
            source_map.render_header_without_position(&path),
            eq(&formatdoc! {r#"
                File "{path}"
                    (source not shown: the file changed after it was validated)"#})
        )
    }

    #[gtest]
    fn an_unchanged_file_s_header_names_only_the_file() -> Result<()> {
        let path = write_file("unchanged_header.dfn", "text\n")?;
        let source_map = SourceMap::new(None);
        source_map.register_file(&path, b"text\n");
        verify_that!(
            source_map.render_header_without_position(&path),
            eq(&format!("File \"{path}\""))
        )
    }

    #[gtest]
    fn the_in_memory_source_shows_its_source_line() -> Result<()> {
        let source_map = SourceMap::new(Some(String::from(indoc! {"
            a
            b c
        "})));
        verify_that!(
            source_map.render_in_memory(location(2, 3, 3)),
            ok(eq(indoc! {"
                line 2, column 3
                    b c
                      ^"}))
        )
    }

    #[gtest]
    fn with_no_in_memory_source_it_is_an_error() -> Result<()> {
        let source_map = SourceMap::new(None);
        verify_that!(
            source_map
                .render_in_memory(location(1, 1, 1))
                .map_err(|error| error.to_string()),
            err(eq(
                "a location with no file path needs the source validated without a file"
            ))
        )
    }
}
