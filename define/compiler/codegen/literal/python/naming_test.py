from __future__ import annotations

import hashlib
from pathlib import Path

from define.compiler import ast, name_types
from define.compiler.codegen.literal.python import naming

_LOCATION = ast.start_of_file_location()
_FQUN = ast.Fqun(
    multiverse=None,
    authority=ast.Authority(name="my.domain.com", location=_LOCATION),
    universe=ast.Universe(name="my_lib", location=_LOCATION),
    location=_LOCATION,
)


def _typed_name(
    name_type: name_types.NameType, path: str
) -> ast.GlobalTypedNameInDefinition:
    return ast.GlobalTypedNameInDefinition(
        name_type=name_type,
        name_content=ast.DefinitionGlobalNameContent(
            fqun=_FQUN,
            path=ast.GlobalPathName(name=path, location=_LOCATION),
            location=_LOCATION,
        ),
        location=_LOCATION,
    )


def _action_name(path: str) -> ast.GlobalTypedNameInDefinition:
    return _typed_name(name_types.NameType.ACTION, path)


def test_class_name_normal():
    converter = naming.NameConverter()
    assert converter.class_name(_action_name("/normal")) == "NormalAction"


def test_class_name_multi_segment():
    converter = naming.NameConverter()
    assert converter.class_name(_action_name("/my_thing")) == "MyThingAction"


def test_class_names_at_one_path_end_in_their_name_types():
    converter = naming.NameConverter()
    assert converter.class_name(
        _typed_name(name_types.NameType.POSITION, "/thing")
    ) == ("ThingPosition")
    assert converter.class_name(_typed_name(name_types.NameType.ACTION, "/thing")) == (
        "ThingAction"
    )
    assert converter.class_name(_typed_name(name_types.NameType.VALUE, "/thing")) == (
        "ThingValue"
    )


def test_class_name_cannot_match_imported_name():
    converter = naming.NameConverter()
    assert converter.class_name(_action_name("/class_var")) == "ClassVarAction"


def test_class_name_cached():
    converter = naming.NameConverter()
    first = converter.class_name(_action_name("/class_var"))
    second = converter.class_name(_action_name("/class_var"))
    assert first == second == "ClassVarAction"


def test_class_names_in_different_modules_can_match():
    converter = naming.NameConverter()
    first = converter.class_name(_action_name("/class_var"))
    second = converter.class_name(_action_name("/class__var"))
    assert first == second == "ClassVarAction"


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


def test_class_reference_in_standard_universe():
    converter = naming.NameConverter()
    value_name = ast.GlobalTypedNameInDefinition(
        name_type=name_types.NameType.VALUE,
        name_content=ast.DefinitionGlobalNameContent(
            fqun=ast.Fqun(
                multiverse=None,
                authority=None,
                universe=ast.Universe(name="standard", location=_LOCATION),
                location=_LOCATION,
            ),
            path=ast.GlobalPathName(name="/number/rational", location=_LOCATION),
            location=_LOCATION,
        ),
        location=_LOCATION,
    )
    assert converter.class_reference(value_name) == naming.ClassReference(
        module_name="standard.number.rational", class_name="NumberRationalValue"
    )


def test_module_name_escapes_keyword_component():
    converter = naming.NameConverter()
    name_content = _action_name("/if").name_content
    assert converter.module_name(name_content) == "local.my_domain_com.my_lib.if_"


def test_module_name_escapes_component_ending_in_underscore():
    converter = naming.NameConverter()
    name_content = _action_name("/if_").name_content
    assert converter.module_name(name_content) == "local.my_domain_com.my_lib.if__"


def test_module_name_is_shared_by_definitions_at_one_path():
    converter = naming.NameConverter()
    position = _typed_name(name_types.NameType.POSITION, "/thing").name_content
    action = _typed_name(name_types.NameType.ACTION, "/thing").name_content
    assert converter.module_name(position) == converter.module_name(action)


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


def _encoding_operation_name(path: str) -> ast.GlobalTypedNameInDefinition:
    return _typed_name(name_types.NameType.ENCODING_OPERATION, path)


def test_function_reference_is_in_parent_module():
    converter = naming.NameConverter()
    assert converter.function_reference(
        _encoding_operation_name("/number/add")
    ) == naming.FunctionReference(
        function_name="add", module_name="local.my_domain_com.my_lib.number"
    )


def test_function_reference_at_universe_root():
    converter = naming.NameConverter()
    assert converter.function_reference(
        _encoding_operation_name("/add")
    ) == naming.FunctionReference(
        function_name="add", module_name="local.my_domain_com.my_lib"
    )


def test_function_name_escapes_keyword():
    converter = naming.NameConverter()
    assert (
        converter.function_reference(
            _encoding_operation_name("/number/if")
        ).function_name
        == "if_"
    )


def test_package_named_like_function_gets_underscore():
    converter = naming.NameConverter()
    converter.reserve_function_name(_encoding_operation_name("/number/add"))
    count = _typed_name(name_types.NameType.POSITION, "/number/add/count").name_content
    assert (
        converter.module_name(count) == "local.my_domain_com.my_lib.number.add_.count"
    )


def test_definition_at_function_path_gets_underscore():
    converter = naming.NameConverter()
    converter.reserve_function_name(_encoding_operation_name("/number/add"))
    position = _typed_name(name_types.NameType.POSITION, "/number/add").name_content
    assert converter.module_name(position) == "local.my_domain_com.my_lib.number.add_"


def test_package_under_function_with_underscored_sibling_stays_distinct():
    converter = naming.NameConverter()
    converter.reserve_function_name(_encoding_operation_name("/number/if"))
    keyword_package = _typed_name(name_types.NameType.POSITION, "/number/if/count")
    underscored_package = _typed_name(name_types.NameType.POSITION, "/number/if_/count")
    assert (
        converter.module_name(keyword_package.name_content)
        == "local.my_domain_com.my_lib.number.if__.count"
    )
    assert (
        converter.module_name(underscored_package.name_content)
        == "local.my_domain_com.my_lib.number.if___.count"
    )


def test_package_without_function_keeps_its_name():
    converter = naming.NameConverter()
    converter.reserve_function_name(_encoding_operation_name("/other/add"))
    count = _typed_name(name_types.NameType.POSITION, "/number/add/count").name_content
    assert converter.module_name(count) == "local.my_domain_com.my_lib.number.add.count"


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
    allocator = naming.LocalNameAllocator()
    assert allocator.allocate("name") == "name"


def test_name_allocator_underscores_repeated_candidates():
    allocator = naming.LocalNameAllocator()
    assert [allocator.allocate("name") for _ in range(3)] == [
        "name",
        "name_",
        "name__",
    ]


def test_name_allocator_underscores_reserved_names():
    allocator = naming.LocalNameAllocator()
    assert allocator.allocate("class") == "class_"
    assert allocator.allocate("class") == "class__"
    assert allocator.allocate("class") == "class___"
    assert allocator.allocate("self") == "self_"
    assert allocator.allocate("literal") == "literal_"


def test_name_allocator_underscores_imported_module_names():
    allocator = naming.LocalNameAllocator()
    allocator.reserve_module_first_names(["package.module"])
    assert allocator.allocate("package") == "package_"
    assert allocator.allocate("package") == "package__"


def test_name_allocator_underscores_collisions_with_reserved_name_results():
    allocator = naming.LocalNameAllocator()
    assert allocator.allocate("class") == "class_"
    assert allocator.allocate("class_") == "class__"
    assert allocator.allocate("class_") == "class___"


def test_name_allocator_skips_conflicting_source_suffixes():
    allocator = naming.LocalNameAllocator()
    assert allocator.allocate("name") == "name"
    assert allocator.allocate("name_") == "name_"
    assert allocator.allocate("name__") == "name__"
    assert allocator.allocate("name") == "name___"


def test_name_allocator_skips_conflicting_generated_suffixes():
    allocator = naming.LocalNameAllocator()
    assert allocator.allocate("name") == "name"
    assert allocator.allocate("name") == "name_"
    assert allocator.allocate("name_") == "name__"


def test_name_allocators_are_independent_namespaces():
    first = naming.LocalNameAllocator()
    second = naming.LocalNameAllocator()
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
