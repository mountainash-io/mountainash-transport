"""Distribution metadata: slim base install; every remote extra carries the [http] stack."""

from importlib.metadata import metadata, requires

import pytest
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name

STACK_NAMES = {"mountainash-settings", "mountainash-auth-client", "pydantic", "universal-pathlib", "httpx", "fsspec"}
SIBLING_BOUNDS = {"mountainash-settings": ">=0.1.0,<0.2", "mountainash-auth-client": ">=0.1.0,<0.2"}


def _requirements():
    return [Requirement(item) for item in requires("mountainash-transport") or []]


def test_base_install_requires_only_typing_extensions():
    base = {canonicalize_name(r.name) for r in _requirements() if r.marker is None}
    assert base == {"typing-extensions"}


@pytest.mark.parametrize("extra", ["http", "s3", "gcs", "azure", "sftp", "oauth1", "all"])
def test_every_remote_extra_resolves_the_http_stack_with_unchanged_bounds(extra):
    active = {
        canonicalize_name(r.name): r.specifier
        for r in _requirements()
        if r.marker is not None and r.marker.evaluate({"extra": extra})
    }
    assert STACK_NAMES <= set(active), (extra, STACK_NAMES - set(active))
    for name, bound in SIBLING_BOUNDS.items():
        assert active[name] == SpecifierSet(bound), (extra, name)
    assert "0.2.0" not in active["mountainash-auth-client"]
    assert "26.6.1" not in active["mountainash-auth-client"]


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
