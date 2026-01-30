<!--
Instructions for humans and AI agents modifying this file:

This is a concise description of exactly what the compiler needs to do in
order to correctly implement Define's syntax and semantics. It is a specification
for a programming language called Define.

Nothing may be added to this spec unless there is first a Define Language Proposal
for that aspect of the language.

This file does not contain justifications or reasons for why decisions were made.
Instead, sections link to the relevant Define Language Proposals, like this:

## Naming

Proposals:
- [DLP 1: Types of Names](../proposals/00001-types-of-names.md)
- [DLP 2: Universes](../proposals/00002-universes.md)
- [DLP 3: Authorities](../proposals/00003-authorities.md)

Then after that the section contains concise wording, EBNF specifications, and
whatever else is needed to convey the precise details the compiler needs to know.

If a parent header lists a Define Language Proposal, the subheaders do not also
need to list that proposal. However, some DLPs will only be relevant to a subheader,
and so would be listed there.

This comment may not be modified by AI agents.
-->

# The Define Language Specification

## Introduction

This specification defines the syntax and semantics needed to compile Define
programs.

Every aspect of this specification is covered by a
[Define Language Proposal](../proposals/). Sections of this doc link to those
proposals, which contain the rationale behind Define's language decisions. This
specification contains only the specifics required for the compiler to correctly
implement Define.

The concepts behind Define are described in
[The Conceptual Basis of Define](concepts.md). It is expected that the reader
has at least a general understanding of the concepts described there.

At a high level, the language's design is guided also by our
[Principles](principles.md) and [Requirements](requirements.md).

## A Note About Undefined Behavior

Define is intended to be a very strict language. Any syntax or semantics not
specified in this spec is an error.

Define has no "undefined behavior." If the compiler encounters a situation not
described in this spec, it will provide an error and refuse to compile the
program.

In the case that there is a bug in the compiler and it does not behave according
to the spec, future versions of Define may fix that bug even if it causes
existing programs to fail to compile (that is, even if it breaks backward
compatibility).
