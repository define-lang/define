//! Places in the source.

/// A point in the source, as a 1-based line and a 1-based column counted in
/// characters.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Position {
    pub line: usize,
    pub column: usize,
}

/// The part of the source that a node or an error covers. Lines and columns
/// are 1-based, columns count characters, and `end_line` and `end_column` are
/// the position of the last character that the location covers.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct SourceLocation {
    pub line: usize,
    pub column: usize,
    pub end_line: usize,
    pub end_column: usize,
}

impl SourceLocation {
    /// The location from `start` through `end`, the position of the last
    /// character covered.
    pub(crate) const fn new(start: Position, end: Position) -> Self {
        Self {
            line: start.line,
            column: start.column,
            end_line: end.line,
            end_column: end.column,
        }
    }

    /// The location of the one character at `position`, or of the point
    /// where something belongs.
    pub(crate) const fn at(position: Position) -> Self {
        Self::new(position, position)
    }

    pub(crate) const fn start(self) -> Position {
        Position {
            line: self.line,
            column: self.column,
        }
    }

    pub(crate) const fn end(self) -> Position {
        Position {
            line: self.end_line,
            column: self.end_column,
        }
    }
}
