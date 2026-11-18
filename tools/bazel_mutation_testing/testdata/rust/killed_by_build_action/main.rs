//! Writes a greeting to the file its argument names, and fails when the
//! greeting is wrong, as a code generator fails on bad input.

use std::process::ExitCode;

const fn greeting() -> &'static str {
    "hello"
}

fn main() -> ExitCode {
    let text = greeting();
    if text != "hello" {
        return ExitCode::FAILURE;
    }
    let Some(path) = std::env::args().nth(1) else {
        return ExitCode::FAILURE;
    };
    if std::fs::write(path, text).is_err() {
        return ExitCode::FAILURE;
    }
    ExitCode::SUCCESS
}
