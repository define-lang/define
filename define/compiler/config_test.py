from __future__ import annotations

import typing
from pathlib import PurePosixPath

from defcl.python import error_types, errors
from define.compiler import ast, config, constants
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
        root, 'project: {\n  universe_name: "test.example.com:my_lib"\n}\n'
    )


def _load(root: define_path.DefinePath = constants.PROJECT_ROOT):
    return config.ConfigLoader(root).load_project_root_config()


def _invalid_local_deps(violation_message: str) -> config.RootConfigResult:
    return config.RootConfigResult(
        root_config=None,
        diagnostics=[
            diagnostics.InvalidConfigDiagnostic(
                location=ast.start_of_file_location(str(_LOCAL_DEPS_PATH)),
                violation_messages=[violation_message],
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
                    "mv:define-lang.org:lib": define_path.DefinePathFromPosix(
                        PurePosixPath("vendor/lib")
                    ),
                    "mv:define-lang.org:core": define_path.DefinePathFromPosix(
                        PurePosixPath("vendor/core")
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
                    location=ast.start_of_file_location(str(_PROJECT_CONFIG_PATH)),
                    config_path=str(_PROJECT_CONFIG_PATH),
                )
            ],
        )

    def test_expected_fqun_match_succeeds(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _write_valid_project_config(tmp_path)
        monkeypatch.chdir(tmp_path)

        assert config.ConfigLoader(constants.PROJECT_ROOT).load_project_root_config(
            "test.example.com:my_lib"
        ) == config.RootConfigResult(
            root_config=config.ProjectRootConfig(
                fqun="test.example.com:my_lib", sub_roots={}
            ),
            diagnostics=[],
        )

    def test_expected_fqun_mismatch(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _write_valid_project_config(tmp_path)
        monkeypatch.chdir(tmp_path)

        assert config.ConfigLoader(constants.PROJECT_ROOT).load_project_root_config(
            "other.example.com:other_lib"
        ) == config.RootConfigResult(
            root_config=None,
            diagnostics=[
                diagnostics.SubRootFqunMismatchDiagnostic(
                    location=ast.start_of_file_location(str(_PROJECT_CONFIG_PATH)),
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
            'project: {\n  universe_name: "test.example.com:my_lib"\n  universe_nam: "x"\n  owner: "y"\n}\n',
        )
        monkeypatch.chdir(tmp_path)

        result = _load()
        assert result.root_config is None
        first, second = result.diagnostics
        assert isinstance(first, diagnostics.ConfigDclDiagnostic)
        assert first.location == rendering.SourceLocation(
            line=3,
            column=3,
            end_line=3,
            end_column=14,
            file_path=str(_PROJECT_CONFIG_PATH),
        )
        assert isinstance(first.dcl_error, errors.UnknownFieldNameDiagnostic)
        assert first.dcl_error.kind == error_types.DiagnosticKind.UNKNOWN_FIELD_NAME
        assert first.dcl_error.field_name == "universe_nam"
        assert first.dcl_error.message_type == "define.config.project.Project"
        assert isinstance(second, diagnostics.ConfigDclDiagnostic)
        assert second.location == rendering.SourceLocation(
            line=4,
            column=3,
            end_line=4,
            end_column=7,
            file_path=str(_PROJECT_CONFIG_PATH),
        )
        assert isinstance(second.dcl_error, errors.UnknownFieldNameDiagnostic)
        assert second.dcl_error.kind == error_types.DiagnosticKind.UNKNOWN_FIELD_NAME
        assert second.dcl_error.field_name == "owner"
        assert second.dcl_error.message_type == "define.config.project.Project"

    def test_value_of_the_wrong_kind_is_a_diagnostic(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _write_project_config(tmp_path, "project: {\n  universe_name: 5\n}\n")
        monkeypatch.chdir(tmp_path)

        result = _load()
        assert result.root_config is None
        (diagnostic,) = result.diagnostics
        assert isinstance(diagnostic, diagnostics.ConfigDclDiagnostic)
        assert diagnostic.location == rendering.SourceLocation(
            line=2,
            column=18,
            end_line=2,
            end_column=18,
            file_path=str(_PROJECT_CONFIG_PATH),
        )
        assert type(diagnostic.dcl_error) is errors.DclDiagnostic
        assert (
            diagnostic.dcl_error.kind
            == error_types.DiagnosticKind.NON_STRING_FOR_STRING_FIELD
        )
        assert diagnostic.dcl_error.field_name == "universe_name"

    def test_empty_universe_name(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        _write_project_config(tmp_path, 'project: {\n  universe_name: ""\n}\n')
        monkeypatch.chdir(tmp_path)

        assert _load() == config.RootConfigResult(
            root_config=None,
            diagnostics=[
                diagnostics.InvalidConfigDiagnostic(
                    location=ast.start_of_file_location(str(_PROJECT_CONFIG_PATH)),
                    violation_messages=[
                        "project.universe_name: must be at least 1 characters"
                    ],
                )
            ],
        )

    def test_missing_universe_name(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _write_project_config(tmp_path, "project: {}\n")
        monkeypatch.chdir(tmp_path)

        assert _load() == config.RootConfigResult(
            root_config=None,
            diagnostics=[
                diagnostics.InvalidConfigDiagnostic(
                    location=ast.start_of_file_location(str(_PROJECT_CONFIG_PATH)),
                    violation_messages=["project.universe_name: value is required"],
                )
            ],
        )

    def test_syntax_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        _write_project_config(
            tmp_path, 'project: {\n  universe_name "test.example.com:my_lib"\n}\n'
        )
        monkeypatch.chdir(tmp_path)

        result = _load()
        assert result.root_config is None
        (diagnostic,) = result.diagnostics
        assert isinstance(diagnostic, diagnostics.ConfigDclDiagnostic)
        assert diagnostic.location == rendering.SourceLocation(
            line=2,
            column=16,
            end_line=2,
            end_column=16,
            file_path=str(_PROJECT_CONFIG_PATH),
        )
        assert isinstance(diagnostic.dcl_error, errors.DclError)
        assert diagnostic.dcl_error.kind == error_types.DclErrorKind.MISSING_COLON


class TestLocalDepsConfig:
    def test_empty_deps_list(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        _write_valid_project_config(tmp_path)
        _write_local_deps(tmp_path, "deps: {}\n")
        monkeypatch.chdir(tmp_path)

        assert _load() == config.RootConfigResult(
            root_config=config.ProjectRootConfig(
                fqun="test.example.com:my_lib", sub_roots={}
            ),
            diagnostics=[],
        )

    def test_empty_local_list(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        _write_valid_project_config(tmp_path)
        _write_local_deps(tmp_path, "deps: { local: [] }\n")
        monkeypatch.chdir(tmp_path)

        assert _load() == config.RootConfigResult(
            root_config=config.ProjectRootConfig(
                fqun="test.example.com:my_lib", sub_roots={}
            ),
            diagnostics=[],
        )

    def test_missing_universe_name(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _write_valid_project_config(tmp_path)
        _write_local_deps(tmp_path, 'deps: { local: [{ path: "vendor/lib" }] }\n')
        monkeypatch.chdir(tmp_path)

        assert _load() == _invalid_local_deps(
            "deps.local.universe_name: value is required"
        )

    def test_empty_universe_name(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        _write_valid_project_config(tmp_path)
        _write_local_deps(
            tmp_path, 'deps: { local: [{ universe_name: "" path: "vendor/lib" }] }\n'
        )
        monkeypatch.chdir(tmp_path)

        assert _load() == _invalid_local_deps(
            "deps.local.universe_name: must be at least 1 characters"
        )

    def test_missing_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        _write_valid_project_config(tmp_path)
        _write_local_deps(
            tmp_path,
            'deps: { local: [{ universe_name: "mv:define-lang.org:lib" }] }\n',
        )
        monkeypatch.chdir(tmp_path)

        assert _load() == _invalid_local_deps("deps.local.path: value is required")

    def test_absolute_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        _write_valid_project_config(tmp_path)
        _write_local_deps(
            tmp_path,
            (
                "deps: { local: [{"
                ' universe_name: "mv:define-lang.org:lib"'
                ' path: "/absolute/path"'
                " }] }\n"
            ),
        )
        monkeypatch.chdir(tmp_path)

        assert _load() == _invalid_local_deps(
            "deps.local.path: path must not be absolute"
        )

    def test_dotdot_in_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        _write_valid_project_config(tmp_path)
        _write_local_deps(
            tmp_path,
            (
                "deps: { local: [{"
                ' universe_name: "mv:define-lang.org:lib"'
                ' path: "vendor/../lib"'
                " }] }\n"
            ),
        )
        monkeypatch.chdir(tmp_path)

        assert _load() == _invalid_local_deps(
            "deps.local.path: path must not contain '..'"
        )

    def test_trailing_slash_in_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _write_valid_project_config(tmp_path)
        _write_local_deps(
            tmp_path,
            (
                "deps: { local: [{"
                ' universe_name: "mv:define-lang.org:lib"'
                ' path: "vendor/lib/"'
                " }] }\n"
            ),
        )
        monkeypatch.chdir(tmp_path)

        assert _load() == _invalid_local_deps(
            "deps.local.path: path must not end with '/'"
        )

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

        assert _load() == _invalid_local_deps(
            'deps.local: duplicate universe_name "mv:define-lang.org:lib"'
        )

    def test_syntax_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        _write_valid_project_config(tmp_path)
        _write_local_deps(tmp_path, "deps: { local: [{ universe_name: 'bad' }] }\n")
        monkeypatch.chdir(tmp_path)

        result = _load()
        assert result.root_config is None
        (diagnostic,) = result.diagnostics
        assert isinstance(diagnostic, diagnostics.ConfigDclDiagnostic)
        assert diagnostic.location == rendering.SourceLocation(
            line=1,
            column=34,
            end_line=1,
            end_column=38,
            file_path=str(_LOCAL_DEPS_PATH),
        )
        assert isinstance(diagnostic.dcl_error, errors.DclError)
        assert (
            diagnostic.dcl_error.kind
            == error_types.DclErrorKind.SINGLE_QUOTES_NOT_ALLOWED
        )


class TestSubRoot:
    def test_not_a_project_root(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        (tmp_path / "subroot").mkdir()
        monkeypatch.chdir(tmp_path)

        assert _load(define_path.DefinePath("subroot")) == config.RootConfigResult(
            root_config=None,
            diagnostics=[
                diagnostics.SubRootNotProjectRootDiagnostic(
                    location=ast.start_of_file_location(
                        "subroot/.define/project/config.defcl"
                    ),
                    config_path="subroot/.define/project/config.defcl",
                    sub_root_path="subroot",
                )
            ],
        )

    def test_resolves_fqun_and_sub_roots(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _write_project_config(
            tmp_path / "subroot",
            'project: {\n  universe_name: "sub.example.com:lib"\n}\n',
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
                    "mv:define-lang.org:lib": define_path.DefinePathFromPosix(
                        PurePosixPath("vendor/lib")
                    )
                },
            ),
            diagnostics=[],
        )

    def test_project_config_validation_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _write_project_config(tmp_path / "subroot", "project: {}\n")
        monkeypatch.chdir(tmp_path)

        config_path = PurePosixPath("subroot/.define/project/config.defcl")
        assert _load(define_path.DefinePath("subroot")) == config.RootConfigResult(
            root_config=None,
            diagnostics=[
                diagnostics.InvalidConfigDiagnostic(
                    location=ast.start_of_file_location(str(config_path)),
                    violation_messages=["project.universe_name: value is required"],
                )
            ],
        )

    def test_local_deps_validation_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        _write_project_config(
            tmp_path / "subroot",
            'project: {\n  universe_name: "sub.example.com:lib"\n}\n',
        )
        _write_local_deps(
            tmp_path / "subroot",
            'deps: { local: [{ universe_name: "mv:define-lang.org:lib" }] }\n',
        )
        monkeypatch.chdir(tmp_path)

        deps_path = PurePosixPath("subroot/.define/deps/local.defcl")
        assert _load(define_path.DefinePath("subroot")) == config.RootConfigResult(
            root_config=None,
            diagnostics=[
                diagnostics.InvalidConfigDiagnostic(
                    location=ast.start_of_file_location(str(deps_path)),
                    violation_messages=["deps.local.path: value is required"],
                )
            ],
        )
