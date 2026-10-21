from __future__ import annotations

from tools import rust_source


def _question_mark_offset(
    source: rust_source.RustSource, text: str, marker: str
) -> int:
    line_index = next(
        index for index, line in enumerate(text.splitlines()) if marker in line
    )
    line = text.splitlines()[line_index]
    column = len(line[: line.index(marker) + len(marker) - 1].encode()) + 1
    return source.offset(line_index + 1, column)


def test_functions_have_their_impl_type_and_whether_they_return_py_result():
    source = rust_source.RustSource(
        "impl<'py> AstBuilder<'py> {\n"
        + "    pub fn location(&self) -> PyResult<Location<'py>> {\n"
        + "        Ok(Location)\n"
        + "    }\n"
        + "}\n"
        + "impl<'py> PythonArgument<'py> for Bound<'py, PyString> {\n"
        + "    fn as_argument(&self, apply: impl Fn(u8) -> PyResult<u8>) -> u8 {\n"
        + "        0\n"
        + "    }\n"
        + "}\n"
        + "trait Node {\n"
        + "    fn into_object(self) -> PyResult<u8>;\n"
        + "}\n"
        + "fn split(text: &str) -> impl Iterator<Item = &str> {\n"
        + "    text.split(':')\n"
        + "}\n"
        + "fn generic<T>(value: T) -> PyResult<T>\n"
        + "where\n"
        + "    T: Copy,\n"
        + "{\n"
        + "    Ok(value)\n"
        + "}\n"
    )

    assert source.functions == [
        rust_source.RustFunction(
            name="location", impl_type="AstBuilder", returns_python_result=True
        ),
        rust_source.RustFunction(
            name="as_argument", impl_type="Bound", returns_python_result=False
        ),
        rust_source.RustFunction(
            name="into_object", impl_type=None, returns_python_result=True
        ),
        rust_source.RustFunction(
            name="split", impl_type=None, returns_python_result=False
        ),
        rust_source.RustFunction(
            name="generic", impl_type=None, returns_python_result=True
        ),
    ]


def test_comments_and_literals_do_not_declare_functions():
    source = rust_source.RustSource(
        "// fn commented() -> PyResult<u8> {\n"
        + "/* fn outer() {\n"
        + "/* fn nested() */ } */\n"
        + 'const TEXT: &str = "fn quoted() { \\" }";\n'
        + 'const RAW: &str = r#"fn raw() { "# ;\n'
        + 'const BYTES: &[u8] = b"fn bytes() {";\n'
        + "const BRACE: char = '{';\n"
        + "const QUOTE: u8 = b'\"';\n"
        + "fn real<'a>(text: &'a str) -> PyResult<&'a str> {\n"
        + "    Ok(text)\n"
        + "}\n"
    )

    assert source.functions == [
        rust_source.RustFunction(
            name="real", impl_type=None, returns_python_result=True
        )
    ]


def test_enclosing_function_is_the_innermost_function_with_the_offset():
    text = (
        "fn outer() -> ParseResult<u8> {\n"
        + "    fn inner() -> PyResult<u8> {\n"
        + "        python()?;\n"
        + "    }\n"
        + "    parse()?;\n"
        + "}\n"
    )
    source = rust_source.RustSource(text)

    assert source.enclosing_function(
        _question_mark_offset(source, text, "python()?")
    ) == rust_source.RustFunction(
        name="inner", impl_type=None, returns_python_result=True
    )
    assert source.enclosing_function(
        _question_mark_offset(source, text, "parse()?")
    ) == rust_source.RustFunction(
        name="outer", impl_type=None, returns_python_result=False
    )
    assert source.enclosing_function(0) is None


def test_enclosing_function_is_none_in_a_closure():
    text = (
        "fn outer() -> PyResult<u8> {\n"
        + "    let parse_all = || -> ParseResult<u8> {\n"
        + "        braced()?;\n"
        + "    };\n"
        + "    values.map(|value| unbraced(value)?);\n"
        + "    values.map_err(|error| convert(error))?;\n"
        + "    if first || second {\n"
        + "        condition()?;\n"
        + "    }\n"
        + "}\n"
    )
    source = rust_source.RustSource(text)

    assert (
        source.enclosing_function(_question_mark_offset(source, text, "braced()?"))
        is None
    )
    assert (
        source.enclosing_function(
            _question_mark_offset(source, text, "unbraced(value)?")
        )
        is None
    )
    outer = rust_source.RustFunction(
        name="outer", impl_type=None, returns_python_result=True
    )
    assert (
        source.enclosing_function(_question_mark_offset(source, text, "error))?"))
        == outer
    )
    assert (
        source.enclosing_function(_question_mark_offset(source, text, "condition()?"))
        == outer
    )


def test_callee_before_names_the_called_function():
    text = (
        "fn parse() -> ParseResult<u8> {\n"
        + "    self.ast.location(start, end)?;\n"
        + "    AstBuilder::new(py)?;\n"
        + "    module.add_class::<ParseResult>()?;\n"
        + "    wrap_pyfunction!(parse, module)?;\n"
        + "    self.ast.position_definition(\n"
        + "        location,\n"
        + "    )?;\n"
        + "    first_run?;\n"
        + "    (value)?;\n"
        + "    apply::<fn() -> u8>()?;\n"
        + "}\n"
    )
    source = rust_source.RustSource(text)

    assert source.callee_before(
        _question_mark_offset(source, text, "end)?")
    ) == rust_source.Callee(name="location", qualifier=None)
    assert source.callee_before(
        _question_mark_offset(source, text, "new(py)?")
    ) == rust_source.Callee(name="new", qualifier="AstBuilder")
    assert source.callee_before(
        _question_mark_offset(source, text, "<ParseResult>()?")
    ) == rust_source.Callee(name="add_class", qualifier=None)
    assert source.callee_before(
        _question_mark_offset(source, text, "module)?")
    ) == rust_source.Callee(name="wrap_pyfunction", qualifier=None)
    assert source.callee_before(
        _question_mark_offset(source, text, "    )?")
    ) == rust_source.Callee(name="position_definition", qualifier=None)
    assert (
        source.callee_before(_question_mark_offset(source, text, "first_run?")) is None
    )
    assert source.callee_before(_question_mark_offset(source, text, "(value)?")) is None
    assert source.callee_before(
        _question_mark_offset(source, text, "u8>()?")
    ) == rust_source.Callee(name="apply", qualifier=None)


def test_callee_before_a_turbofish_without_a_path_is_none():
    text = "fn parse() -> ParseResult<u8> {\n    convert<u8>()?;\n}\n"
    source = rust_source.RustSource(text)

    assert source.callee_before(_question_mark_offset(source, text, "()?")) is None


def test_crate_says_whether_every_function_a_callee_may_name_returns_py_result():
    crate = rust_source.RustCrate(
        [
            rust_source.RustSource(
                "impl AstBuilder {\n"
                + "    fn new() -> PyResult<Self> {}\n"
                + "    fn location(&self) -> PyResult<u8> {}\n"
                + "}\n"
                + "impl Scanner {\n"
                + "    fn new() -> Self {}\n"
                + "}\n"
            ),
            rust_source.RustSource("fn location() -> PyResult<u8> {}\n"),
        ]
    )

    assert crate.returns_python_result(
        rust_source.Callee(name="location", qualifier=None)
    )
    assert crate.returns_python_result(
        rust_source.Callee(name="new", qualifier="AstBuilder")
    )
    assert not crate.returns_python_result(
        rust_source.Callee(name="new", qualifier=None)
    )
    assert (
        crate.returns_python_result(rust_source.Callee(name="getattr", qualifier=None))
        is None
    )
    assert (
        crate.returns_python_result(rust_source.Callee(name="new", qualifier="PyTuple"))
        is None
    )


def test_offset_counts_byte_columns():
    source = rust_source.RustSource("// é\nfn f() {}\n")

    assert source.offset(1, 6) == 4
    assert source.offset(2, 1) == 5
