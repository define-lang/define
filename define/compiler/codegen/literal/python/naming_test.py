from define.compiler import ast
from define.compiler.codegen.literal.python import naming
from define.compiler.data_structures import define_path

_LOCATION = ast.start_of_file_location()
_FQUN = ast.Fqun(
    multiverse=None,
    authority=ast.Authority(name="my.domain.com", location=_LOCATION),
    universe=ast.Universe(name="my_lib", location=_LOCATION),
    location=_LOCATION,
)


def _action_name(path: str) -> ast.GlobalTypedNameInDefinition:
    return ast.GlobalTypedNameInDefinition(
        name_type=ast.NameType.ACTION,
        name_content=ast.DefinitionGlobalNameContent(
            fqun=_FQUN,
            path=ast.GlobalPathName(name=path, location=_LOCATION),
            location=_LOCATION,
        ),
        location=_LOCATION,
    )


def test_class_name_normal():
    converter = naming.NameConverter()
    assert converter.class_name(define_path.DefinePath("normal")) == "Normal"


def test_class_name_multi_segment():
    converter = naming.NameConverter()
    assert converter.class_name(define_path.DefinePath("my_action")) == "MyAction"


def test_class_name_mangles_classvar():
    converter = naming.NameConverter()
    assert converter.class_name(define_path.DefinePath("class_var")) == "ClassVar_"


def test_class_name_mangles_builtin():
    converter = naming.NameConverter()
    assert converter.class_name(define_path.DefinePath("type_error")) == "TypeError_"


def test_class_name_cached():
    converter = naming.NameConverter()
    first = converter.class_name(define_path.DefinePath("class_var"))
    second = converter.class_name(define_path.DefinePath("class_var"))
    assert first == second == "ClassVar_"


def test_class_name_double_conflict():
    converter = naming.NameConverter()
    first = converter.class_name(define_path.DefinePath("class_var"))
    second = converter.class_name(define_path.DefinePath("class_var_"))
    assert first == "ClassVar_"
    assert second == "ClassVar__"


def test_guarantees_class_reference():
    converter = naming.NameConverter()
    assert converter.guarantees_class_reference(
        _action_name("/worker")
    ) == naming.ClassReference(
        class_name="WorkerGuarantees",
        module_name="local.my_domain_com.my_lib.worker",
    )


def test_guarantees_class_reference_is_stable():
    converter = naming.NameConverter()
    first = converter.guarantees_class_reference(_action_name("/worker"))
    second = converter.guarantees_class_reference(_action_name("/worker"))
    assert (
        first
        == second
        == naming.ClassReference(
            class_name="WorkerGuarantees",
            module_name="local.my_domain_com.my_lib.worker",
        )
    )


def test_guarantees_class_reference_avoids_definition_class_conflict():
    converter = naming.NameConverter()
    definition_class = converter.class_name(define_path.DefinePath("worker_guarantees"))
    guarantees_class = converter.guarantees_class_reference(_action_name("/worker"))
    assert definition_class == "WorkerGuarantees"
    assert guarantees_class.class_name == "WorkerGuarantees_"


def test_name_allocator_preserves_first_candidate():
    allocator = naming.NameAllocator()
    assert allocator.allocate("name") == "name"


def test_name_allocator_numbers_repeated_candidates():
    allocator = naming.NameAllocator()
    assert [allocator.allocate("name") for _ in range(3)] == [
        "name",
        "name_2",
        "name_3",
    ]


def test_name_allocator_skips_conflicting_source_suffixes():
    allocator = naming.NameAllocator()
    assert allocator.allocate("name") == "name"
    assert allocator.allocate("name_2") == "name_2"
    assert allocator.allocate("name") == "name_3"


def test_name_allocator_skips_conflicting_generated_suffixes():
    allocator = naming.NameAllocator()
    assert allocator.allocate("name") == "name"
    assert allocator.allocate("name") == "name_2"
    assert allocator.allocate("name_2") == "name_2_2"


def test_name_allocator_honors_reserved_names():
    allocator = naming.NameAllocator(("action", "scheduler"))
    assert allocator.allocate("action") == "action_2"
    assert allocator.allocate("scheduler") == "scheduler_2"


def test_name_allocators_are_independent_namespaces():
    first = naming.NameAllocator()
    second = naming.NameAllocator()
    assert first.allocate("name") == "name"
    assert second.allocate("name") == "name"


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
