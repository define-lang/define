import ast
from pathlib import Path

import pytest

from tools import check_python_deps


def test_analyze_imports_prefers_imported_module_to_package():
    tree = ast.parse("import define.compiler.ast\nfrom define.compiler import parser\n")

    assert check_python_deps.analyze_imports(
        tree,
        {
            "define.compiler": "//define/compiler:compiler",
            "define.compiler.ast": "//define/compiler:ast",
            "define.compiler.parser": "//define/compiler:parser",
        },
        {},
    ) == check_python_deps.ImportAnalysis(
        frozenset(
            {
                "//define/compiler:ast",
                "//define/compiler:parser",
            }
        ),
        frozenset(),
    )


def test_analyze_imports_includes_package_for_exported_symbol():
    tree = ast.parse("from package import owned_module, exported_symbol\n")

    assert check_python_deps.analyze_imports(
        tree,
        {
            "package": "//package:package",
            "package.owned_module": "//package:owned_module",
        },
        {},
    ) == check_python_deps.ImportAnalysis(
        frozenset({"//package:package", "//package:owned_module"}),
        frozenset(),
    )


def test_analyze_imports_reports_unresolved_package_in_mixed_from_import():
    tree = ast.parse("from unknown import owned_module, exported_symbol\n")

    assert check_python_deps.analyze_imports(
        tree, {"unknown.owned_module": "//unknown:owned_module"}, {}
    ) == check_python_deps.ImportAnalysis(
        frozenset({"//unknown:owned_module"}), frozenset({"unknown"})
    )


def test_replace_deps_adds_sorted_multiline_attribute():
    rule = [
        "py_library(\n",
        '    name = "example",\n',
        '    srcs = ["example.py"],\n',
        ")\n",
    ]

    assert check_python_deps.replace_deps(
        rule,
        frozenset({"//z:z", "//a:a"}),
        check_python_deps.PythonTarget(
            label="//example:example",
            rule_class="py_library",
            build_file=Path("BUILD.bazel"),
            source=Path("example.py"),
            deps=frozenset(),
        ),
    ) == [
        "py_library(\n",
        '    name = "example",\n',
        '    srcs = ["example.py"],\n',
        "    deps = [\n",
        '        "//a:a",\n',
        '        "//z:z",\n',
        "    ],\n",
        ")\n",
    ]


def test_module_name_uses_package_for_init():
    assert check_python_deps.module_name(Path("define/compiler/__init__.py")) == (
        "define.compiler"
    )


def test_analyze_imports_ignores_standard_library_for_unresolved_imports():
    tree = ast.parse("import pathlib\nimport unknown_package\n")

    assert check_python_deps.analyze_imports(
        tree, {}, {}
    ) == check_python_deps.ImportAnalysis(frozenset(), frozenset({"unknown_package"}))


def test_fixture_names_include_named_and_ordinary_fixtures():
    tree = ast.parse(
        """@pytest.fixture
def ordinary(): pass
@pytest.fixture(name="renamed")
def original(): pass
"""
    )

    assert check_python_deps.fixture_names(tree) == {"ordinary", "renamed"}


def test_requested_fixture_names_include_method_and_keyword_only_parameters():
    tree = ast.parse(
        """class TestExample:
    def test_example(self, fixture, *, keyword_fixture): pass
"""
    )

    assert check_python_deps.requested_fixture_names(tree) == {
        "self",
        "fixture",
        "keyword_fixture",
    }


def test_requested_fixture_names_ignore_ordinary_helper_parameters():
    tree = ast.parse(
        """def helper(not_a_fixture): pass
@pytest.fixture
def actual_fixture(fixture_dependency): pass
"""
    )

    assert check_python_deps.requested_fixture_names(tree) == {"fixture_dependency"}


def test_requested_fixture_names_ignore_nested_tests_and_uncollected_classes():
    tree = ast.parse(
        """def helper():
    def test_nested(not_a_fixture): pass
class Example:
    def test_method(also_not_a_fixture): pass
"""
    )

    assert check_python_deps.requested_fixture_names(tree) == set()


def test_import_analysis_resolves_generated_and_external_modules():
    tree = ast.parse("import define.config.project.config_pb2\nimport regex\n")

    assert check_python_deps.analyze_imports(
        tree,
        {
            "define.config.project.config_pb2": (
                "//define/config/project:config_proto_py"
            )
        },
        {"regex": "@pypi//regex"},
    ) == check_python_deps.ImportAnalysis(
        frozenset(
            {
                "//define/config/project:config_proto_py",
                "@pypi//regex",
            }
        ),
        frozenset(),
    )


def test_repository_analysis_updates_mixed_imports_and_conftest_deps(
    tmp_path: Path,
):
    package = tmp_path / "define/example"
    child_package = package / "child"
    child_package.mkdir(parents=True)
    _ = (package / "__init__.py").write_text("exported_symbol = object()\n")
    _ = (package / "owned_module.py").write_text("")
    _ = (package / "conftest.py").write_text(
        "import pytest\n@pytest.fixture\ndef shared_fixture(): pass\n"
    )
    _ = (package / "example_test.py").write_text(
        """from define.example import owned_module, exported_symbol
def test_example(shared_fixture): pass
"""
    )
    _ = (child_package / "child_test.py").write_text(
        "def test_child(shared_fixture): pass\n"
    )
    (tmp_path / "define/unrelated").mkdir()
    _ = (tmp_path / "define/unrelated/unrelated_test.py").write_text(
        "def test_unrelated(): pass\n"
    )
    _ = (package / "BUILD.bazel").write_text(
        """py_library(name = "example", srcs = ["__init__.py"])
py_library(name = "owned_module", srcs = ["owned_module.py"])
py_library(name = "conftest", srcs = ["conftest.py"], deps = ["@pypi//pytest"])
py_test(name = "example_test", srcs = ["example_test.py"], deps = ["//old:unused"])
"""
    )
    _ = (child_package / "BUILD.bazel").write_text(
        'py_test(name = "child_test", srcs = ["child_test.py"])\n'
    )
    _ = (tmp_path / "define/unrelated/BUILD.bazel").write_text(
        'py_test(name = "unrelated_test", srcs = ["unrelated_test.py"])\n'
    )

    repository = check_python_deps.load_repository(tmp_path)
    results = check_python_deps.analyze_targets(repository, [package / "conftest.py"])

    assert [change.target.label for change in results.changes] == [
        "//define/example:example_test",
        "//define/example/child:child_test",
    ]
    assert results.changes[0].expected == {
        "//define/example:conftest",
        "//define/example:example",
        "//define/example:owned_module",
    }
    assert results.changes[1].expected == {"//define/example:conftest"}


def test_repository_analysis_removes_conftest_dep_after_fixture_removal(
    tmp_path: Path,
):
    target = check_python_deps.PythonTarget(
        "//define/example:example_test",
        "py_test",
        Path("define/example/BUILD.bazel"),
        Path("define/example/example_test.py"),
        frozenset({"//define/example:conftest"}),
    )
    repository = check_python_deps.RepositoryAnalysis(
        tmp_path,
        (
            check_python_deps.ParsedTarget(
                target, ast.parse("def test_example(removed_fixture): pass\n")
            ),
        ),
        {"define.example.conftest": "//define/example:conftest"},
        {},
        {Path("define/example/conftest.py"): frozenset()},
    )

    results = check_python_deps.analyze_targets(
        repository, [Path("define/example/conftest.py")]
    )

    assert results.changes == (
        check_python_deps.DependencyChanges(target, frozenset()),
    )


def test_report_results_rewrites_multiple_targets_and_preserves_kept_deps(
    tmp_path: Path,
):
    package = tmp_path / "tools"
    package.mkdir()
    build_file = package / "BUILD.bazel"
    _ = build_file.write_text(
        """py_library(
    name = "first",
    srcs = ["first.py"],
    deps = [
        "@pypi//regex",  # keep
    ],
)
py_library(
    name = "second",
    srcs = ["second.py"],
    deps = ["//old:unused"],
)
"""
    )
    first = check_python_deps.PythonTarget(
        "//tools:first",
        "py_library",
        Path("tools/BUILD.bazel"),
        Path("tools/first.py"),
        frozenset({"@pypi//regex"}),
        frozenset({"@pypi//regex"}),
    )
    second = check_python_deps.PythonTarget(
        "//tools:second",
        "py_library",
        Path("tools/BUILD.bazel"),
        Path("tools/second.py"),
        frozenset({"//old:unused"}),
    )
    repository = check_python_deps.RepositoryAnalysis(tmp_path, (), {}, {}, {})
    results = check_python_deps.AnalysisResults(
        (
            check_python_deps.DependencyChanges(first, frozenset({"@pypi//regex"})),
            check_python_deps.DependencyChanges(second, frozenset()),
        ),
        {},
    )

    assert check_python_deps.report_results(repository, results, check_only=False) == 1
    contents = build_file.read_text()
    assert '"@pypi//regex",  # keep' in contents
    assert "//old:unused" not in contents
    assert 'name = "second"' in contents


def test_load_repository_rejects_python_targets_with_multiple_sources(
    tmp_path: Path,
):
    package = tmp_path / "tools"
    package.mkdir()
    _ = (package / "BUILD.bazel").write_text(
        'py_library(name = "example", srcs = ["first.py", "second.py"])\n'
    )

    with pytest.raises(
        ValueError,
        match="tools:example must have exactly one Python source",
    ):
        _ = check_python_deps.load_repository(tmp_path)


def test_load_repository_rejects_malformed_keep_dependency(tmp_path: Path):
    package = tmp_path / "tools"
    package.mkdir()
    _ = (package / "example.py").write_text("")
    _ = (package / "BUILD.bazel").write_text(
        """py_library(
    name = "example",
    srcs = ["example.py"],
    deps = [
        invalid_label,  # keep
    ],
)
"""
    )

    with pytest.raises(ValueError, match="Invalid # keep dependency"):
        _ = check_python_deps.load_repository(tmp_path)
