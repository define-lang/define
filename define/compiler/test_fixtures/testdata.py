"""Test fixture for finding a test's convention-derived testdata."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from define.testdata import path_resolver

if TYPE_CHECKING:
    from pathlib import Path


def testdata_directory(request: pytest.FixtureRequest) -> Path:
    """Return the convention-derived testdata directory of the test that makes the request."""
    test_function = cast("pytest.Function", request.node)
    test_class = test_function.parent
    test_class_name = test_class.name if isinstance(test_class, pytest.Class) else None
    return path_resolver.directory_for(
        request.path,
        test_function.originalname,
        test_class_name,
    )


@pytest.fixture
def testdata_project_directory(
    request: pytest.FixtureRequest,
) -> Path:
    """Return the current test's convention-derived project directory."""
    return testdata_directory(request)
