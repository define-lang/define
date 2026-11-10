from __future__ import annotations

import typing
from pathlib import PurePosixPath

from defcl.python import error_types, errors
from define.compiler import config, constants
from define.compiler.data_structures import define_path
from define.compiler.errors import diagnostics
from source_rendering.python import rendering

if typing.TYPE_CHECKING:
    from pathlib import Path

    import pytest

_PROJECT_CONFIG_PATH = PurePosixPath(".define/project/config.defcl")
_LOCAL_DEPS_PATH = PurePosixPath(".define/deps/local.defcl")


def _write_project_config(root: Path, content: str):
    config_dir = root / ".define" / "project"
    config_dir.mkdir(parents=True, exist_ok=True)
    _ = (config_dir / "config.defcl").write_text(
        content, encoding="utf-8", newline="\n"
    )


def _write_local_deps(root: Path, content: str):
    deps_dir = root / ".define" / "deps"
    deps_dir.mkdir(parents=True, exist_ok=True)
    _ = (deps_dir / "local.defcl").write_text(content, encoding="utf-8", newline="\n")


def _write_valid_project_config(root: Path):
    _write_project_config(
        root, ('project: {\n  universe_name: "test.example.com:my_lib"\n}\n')
    )


def _load(root: define_path.DefinePath = constants.PROJECT_ROOT):
    return config.ConfigLoader(root, rendering.SourceMap()).load_project_root_config()


def _declaring_entry(universe: str, path: str) -> config.LocalDependencyEntry:
    return config.LocalDependencyEntry(
        deps_path=str(_LOCAL_DEPS_PATH),
        index=0,
        universe=universe,
        path=define_path.DefinePathFromPosix(PurePosixPath(path)),
    )


def _invalid_local_dep_field(
    field_name: str, violation_message: str
) -> config.RootConfigResult:
    return config.RootConfigResult(
        root_config=None,
        diagnostics=[
            diagnostics.ConfigViolationDiagnostic(
                config_path=str(_LOCAL_DEPS_PATH),
                field_path=("deps", "local", 0, field_name),
                violation_message=violation_message,
            )
        ],
    )


class TestLoadProjectRootConfig:
    def test_resolves_fqun_and_sub_roots(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _write_valid_project_config(tmp_path)
        _write_local_deps(
            tmp_path,
            (
                "deps: {\n"
                "  local: [\n"
                "    {\n"
                '      universe_name: "mv:define-lang.org:lib"\n'
                '      path: "vendor/lib"\n'
                "    },\n"
                "    {\n"
                '      universe_name: "mv:define-lang.org:core"\n'
                '      path: "vendor/core"\n'
                "    }\n"
                "  ]\n"
                "}\n"
            ),
        )
        monkeypatch.chdir(tmp_path)

        assert _load() == config.RootConfigResult(
            root_config=config.ProjectRootConfig(
                fqun="test.example.com:my_lib",
                sub_roots={
                    "mv:define-lang.org:lib": config.LocalDependencyEntry(
                        deps_path=str(_LOCAL_DEPS_PATH),
                        index=0,
                        universe="mv:define-lang.org:lib",
                        path=define_path.DefinePathFromPosix(
                            PurePosixPath("vendor/lib")
                        ),
                    ),
                    "mv:define-lang.org:core": config.LocalDependencyEntry(
                        deps_path=str(_LOCAL_DEPS_PATH),
                        index=1,
                        universe="mv:define-lang.org:core",
                        path=define_path.DefinePathFromPosix(
                            PurePosixPath("vendor/core")
                        ),
                    ),
                },
            ),
            diagnostics=[],
        )

    def test_missing_local_deps_resolves_empty_sub_roots(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _write_valid_project_config(tmp_path)
        monkeypatch.chdir(tmp_path)

        assert _load() == config.RootConfigResult(
            root_config=config.ProjectRootConfig(
                fqun="test.example.com:my_lib", sub_roots={}
            ),
            diagnostics=[],
        )

    def test_not_a_project_root(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.chdir(tmp_path)

        assert _load() == config.RootConfigResult(
            root_config=None,
            diagnostics=[
                diagnostics.NotRunFromProjectRootDiagnostic(
                    config_path=str(_PROJECT_CONFIG_PATH),
                )
            ],
        )

    def test_declaring_entry_universe_match_succeeds(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _write_valid_project_config(tmp_path)
        monkeypatch.chdir(tmp_path)

        assert config.ConfigLoader(
            constants.PROJECT_ROOT, rendering.SourceMap()
        ).load_project_root_config(
            _declaring_entry("test.example.com:my_lib", ".")
        ) == config.RootConfigResult(
            root_config=config.ProjectRootConfig(
                fqun="test.example.com:my_lib", sub_roots={}
            ),
            diagnostics=[],
        )

    def test_declaring_entry_universe_mismatch(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _write_valid_project_config(tmp_path)
        monkeypatch.chdir(tmp_path)

        assert config.ConfigLoader(
            constants.PROJECT_ROOT, rendering.SourceMap()
        ).load_project_root_config(
            _declaring_entry("other.example.com:other_lib", ".")
        ) == config.RootConfigResult(
            root_config=None,
            diagnostics=[
                diagnostics.SubRootFqunMismatchDiagnostic(
                    config_path=str(_PROJECT_CONFIG_PATH),
                    field_path=("project", "universe_name"),
                    expected_fqun="other.example.com:other_lib",
                    actual_fqun="test.example.com:my_lib",
                    sub_root_path=str(constants.PROJECT_ROOT),
                )
            ],
        )


class TestProjectConfig:
    def test_each_schema_error_is_a_diagnostic(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _write_project_config(
            tmp_path,
            (
                "project: {\n"
                '  universe_name: "test.example.com:my_lib"\n'
                '  universe_nam: "x"\n'
                '  owner: "y"\n'
                "}\n"
            ),
        )
        monkeypatch.chdir(tmp_path)

        result = _load()
        assert result.root_config is None
        first, second = result.diagnostics
        assert isinstance(first, errors.UnknownFieldNameDiagnostic)
        assert first.location == rendering.SourceLocation(
            line=3,
            column=3,
            end_line=3,
            end_column=14,
            file_path=str(_PROJECT_CONFIG_PATH),
        )
        assert first.kind == error_types.SemanticDiagnosticKind.UNKNOWN_FIELD_NAME
        assert first.field_name == "universe_nam"
        assert first.message_type == "define.config.project.Project"
        assert isinstance(second, errors.UnknownFieldNameDiagnostic)
        assert second.location == rendering.SourceLocation(
            line=4,
            column=3,
            end_line=4,
            end_column=7,
            file_path=str(_PROJECT_CONFIG_PATH),
        )
        assert second.kind == error_types.SemanticDiagnosticKind.UNKNOWN_FIELD_NAME
        assert second.field_name == "owner"
        assert second.message_type == "define.config.project.Project"

    def test_value_of_the_wrong_kind_is_a_diagnostic(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _write_project_config(tmp_path, ("project: {\n  universe_name: 5\n}\n"))
        monkeypatch.chdir(tmp_path)

        result = _load()
        assert result.root_config is None
        (diagnostic,) = result.diagnostics
        assert type(diagnostic) is errors.SemanticDiagnostic
        assert diagnostic.location == rendering.SourceLocation(
            line=2,
            column=18,
            end_line=2,
            end_column=18,
            file_path=str(_PROJECT_CONFIG_PATH),
        )
        assert (
            diagnostic.kind
            == error_types.SemanticDiagnosticKind.NON_STRING_FOR_STRING_FIELD
        )
        assert diagnostic.field_name == "universe_name"

    def test_empty_universe_name(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        _write_project_config(tmp_path, ('project: {\n  universe_name: ""\n}\n'))
        monkeypatch.chdir(tmp_path)

        assert _load() == config.RootConfigResult(
            root_config=None,
            diagnostics=[
                diagnostics.ConfigViolationDiagnostic(
                    config_path=str(_PROJECT_CONFIG_PATH),
                    field_path=("project", "universe_name"),
                    violation_message="must be at least 1 characters",
                )
            ],
        )

    def test_syntax_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        _write_project_config(
            tmp_path,
            ('project: {\n  universe_name "test.example.com:my_lib"\n}\n'),
        )
        monkeypatch.chdir(tmp_path)

        result = _load()
        assert result.root_config is None
        (diagnostic,) = result.diagnostics
        assert isinstance(diagnostic, errors.SyntaxDiagnostic)
        assert diagnostic.location == rendering.SourceLocation(
            line=2,
            column=16,
            end_line=2,
            end_column=16,
            file_path=str(_PROJECT_CONFIG_PATH),
        )
        assert diagnostic.kind == error_types.SyntaxDiagnosticKind.MISSING_COLON


class TestLocalDepsConfig:
    def test_missing_universe_name(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _write_valid_project_config(tmp_path)
        _write_local_deps(
            tmp_path,
            ('deps: {\n  local: [\n    {\n      path: "vendor/lib"\n    }\n  ]\n}\n'),
        )
        monkeypatch.chdir(tmp_path)

        assert _load() == _invalid_local_dep_field("universe_name", "value is required")

    def test_empty_universe_name(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        _write_valid_project_config(tmp_path)
        _write_local_deps(
            tmp_path,
            (
                "deps: {\n"
                "  local: [\n"
                "    {\n"
                '      universe_name: ""\n'
                '      path: "vendor/lib"\n'
                "    }\n"
                "  ]\n"
                "}\n"
            ),
        )
        monkeypatch.chdir(tmp_path)

        assert _load() == _invalid_local_dep_field(
            "universe_name", "must be at least 1 characters"
        )

    def test_missing_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        _write_valid_project_config(tmp_path)
        _write_local_deps(
            tmp_path,
            (
                "deps: {\n"
                "  local: [\n"
                "    {\n"
                '      universe_name: "mv:define-lang.org:lib"\n'
                "    }\n"
                "  ]\n"
                "}\n"
            ),
        )
        monkeypatch.chdir(tmp_path)

        assert _load() == _invalid_local_dep_field("path", "value is required")

    def test_absolute_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        _write_valid_project_config(tmp_path)
        _write_local_deps(
            tmp_path,
            (
                "deps: {\n"
                "  local: [\n"
                "    {\n"
                '      universe_name: "mv:define-lang.org:lib"\n'
                '      path: "/absolute/path"\n'
                "    }\n"
                "  ]\n"
                "}\n"
            ),
        )
        monkeypatch.chdir(tmp_path)

        assert _load() == _invalid_local_dep_field("path", "path must not be absolute")

    def test_dotdot_part_in_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        _write_valid_project_config(tmp_path)
        _write_local_deps(
            tmp_path,
            (
                "deps: {\n"
                "  local: [\n"
                "    {\n"
                '      universe_name: "mv:define-lang.org:lib"\n'
                '      path: "vendor/../lib"\n'
                "    }\n"
                "  ]\n"
                "}\n"
            ),
        )
        monkeypatch.chdir(tmp_path)

        assert _load() == _invalid_local_dep_field(
            "path", "path must not have a '..' part"
        )

    def test_leading_dotdot_part_in_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _write_valid_project_config(tmp_path)
        _write_local_deps(
            tmp_path,
            (
                "deps: {\n"
                "  local: [\n"
                "    {\n"
                '      universe_name: "mv:define-lang.org:lib"\n'
                '      path: "../lib"\n'
                "    }\n"
                "  ]\n"
                "}\n"
            ),
        )
        monkeypatch.chdir(tmp_path)

        assert _load() == _invalid_local_dep_field(
            "path", "path must not have a '..' part"
        )

    def test_dot_part_in_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        _write_valid_project_config(tmp_path)
        _write_local_deps(
            tmp_path,
            (
                "deps: {\n"
                "  local: [\n"
                "    {\n"
                '      universe_name: "mv:define-lang.org:lib"\n'
                '      path: "./vendor/lib"\n'
                "    }\n"
                "  ]\n"
                "}\n"
            ),
        )
        monkeypatch.chdir(tmp_path)

        assert _load() == _invalid_local_dep_field(
            "path", "path must not have a '.' part"
        )

    def test_dot_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        _write_valid_project_config(tmp_path)
        _write_local_deps(
            tmp_path,
            (
                "deps: {\n"
                "  local: [\n"
                "    {\n"
                '      universe_name: "mv:define-lang.org:lib"\n'
                '      path: "."\n'
                "    }\n"
                "  ]\n"
                "}\n"
            ),
        )
        monkeypatch.chdir(tmp_path)

        assert _load() == _invalid_local_dep_field(
            "path", "path must not have a '.' part"
        )

    def test_empty_part_in_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        _write_valid_project_config(tmp_path)
        _write_local_deps(
            tmp_path,
            (
                "deps: {\n"
                "  local: [\n"
                "    {\n"
                '      universe_name: "mv:define-lang.org:lib"\n'
                '      path: "vendor//lib"\n'
                "    }\n"
                "  ]\n"
                "}\n"
            ),
        )
        monkeypatch.chdir(tmp_path)

        assert _load() == _invalid_local_dep_field("path", "path must not contain '//'")

    def test_backslash_in_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        _write_valid_project_config(tmp_path)
        _write_local_deps(
            tmp_path,
            (
                "deps: {\n"
                "  local: [\n"
                "    {\n"
                '      universe_name: "mv:define-lang.org:lib"\n'
                '      path: "vendor\\\\lib"\n'
                "    }\n"
                "  ]\n"
                "}\n"
            ),
        )
        monkeypatch.chdir(tmp_path)

        assert _load() == _invalid_local_dep_field(
            "path", "path must not contain a backslash"
        )

    def test_dots_within_a_part_of_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _write_valid_project_config(tmp_path)
        _write_local_deps(
            tmp_path,
            (
                "deps: {\n"
                "  local: [\n"
                "    {\n"
                '      universe_name: "mv:define-lang.org:lib"\n'
                '      path: "vendor/lib..v2/.hidden"\n'
                "    }\n"
                "  ]\n"
                "}\n"
            ),
        )
        monkeypatch.chdir(tmp_path)

        assert _load() == config.RootConfigResult(
            root_config=config.ProjectRootConfig(
                fqun="test.example.com:my_lib",
                sub_roots={
                    "mv:define-lang.org:lib": config.LocalDependencyEntry(
                        deps_path=str(_LOCAL_DEPS_PATH),
                        index=0,
                        universe="mv:define-lang.org:lib",
                        path=define_path.DefinePathFromPosix(
                            PurePosixPath("vendor/lib..v2/.hidden")
                        ),
                    ),
                },
            ),
            diagnostics=[],
        )

    def test_trailing_slash_in_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _write_valid_project_config(tmp_path)
        _write_local_deps(
            tmp_path,
            (
                "deps: {\n"
                "  local: [\n"
                "    {\n"
                '      universe_name: "mv:define-lang.org:lib"\n'
                '      path: "vendor/lib/"\n'
                "    }\n"
                "  ]\n"
                "}\n"
            ),
        )
        monkeypatch.chdir(tmp_path)

        assert _load() == _invalid_local_dep_field("path", "path must not end with '/'")

    def test_duplicate_universe_name(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _write_valid_project_config(tmp_path)
        _write_local_deps(
            tmp_path,
            (
                "deps: {\n"
                "  local: [\n"
                "    {\n"
                '      universe_name: "mv:define-lang.org:lib"\n'
                '      path: "vendor/lib"\n'
                "    },\n"
                "    {\n"
                '      universe_name: "mv:define-lang.org:lib"\n'
                '      path: "other/lib"\n'
                "    }\n"
                "  ]\n"
                "}\n"
            ),
        )
        monkeypatch.chdir(tmp_path)

        assert _load() == config.RootConfigResult(
            root_config=None,
            diagnostics=[
                diagnostics.DuplicateLocalDependencyDiagnostic(
                    config_path=str(_LOCAL_DEPS_PATH),
                    field_path=("deps", "local", 1, "universe_name"),
                    universe_name="mv:define-lang.org:lib",
                    first_field_path=("deps", "local", 0, "universe_name"),
                )
            ],
        )

    def test_syntax_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        _write_valid_project_config(tmp_path)
        _write_local_deps(
            tmp_path,
            ("deps: {\n  local: [\n    {\n      universe_name: 'bad'\n    }\n  ]\n}\n"),
        )
        monkeypatch.chdir(tmp_path)

        result = _load()
        assert result.root_config is None
        (diagnostic,) = result.diagnostics
        assert isinstance(diagnostic, errors.SyntaxDiagnostic)
        assert diagnostic.location == rendering.SourceLocation(
            line=4,
            column=22,
            end_line=4,
            end_column=26,
            file_path=str(_LOCAL_DEPS_PATH),
        )
        assert (
            diagnostic.kind
            == error_types.SyntaxDiagnosticKind.SINGLE_QUOTES_NOT_ALLOWED
        )


class TestSubRoot:
    def test_not_a_project_root(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        (tmp_path / "subroot").mkdir()
        monkeypatch.chdir(tmp_path)

        assert config.ConfigLoader(
            define_path.DefinePath("subroot"), rendering.SourceMap()
        ).load_project_root_config(
            _declaring_entry("sub.example.com:lib", "subroot")
        ) == config.RootConfigResult(
            root_config=None,
            diagnostics=[
                diagnostics.SubRootNotProjectRootDiagnostic(
                    config_path=str(_LOCAL_DEPS_PATH),
                    field_path=("deps", "local", 0, "path"),
                    sub_root_path="subroot",
                    sub_root_config_path="subroot/.define/project/config.defcl",
                )
            ],
        )

    def test_resolves_fqun_and_sub_roots(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _write_project_config(
            tmp_path / "subroot",
            ('project: {\n  universe_name: "sub.example.com:lib"\n}\n'),
        )
        _write_local_deps(
            tmp_path / "subroot",
            (
                "deps: {\n"
                "  local: [\n"
                "    {\n"
                '      universe_name: "mv:define-lang.org:lib"\n'
                '      path: "vendor/lib"\n'
                "    }\n"
                "  ]\n"
                "}\n"
            ),
        )
        monkeypatch.chdir(tmp_path)

        assert _load(define_path.DefinePath("subroot")) == config.RootConfigResult(
            root_config=config.ProjectRootConfig(
                fqun="sub.example.com:lib",
                sub_roots={
                    "mv:define-lang.org:lib": config.LocalDependencyEntry(
                        deps_path="subroot/.define/deps/local.defcl",
                        index=0,
                        universe="mv:define-lang.org:lib",
                        path=define_path.DefinePathFromPosix(
                            PurePosixPath("vendor/lib")
                        ),
                    )
                },
            ),
            diagnostics=[],
        )

    def test_project_config_validation_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _write_project_config(
            tmp_path / "subroot",
            ('project: {\n  universe_name: ""\n}\n'),
        )
        monkeypatch.chdir(tmp_path)

        config_path = PurePosixPath("subroot/.define/project/config.defcl")
        assert _load(define_path.DefinePath("subroot")) == config.RootConfigResult(
            root_config=None,
            diagnostics=[
                diagnostics.ConfigViolationDiagnostic(
                    config_path=str(config_path),
                    field_path=("project", "universe_name"),
                    violation_message="must be at least 1 characters",
                )
            ],
        )

    def test_local_deps_validation_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _write_project_config(
            tmp_path / "subroot",
            ('project: {\n  universe_name: "sub.example.com:lib"\n}\n'),
        )
        _write_local_deps(
            tmp_path / "subroot",
            (
                "deps: {\n"
                "  local: [\n"
                "    {\n"
                '      universe_name: "mv:define-lang.org:lib"\n'
                "    }\n"
                "  ]\n"
                "}\n"
            ),
        )
        monkeypatch.chdir(tmp_path)

        deps_path = PurePosixPath("subroot/.define/deps/local.defcl")
        assert _load(define_path.DefinePath("subroot")) == config.RootConfigResult(
            root_config=None,
            diagnostics=[
                diagnostics.ConfigViolationDiagnostic(
                    config_path=str(deps_path),
                    field_path=("deps", "local", 0, "path"),
                    violation_message="value is required",
                )
            ],
        )
