"""Distribution metadata must select the migrated runtime dependency family."""

from importlib.metadata import metadata, requires

import pytest
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name


@pytest.mark.parametrize(
    ("name", "bound", "accepted", "rejected"),
    [
        ("mountainash-settings", ">=0.1.0,<0.2", "0.1.0", ["0.0.9", "0.2.0"]),
        ("mountainash-auth-client", ">=0.1.0,<0.2", "0.1.0", ["0.0.9", "0.2.0", "26.6.1"]),
    ],
)
def test_runtime_dependency_bounds(name, bound, accepted, rejected):
    dependencies = {
        canonicalize_name(req.name): req
        for item in requires("mountainash-transport") or []
        if (req := Requirement(item)).marker is None
    }
    assert name in dependencies, f"Missing unconditional runtime dependency: {name}"
    specifier = dependencies[name].specifier
    assert specifier == SpecifierSet(bound)
    assert accepted in specifier
    assert all(version not in specifier for version in rejected)


def test_supported_python_metadata():
    package = metadata("mountainash-transport")
    versions = SpecifierSet(package["Requires-Python"])
    assert "3.12" in versions
    assert "3.13" in versions
    assert "3.11" not in versions
    assert "3.10" not in versions
    classifiers = package.get_all("Classifier", [])
    assert "Programming Language :: Python :: 3.12" in classifiers
    assert "Programming Language :: Python :: 3.13" in classifiers
    assert "Programming Language :: Python :: 3.10" not in classifiers
    assert "Programming Language :: Python :: 3.11" not in classifiers
