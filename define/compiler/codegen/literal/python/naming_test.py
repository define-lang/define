from pathlib import PurePosixPath

from define.compiler.codegen.literal.python import naming


def test_class_name_normal():
    converter = naming.NameConverter()
    assert converter.class_name(PurePosixPath("normal")) == "Normal"


def test_class_name_multi_segment():
    converter = naming.NameConverter()
    assert converter.class_name(PurePosixPath("my_action")) == "MyAction"


def test_class_name_mangles_classvar():
    converter = naming.NameConverter()
    assert converter.class_name(PurePosixPath("class_var")) == "ClassVar_"


def test_class_name_mangles_builtin():
    converter = naming.NameConverter()
    assert converter.class_name(PurePosixPath("type_error")) == "TypeError_"


def test_class_name_cached():
    converter = naming.NameConverter()
    first = converter.class_name(PurePosixPath("class_var"))
    second = converter.class_name(PurePosixPath("class_var"))
    assert first == second == "ClassVar_"


def test_class_name_double_conflict():
    converter = naming.NameConverter()
    first = converter.class_name(PurePosixPath("class_var"))
    second = converter.class_name(PurePosixPath("class_var_"))
    assert first == "ClassVar_"
    assert second == "ClassVar__"


def test_local_name_normal():
    local = naming.LocalNameConverter()
    assert local.convert("typing") == "typing"


def test_local_name_self():
    local = naming.LocalNameConverter()
    assert local.convert("self") == "self_"


def test_local_name_literal():
    local = naming.LocalNameConverter()
    assert local.convert("literal") == "literal_"


def test_local_name_keyword():
    local = naming.LocalNameConverter()
    assert local.convert("class") == "class_"


def test_local_name_builtin():
    local = naming.LocalNameConverter()
    assert local.convert("super") == "super_"


def test_local_name_cached():
    local = naming.LocalNameConverter()
    first = local.convert("self")
    second = local.convert("self")
    assert first == second == "self_"


def test_local_name_double_conflict():
    local = naming.LocalNameConverter()
    first = local.convert("self")
    second = local.convert("self_")
    assert first == "self_"
    assert second == "self__"


def test_local_name_double_conflict_reverse_order():
    local = naming.LocalNameConverter()
    first = local.convert("self_")
    second = local.convert("self")
    assert first == "self_"
    assert second == "self__"
