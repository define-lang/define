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


def test_authority_segment_simple():
    converter = naming.NameConverter()
    assert converter.authority_segment("my.domain.com") == "my_domain_com"


def test_authority_segment_with_path():
    converter = naming.NameConverter()
    assert converter.authority_segment("my.domain.com/org") == "my_domain_com_org"


def test_authority_segment_cached():
    converter = naming.NameConverter()
    first = converter.authority_segment("my.domain.com")
    second = converter.authority_segment("my.domain.com")
    assert first == second == "my_domain_com"


def test_authority_segment_conflict():
    converter = naming.NameConverter()
    first = converter.authority_segment("my.domain.com")
    second = converter.authority_segment("my-domain-com")
    assert first == "my_domain_com"
    assert second == "my_domain_com_"


def test_authority_segment_conflict_with_hyphen_and_tilde():
    converter = naming.NameConverter()
    first = converter.authority_segment("a.b")
    second = converter.authority_segment("a-b")
    third = converter.authority_segment("a~b")
    assert first == "a_b"
    assert second == "a_b_"
    assert third == "a_b__"


def test_authority_segment_conflict_with_slash():
    converter = naming.NameConverter()
    first = converter.authority_segment("a.b/c")
    second = converter.authority_segment("a-b/c")
    assert first == "a_b_c"
    assert second == "a_b_c_"
