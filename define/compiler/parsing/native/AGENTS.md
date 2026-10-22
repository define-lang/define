# Native Parser Instructions

## Hot and Cold Paths

Every function in the parser is either on the happy path, which parses valid
source, or on an error path, which only runs once the parser has found a
mistake. The attributes say which:

- A function that only runs on an error path is `#[cold]`. Use it only to build
  an error, never to parse valid source.
- A `#[cold]` function that a happy-path function calls is also
  `#[inline(never)]`, so its code stays out of the happy path. A `#[cold]`
  function that only other `#[cold]` functions call needs only `#[cold]`.
- A function with neither attribute is on the happy path. It must do only the
  work that valid source needs; anything that only an error needs goes in a
  `#[cold]` function.
