// Rejected: clippy::single_match_else
// Rejected in mutation runs: nothing
//! A match arm deleted, which leaves a match that `if let` could write.

pub fn skip_spaces(bytes: &mut std::iter::Peekable<std::str::Bytes<'_>>) -> bool {
    let mut skipped = false;
    loop {
        match bytes.peek() {
            Some(b' ') => {
                bytes.next();
                skipped = true;
            }
            _ => {
                let Some(b'\t') = bytes.peek() else {
                    return skipped;
                };
                bytes.next();
            }
        }
    }
}
