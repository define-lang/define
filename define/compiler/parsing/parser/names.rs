//! Names: local names, global names, typed names, and position references.

use crate::ast;
use crate::characters::{self, TextKind};
use crate::parse_error::{ParseError, ParseResult};
use crate::parser::Parser;
use crate::scanner::{Position, SourceText};
use pyo3::prelude::*;
use pyo3::types::PyString;
use terminals::{
    ACTION, CHAIN_SEPARATOR, COMPONENT_SEPARATOR, NAME_CONTENT_END, NAME_CONTENT_START,
    PATH_SEPARATOR, POSITION, SPACE, TERMINATOR,
};
use vector_scan::FqunSeparators;

pub(crate) const POSITION_OR_ACTION: [(&[u8], ast::NameType); 2] = [
    (POSITION, ast::NameType::Position),
    (ACTION, ast::NameType::Action),
];

/// An FQUN, with its canonical form, which is its text in the source.
pub(crate) struct FqunWithCanonicalText<'py, 'source> {
    pub(crate) node: ast::Fqun<'py>,
    pub(crate) canonical: &'source [u8],
}

/// The parts of a global name's content.
pub(crate) struct GlobalNameParts<'py, 'source> {
    pub(crate) location: ast::SourceLocation<'py>,
    pub(crate) fqun: Option<FqunWithCanonicalText<'py, 'source>>,
    pub(crate) path: ast::GlobalPathName<'py>,
    /// The name content's text in the source, which is its source name.
    pub(crate) text: &'source [u8],
}

/// A local name's content, with its text in the source.
pub(crate) struct LocalNameParts<'py, 'source> {
    pub(crate) content: ast::LocalNameContent<'py>,
    pub(crate) text: &'source [u8],
}

impl<'py, 'source> Parser<'py, 'source> {
    /// Parses a position reference, whose global names take their default
    /// FQUN from `fqun`.
    ///
    /// ```ebnf
    /// position_reference = typed_name, { "::", typed_name } ;
    /// ```
    pub(crate) fn parse_position_reference(
        &mut self,
        fqun: &FqunWithCanonicalText<'py, 'source>,
    ) -> ParseResult<ast::PositionReference<'py>> {
        let start = self.scanner.position;
        let typed_names = self.ast.start_tuple::<ast::TypedNameReference>();
        let full_typed_names = self.ast.start_texts();
        loop {
            // There is no typed name where the reference or its next part
            // belongs.
            if self.scanner.is_at_line_end() || self.scanner.next_byte_is(TERMINATOR) {
                let missing = self.scanner.position;
                return Err(self.errors.missing_position_reference(missing, missing));
            }
            let (typed_name, full_typed_name) = self.parse_typed_name_reference(fqun)?;
            self.ast.push(&typed_names, typed_name);
            self.ast.push_text(&full_typed_names, full_typed_name);
            if !self.scanner.consume(CHAIN_SEPARATOR) {
                break;
            }
        }
        let typed_names = self.ast.finish_tuple(typed_names)?;
        let canonical_chained_name_tuple = self.ast.finish_text_tuple(full_typed_names)?;
        let location = self.ast.location(start, self.scanner.position)?;
        Ok(self.ast.position_reference(
            location,
            typed_names,
            Some(canonical_chained_name_tuple),
            true,
        )?)
    }

    /// Parses a typed name in a position reference, which is local or global,
    /// and whose global name takes its default FQUN from `fqun`, and returns
    /// it with its full typed name.
    ///
    /// ```ebnf
    /// typed_name = ( "position" | "action" ), "<", ( local_name | global_name ), ">" ;
    /// ```
    fn parse_typed_name_reference(
        &mut self,
        fqun: &FqunWithCanonicalText<'py, 'source>,
    ) -> ParseResult<(ast::TypedNameReference<'py>, Bound<'py, PyString>)> {
        let start = self.scanner.position;
        // The name type is not `position` or `action`.
        let Some(name_type) = self.scanner.consume_any(&POSITION_OR_ACTION) else {
            return Err(self.expected_position_or_action());
        };
        // There is no `<`.
        if !self.scanner.consume_byte(NAME_CONTENT_START) {
            return Err(self.missing_open_angle_bracket());
        }
        let content_start = self.scanner.position;
        let (content, scanned) = self.scanner.consume_name_content();
        let content_end = self.scanner.position;
        let ends_name = self.scanner.next_byte_is(NAME_CONTENT_END);
        if ends_name && scanned.is_global_name {
            let name = self.global_name_parts(
                content,
                scanned.fqun_separators,
                content_start,
                content_end,
            )?;
            let location = self.ast.location(start, self.scanner.position)?;
            let (typed_name, full_typed_name) =
                self.global_typed_name_reference(location, fqun, name_type, name)?;
            return Ok((typed_name.into(), full_typed_name));
        }
        // The name content is neither a local name nor a global name that
        // ends with `>`.
        if !ends_name || !scanned.is_local_name {
            return Err(self.invalid_name_content(content, content_start, content_end));
        }
        let name = self.local_name_parts(content, content_start, content_end)?;
        let location = self.ast.location(start, self.scanner.position)?;
        let (typed_name, source_typed_name) =
            self.local_typed_name_reference(location, name_type, name)?;
        Ok((typed_name.into(), source_typed_name))
    }

    /// Parses a typed local name in a reference, and returns it with its
    /// source typed name and its location.
    ///
    /// ```ebnf
    /// typed_local_name = ( "position" | "action" ), "<", local_name, ">" ;
    /// ```
    pub(crate) fn parse_typed_local_name_reference(
        &mut self,
    ) -> ParseResult<(
        ast::LocalTypedNameReference<'py>,
        Bound<'py, PyString>,
        ast::SourceLocation<'py>,
    )> {
        let start = self.scanner.position;
        // The name type is not `position` or `action`.
        let Some(name_type) = self.scanner.consume_any(&POSITION_OR_ACTION) else {
            return Err(self.expected_position_or_action());
        };
        let name = self.parse_local_name_content()?;
        let location = self.ast.location(start, self.scanner.position)?;
        let (typed_name, source_typed_name) =
            self.local_typed_name_reference(location.clone(), name_type, name)?;
        Ok((typed_name, source_typed_name, location))
    }

    /// Returns the interned text of a typed name with `name_type` whose name
    /// content is `content`, after `fqun` and a `:` if there is one.
    fn typed_name_text(
        &mut self,
        name_type: ast::NameType,
        fqun: Option<&[u8]>,
        content: &[u8],
    ) -> PyResult<Bound<'py, PyString>> {
        let text = &mut self.typed_name_text_buffer;
        text.clear();
        text.extend_from_slice(name_type.value().as_bytes());
        text.push(NAME_CONTENT_START);
        if let Some(fqun) = fqun {
            text.extend_from_slice(fqun);
            text.push(COMPONENT_SEPARATOR);
        }
        text.extend_from_slice(content);
        text.push(NAME_CONTENT_END);
        self.ast.interned(text)
    }

    /// Constructs a typed local name reference with `name_type` to the local
    /// name `name`, and returns it with its source typed name.
    pub(crate) fn local_typed_name_reference(
        &mut self,
        location: ast::SourceLocation<'py>,
        name_type: ast::NameType,
        name: LocalNameParts<'py, 'source>,
    ) -> PyResult<(ast::LocalTypedNameReference<'py>, Bound<'py, PyString>)> {
        let source_typed_name = self.typed_name_text(name_type, None, name.text)?;
        let typed_name = self.ast.local_typed_name_reference(
            location,
            name_type,
            name.content,
            source_typed_name.clone(),
        )?;
        Ok((typed_name, source_typed_name))
    }

    /// Constructs a typed global name reference with `name_type` to the global
    /// name `name`, whose default FQUN is `fqun`, and returns it with its full
    /// typed name.
    pub(crate) fn global_typed_name_reference(
        &mut self,
        location: ast::SourceLocation<'py>,
        fqun: &FqunWithCanonicalText<'py, 'source>,
        name_type: ast::NameType,
        name: GlobalNameParts<'py, 'source>,
    ) -> PyResult<(ast::GlobalTypedNameReference<'py>, Bound<'py, PyString>)> {
        let source_typed_name = self.typed_name_text(name_type, None, name.text)?;
        // A name with its own FQUN is written in full, and a name without one
        // is only its path.
        let full_typed_name = match name.fqun {
            Some(_) => source_typed_name.clone(),
            None => self.typed_name_text(name_type, Some(fqun.canonical), name.text)?,
        };
        let name_content = self.ast.reference_global_name_content(
            name.location,
            name.fqun.map(|name_fqun| name_fqun.node),
            name.path,
        )?;
        let typed_name = self.ast.global_typed_name_reference(
            location,
            fqun.node.clone(),
            full_typed_name.clone(),
            name_type,
            name_content,
            source_typed_name,
        )?;
        Ok((typed_name, full_typed_name))
    }

    /// Constructs the typed global name with `name_type` that a definition
    /// defines, whose name content is `name_content`, with the text `text` in
    /// the source.
    pub(crate) fn global_typed_name_in_definition(
        &mut self,
        location: ast::SourceLocation<'py>,
        name_type: ast::NameType,
        name_content: ast::DefinitionGlobalNameContent<'py>,
        text: &'source [u8],
    ) -> PyResult<ast::GlobalTypedNameInDefinition<'py>> {
        let source_typed_name = self.typed_name_text(name_type, None, text)?;
        self.ast.global_typed_name_in_definition(
            location,
            name_type,
            name_content,
            source_typed_name,
        )
    }

    /// Parses the `<`, local name, and `>` that follow the name type of a
    /// local name in a definition or a position presence statement.
    ///
    /// ```ebnf
    /// "<", local_name, ">"
    /// ```
    pub(crate) fn parse_local_name_content(&mut self) -> ParseResult<LocalNameParts<'py, 'source>> {
        // There is no `<`.
        if !self.scanner.consume_byte(NAME_CONTENT_START) {
            return Err(self.missing_open_angle_bracket());
        }
        let start = self.scanner.position;
        let (content, scanned) = self.scanner.consume_name_content();
        let end = self.scanner.position;
        // The name content is not a local name that ends with `>`.
        if !scanned.is_local_name || !self.scanner.next_byte_is(NAME_CONTENT_END) {
            return Err(self.invalid_local_name_content(content, scanned, start, end));
        }
        self.local_name_parts(content, start, end)
    }

    /// Parses local name `content`, from `start` up to `end`, where the
    /// scanner is before its `>`.
    fn local_name_parts(
        &mut self,
        content: SourceText<'source>,
        start: Position,
        end: Position,
    ) -> ParseResult<LocalNameParts<'py, 'source>> {
        self.disallowed_name_character(content, start)?;
        self.scanner.consume_bytes(1);
        let location = self.ast.location(start, end)?;
        let name = self.ast.interned(content.bytes)?;
        Ok(LocalNameParts {
            content: self.ast.local_name_content(location, name)?,
            text: content.bytes,
        })
    }

    /// Parses a typed global name in a reference, whose default FQUN is
    /// `fqun`, with one of the `name_types`, where `wrong_name_type` returns
    /// the error for any other name type, and returns it with its full typed
    /// name.
    ///
    /// ```ebnf
    /// typed_global_name = name_type, "<", global_name, ">" ;
    /// ```
    pub(crate) fn parse_typed_global_name_reference(
        &mut self,
        fqun: &FqunWithCanonicalText<'py, 'source>,
        name_types: &[(&[u8], ast::NameType)],
        wrong_name_type: fn(&Self) -> ParseError,
    ) -> ParseResult<(ast::GlobalTypedNameReference<'py>, Bound<'py, PyString>)> {
        let start = self.scanner.position;
        // The name type is not one this reference allows.
        let Some(name_type) = self.scanner.consume_any(name_types) else {
            return Err(wrong_name_type(self));
        };
        let name = self.parse_global_name_content()?;
        let location = self.ast.location(start, self.scanner.position)?;
        Ok(self.global_typed_name_reference(location, fqun, name_type, name)?)
    }

    /// Parses the `<`, fully qualified global name, and `>` that follow the name
    /// type of a global name in a definition, and returns the name content
    /// with its text in the source and its FQUN.
    ///
    /// ```ebnf
    /// "<", fully_qualified_global_name, ">"
    /// fully_qualified_global_name = fqun, global_name_path ;
    /// ```
    pub(crate) fn parse_global_name_definition_content(
        &mut self,
    ) -> ParseResult<(
        ast::DefinitionGlobalNameContent<'py>,
        &'source [u8],
        FqunWithCanonicalText<'py, 'source>,
    )> {
        let content_start = self.scanner.position.next_column();
        let name = self.parse_global_name_content()?;
        // The name has no FQUN.
        let Some(fqun) = name.fqun else {
            // The scanner is after the `>`.
            let content_end = self.scanner.position.previous_column().previous_column();
            return Err(self
                .errors
                .definition_global_name_content_requires_fqun(content_start, content_end));
        };
        let name_content =
            self.ast
                .definition_global_name_content(name.location, fqun.node.clone(), name.path)?;
        Ok((name_content, name.text, fqun))
    }

    /// Parses the `<`, global name, and `>` that follow the name type of a
    /// global name, and returns the parts of its content.
    ///
    /// ```ebnf
    /// "<", global_name, ">"
    /// global_name = [ fqun ], global_name_path ;
    /// ```
    pub(crate) fn parse_global_name_content(
        &mut self,
    ) -> ParseResult<GlobalNameParts<'py, 'source>> {
        // There is no `<`.
        if !self.scanner.consume_byte(NAME_CONTENT_START) {
            return Err(self.missing_open_angle_bracket());
        }
        let start = self.scanner.position;
        let (content, scanned) = self.scanner.consume_global_name_content();
        let end = self.scanner.position;
        // The name content is not a global name that ends with `>`.
        if !scanned.is_global_name || !self.scanner.next_byte_is(NAME_CONTENT_END) {
            return Err(self.invalid_global_name_content(content, start, end));
        }
        self.global_name_parts(content, scanned.fqun_separators, start, end)
    }

    /// Returns the error for a character in name `content`, which begins at
    /// `start`, that names do not allow, if it has one.
    fn disallowed_name_character(
        &self,
        content: SourceText<'source>,
        start: Position,
    ) -> ParseResult<()> {
        // The name content has a character that names do not allow.
        if !content.is_known_ascii
            && let Some(error) = characters::first_disallowed_character(
                &self.errors,
                start,
                content.bytes,
                TextKind::Name,
            )
        {
            return Err(error);
        }
        Ok(())
    }

    /// Parses global name `content`, which runs from `start` up to `end`, where
    /// the scanner is before its `>`, and whose `:`s before its path are at
    /// `fqun_separators`, and returns its parts.
    fn global_name_parts(
        &mut self,
        content: SourceText<'source>,
        fqun_separators: Option<FqunSeparators>,
        start: Position,
        end: Position,
    ) -> ParseResult<GlobalNameParts<'py, 'source>> {
        self.disallowed_name_character(content, start)?;
        self.scanner.consume_bytes(1);
        let (fqun, path_start, path_text) = match fqun_separators {
            None => (None, start, content),
            // The name has a `:` but nothing before it.
            Some(FqunSeparators { last: 0, .. }) => {
                return Err(self
                    .errors
                    .invalid_global_name(start, end.previous_column()));
            }
            Some(separators) => {
                let (fqun, fqun_end) = self.parse_fqun(content, separators, start)?;
                (
                    Some(fqun),
                    fqun_end.next_column(),
                    content.slice(separators.last as usize + 1..),
                )
            }
        };
        let path_location = self.ast.location(path_start, end)?;
        let path_name = self.ast.interned(path_text.bytes)?;
        let path = self.ast.global_path_name(path_location, path_name)?;
        let location = self.ast.location(start, end)?;
        Ok(GlobalNameParts {
            location,
            fqun,
            path,
            text: content.bytes,
        })
    }

    /// Parses the FQUN at the start of global name `content`, which begins at
    /// `start` and whose `:`s before its path are at `separators`, and returns
    /// it with the position of its last `:`.
    ///
    /// ```ebnf
    /// fqun =
    ///     ( multiverse, ":", authority, ":", universe, ":"
    ///     | authority, ":", universe, ":"
    ///     | "standard:") ;
    /// ```
    fn parse_fqun(
        &mut self,
        content: SourceText<'source>,
        separators: FqunSeparators,
        start: Position,
    ) -> ParseResult<(FqunWithCanonicalText<'py, 'source>, Position)> {
        let first = separators.first as usize;
        let second = separators.second as usize;
        let last = separators.last as usize;
        let (multiverse, authority, universe) = match separators.count.get() {
            1 => (None, None, content.slice(..last)),
            2 => (
                None,
                Some(content.slice(..first)),
                content.slice(first + 1..last),
            ),
            3 => (
                Some(content.slice(..first)),
                Some(content.slice(first + 1..second)),
                content.slice(second + 1..last),
            ),
            // The FQUN has more than three components.
            _ => {
                let end = start.after(content.slice(..last)).previous_column();
                return Err(self.errors.global_name_invalid_fqun_format(start, end));
            }
        };
        let mut component_start = start;
        let multiverse = match multiverse {
            Some(name) => {
                let (location, name, end) = self.fqun_component(name, component_start)?;
                component_start = end.next_column();
                Some(self.ast.multiverse(location, name)?)
            }
            None => None,
        };
        let authority = match authority {
            Some(name) => {
                let (location, name, end) = self.fqun_component(name, component_start)?;
                component_start = end.next_column();
                Some(self.ast.authority(location, name)?)
            }
            None => None,
        };
        let (location, name, end) = self.fqun_component(universe, component_start)?;
        let universe = self.ast.universe(location, name)?;
        let location = self.ast.location(start, end)?;
        // The FQUN's canonical form is its components joined by `:`, as they
        // are written.
        let canonical = content.slice(..last);
        let canonical_name = self.ast.interned(canonical.bytes)?;
        let node = self
            .ast
            .fqun(location, multiverse, authority, universe, canonical_name)?;
        Ok((
            FqunWithCanonicalText {
                node,
                canonical: canonical.bytes,
            },
            end,
        ))
    }

    /// Returns the location and name of the FQUN component `name` that begins
    /// at `start`, and the position after it.
    fn fqun_component(
        &mut self,
        name: SourceText<'source>,
        start: Position,
    ) -> PyResult<(ast::SourceLocation<'py>, Bound<'py, PyString>, Position)> {
        let end = start.after(name);
        let location = self.ast.location(start, end)?;
        Ok((location, self.ast.interned(name.bytes)?, end))
    }
}

// The functions that only run on an error path.
impl<'py, 'source> Parser<'py, 'source> {
    /// Returns the error for a name type, at the scanner's position, that is
    /// not `position` or `action`.
    #[cold]
    #[inline(never)]
    pub(crate) fn expected_position_or_action(&self) -> ParseError {
        if let Some(error) = self.disallowed_character_after_any(&[POSITION, ACTION]) {
            return error;
        }
        let start = self.scanner.position;
        self.errors
            .expected_position_or_action(start, self.scanner.end_of_word())
    }

    /// Returns the error for name `content` in a position reference, from
    /// `start` up to `end`, the scanner's position, that is neither a local
    /// name nor a global name followed by `>`.
    #[cold]
    #[inline(never)]
    fn invalid_name_content(
        &self,
        content: SourceText<'source>,
        start: Position,
        end: Position,
    ) -> ParseError {
        if let Some(error) = self.name_content_error(content, start, end) {
            return error;
        }
        self.errors.invalid_name(
            start,
            end.previous_column(),
            &String::from_utf8_lossy(content.bytes),
        )
    }

    /// Returns the error for name `content` from `start` up to `end`, the
    /// scanner's position, that is empty, has a character that names do not
    /// allow, starts with a space, or has no `>` after its first word, if it
    /// has one of those errors.
    #[cold]
    fn name_content_error(
        &self,
        content: SourceText<'source>,
        start: Position,
        end: Position,
    ) -> Option<ParseError> {
        // There is no name between the `<` and where the `>` belongs.
        if content.bytes.is_empty() {
            return Some(self.errors.empty_name(start, start));
        }
        if let Err(error) = self.disallowed_name_character(content, start) {
            return Some(error);
        }
        match content.bytes.iter().position(|&byte| byte == SPACE) {
            // The name starts with a space.
            Some(0) => Some(self.errors.invalid_name(start, start, " ")),
            // A space ends the name's first word, where its `>` belongs.
            Some(space) => {
                let word = content.slice(..space);
                let missing = start.after(word);
                Some(self.errors.missing_close_angle_bracket(
                    missing,
                    missing,
                    &String::from_utf8_lossy(word.bytes),
                ))
            }
            // The name content runs to the end of the line without a `>`.
            None if !self.scanner.next_byte_is(NAME_CONTENT_END) => {
                Some(self.errors.missing_close_angle_bracket(
                    end,
                    end,
                    &String::from_utf8_lossy(content.bytes),
                ))
            }
            None => None,
        }
    }

    /// Returns the error for name `content`, from `start` up to `end`, the
    /// scanner's position, where a local name followed by `>` belongs.
    #[cold]
    #[inline(never)]
    fn invalid_local_name_content(
        &self,
        content: SourceText<'source>,
        scanned: vector_scan::NameContent,
        start: Position,
        end: Position,
    ) -> ParseError {
        // A space as the first character is not the end of a word.
        if content.bytes.first() == Some(&SPACE) {
            return self.errors.invalid_local_name_character(start, start, " ");
        }
        if let Some(error) = self.name_content_error(content, start, end) {
            return error;
        }
        // The name is a global name.
        if scanned.is_global_name {
            return self
                .errors
                .global_name_where_local_name_expected(start, end.previous_column());
        }
        // Every byte up to the first `:` or `/` is ASCII, since the name has
        // no character that names do not allow before it.
        let Some(index) = content
            .bytes
            .iter()
            .position(|&byte| byte == COMPONENT_SEPARATOR || byte == PATH_SEPARATOR)
        else {
            unreachable!("a name with no space, `:`, or `/` is a local name");
        };
        let position = start.after(content.slice(..index));
        let character = char::from(content.bytes[index]).to_string();
        self.errors
            .invalid_local_name_character(position, position, &character)
    }

    /// Returns the error for a name whose `<` is missing at the scanner's
    /// position.
    #[cold]
    #[inline(never)]
    fn missing_open_angle_bracket(&self) -> ParseError {
        if let Some(error) = self.disallowed_character_ahead(0) {
            return error;
        }
        let missing = self.scanner.position;
        let line = self.scanner.rest_of_line().bytes;
        let spaces = line.iter().take_while(|&&byte| byte == SPACE).count();
        // Spaces come between the name type and the `<`.
        if spaces > 0 && line.get(spaces) == Some(&NAME_CONTENT_START) {
            let last_space = Position {
                line: missing.line,
                column: missing.column + spaces - 1,
            };
            return self
                .errors
                .space_before_open_angle_bracket(missing, last_space);
        }
        self.errors.missing_open_angle_bracket(missing, missing)
    }

    /// Returns the error for name `content` from `start` up to `end`, the
    /// scanner's position, that is not a global name followed by `>`.
    #[cold]
    #[inline(never)]
    fn invalid_global_name_content(
        &self,
        content: SourceText<'source>,
        start: Position,
        end: Position,
    ) -> ParseError {
        // There is no name between the `<` and where the `>` belongs.
        if content.bytes.is_empty() {
            return self.errors.empty_name(start, start);
        }
        if let Some(error) = characters::first_disallowed_character(
            &self.errors,
            start,
            content.bytes,
            TextKind::Name,
        ) {
            return error;
        }
        // The name content runs to the end of the line without a `>`.
        if !self.scanner.next_byte_is(NAME_CONTENT_END) {
            return self.errors.missing_close_angle_bracket(
                end,
                end,
                &String::from_utf8_lossy(content.bytes),
            );
        }
        self.errors
            .invalid_global_name(start, end.previous_column())
    }
}
