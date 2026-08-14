import hashlib
from pathlib import Path

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


def test_class_name_can_match_imported_name():
    converter = naming.NameConverter()
    assert converter.class_name(define_path.DefinePath("class_var")) == "ClassVar"


def test_class_name_can_match_builtin_name():
    converter = naming.NameConverter()
    assert converter.class_name(define_path.DefinePath("type_error")) == "TypeError"


def test_class_name_cached():
    converter = naming.NameConverter()
    first = converter.class_name(define_path.DefinePath("class_var"))
    second = converter.class_name(define_path.DefinePath("class_var"))
    assert first == second == "ClassVar"


def test_class_names_in_different_modules_can_match():
    converter = naming.NameConverter()
    first = converter.class_name(define_path.DefinePath("class_var"))
    second = converter.class_name(define_path.DefinePath("class_var_"))
    assert first == second == "ClassVar"


def test_guarantees_class_reference():
    converter = naming.NameConverter()
    assert converter.guarantees_class_reference(
        _action_name("/worker")
    ) == naming.ClassReference(
        class_name="WorkerGuarantees",
        module_name="local.my_domain_com.my_lib.worker",
    )


def test_guarantees_class_name_can_match_definition_in_another_module():
    converter = naming.NameConverter()
    definition_class = converter.class_name(define_path.DefinePath("worker_guarantees"))
    guarantees_class = converter.guarantees_class_reference(_action_name("/worker"))
    assert definition_class == guarantees_class.class_name == "WorkerGuarantees"


def test_class_reference_cached():
    converter = naming.NameConverter()
    action_name = _action_name("/worker")
    first = converter.class_reference(action_name)
    second = converter.class_reference(action_name)
    assert first is second


def test_module_name_short_component_unchanged():
    converter = naming.NameConverter()
    name_content = _action_name("/worker").name_content
    assert converter.module_name(name_content) == "local.my_domain_com.my_lib.worker"


def test_module_name_truncates_long_component():
    converter = naming.NameConverter()
    long_segment = "x" * 300
    name_content = _action_name(f"/{long_segment}").name_content
    module_name = converter.module_name(name_content)
    *_, last_component = module_name.split(".")
    digest = hashlib.blake2b(long_segment.encode(), digest_size=8).hexdigest()
    assert last_component == "x" * 238 + "_" + digest
    assert len(last_component.encode()) == 255


def test_module_name_distinct_long_components_stay_distinct():
    converter = naming.NameConverter()
    # Both segments share the same 238-byte truncated prefix ("x" * 238), so
    # only the appended digest of the full segment can tell them apart.
    first_segment = "x" * 300
    second_segment = "x" * 238 + "y" * 62
    first = converter.module_name(_action_name(f"/{first_segment}").name_content)
    second = converter.module_name(_action_name(f"/{second_segment}").name_content)
    assert first != second


def test_file_path_for_module_basic():
    assert naming.file_path_for_module("a.b.c") == Path("a", "b", "c", "__init__.py")


def test_file_path_for_module_matches_truncated_import_name():
    converter = naming.NameConverter()
    long_segment = "x" * 300
    name_content = _action_name(f"/{long_segment}").name_content
    module_name = converter.module_name(name_content)
    file_path = naming.file_path_for_module(module_name)
    assert file_path == Path(*module_name.split(".")) / "__init__.py"
    assert all(len(part.encode()) <= 255 for part in file_path.parts[:-1])


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
