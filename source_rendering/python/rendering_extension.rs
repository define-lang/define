//! The Python module that renders locations in source files:
//! `source_rendering.python.rendering`.

use pyo3::prelude::*;
use source_rendering::{Position, SourceLocation};

/// The location from `line`, `column` through `end_line`, `end_column` as
/// diagnostics show it: a header that names the file at `file_path`, then
/// `source_line`, the line that it starts on, with carets under the part that
/// it covers. With no `source_line`, only the header.
#[pyfunction]
#[pyo3(signature = (*, line, column, end_line, end_column, source_line, file_path))]
fn render_location(
    line: u32,
    column: u32,
    end_line: u32,
    end_column: u32,
    source_line: Option<&str>,
    file_path: Option<&str>,
) -> String {
    SourceLocation {
        start: Position { line, column },
        end: Position {
            line: end_line,
            column: end_column,
        },
    }
    .render(source_line, file_path)
}

/// `text` with each character that is not printable written as its escape,
/// such as `\t`, `\0` and `\u{200b}`.
#[pyfunction]
fn escape_invisible(text: &str) -> String {
    source_rendering::escape_invisible(text)
}

#[pymodule(gil_used = false)]
mod rendering {
    #[pymodule_export]
    use super::{escape_invisible, render_location};
}
