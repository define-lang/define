"""Diagnostic base classes, and the diagnostics that more than one compiler stage reports."""

from __future__ import annotations

import typing
from typing import ClassVar

import msgspec

if typing.TYPE_CHECKING:
    from crates.source_rendering.python import rendering


class BaseDiagnostic(msgspec.Struct):
    """Base class for the compiler's own diagnostics."""

    message_format: ClassVar[str] = ""

    def format(self, sources: rendering.SourceMap, /) -> str:
        """Format the diagnostic with the source lines of every location it mentions."""
        return self.render_message(sources)

    def render_message(self, _sources: rendering.SourceMap, /) -> str:
        """Render the diagnostic message, with source lines for other locations it mentions."""
        return self.message_format.format(self=self)


class Diagnostic(BaseDiagnostic):
    """Base class for diagnostics about a place in a Define file."""

    location: rendering.SourceLocation

    @typing.override
    def format(self, sources: rendering.SourceMap, /) -> str:
        return (
            f"{sources.render_location(self.location)}\n{self.render_message(sources)}"
        )


class FormattableDiagnostic(typing.Protocol):
    """A diagnostic as the compiler reports it: anything that can show itself."""

    def format(self, sources: rendering.SourceMap, /) -> str:
        """Format the diagnostic with the source lines of every location it mentions."""
        ...


class EntryPointNotConstructorDiagnostic(Diagnostic):
    """Diagnostic for when the program entry point is not a constructor."""

    message_format: ClassVar[str] = (
        "the entry point of a Define program must be a constructor"
    )
