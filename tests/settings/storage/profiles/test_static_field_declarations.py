"""Static field declarations on storage profiles must match their runtime specs.

Profile fields are generated from ``__spec__`` at runtime; each class declares
the same names under ``if t.TYPE_CHECKING:`` so type checkers can see them.
Those declarations never execute, so this test reads them from source.
"""
from __future__ import annotations

import ast
import inspect
import textwrap

import pytest

from mountainash_transport.settings.storage.registry import STORAGE_REGISTRY

_PROVIDERS = sorted(STORAGE_REGISTRY.specs)


def _declared_fields(cls: type) -> dict[str, str]:
    tree = ast.parse(textwrap.dedent(inspect.getsource(cls)))
    (class_def,) = [node for node in tree.body if isinstance(node, ast.ClassDef)]
    for node in class_def.body:
        if isinstance(node, ast.If) and ast.unparse(node.test).endswith("TYPE_CHECKING"):
            return {
                stmt.target.id: ast.unparse(stmt.annotation)
                for stmt in node.body
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)
            }
    return {}


@pytest.mark.parametrize("provider", _PROVIDERS)
def test_static_declarations_match_spec_parameters(provider: str) -> None:
    cls = STORAGE_REGISTRY.get_settings_class(provider)
    spec_names = [parameter.name for parameter in STORAGE_REGISTRY.get_spec(provider).parameters]
    assert list(_declared_fields(cls)) == spec_names


@pytest.mark.parametrize("provider", _PROVIDERS)
def test_static_declarations_admit_none_defaults(provider: str) -> None:
    """A field whose default is None must be declared optional."""
    declared = _declared_fields(STORAGE_REGISTRY.get_settings_class(provider))
    for parameter in STORAGE_REGISTRY.get_spec(provider).parameters:
        if parameter.default is None:
            assert declared[parameter.name].endswith("| None"), parameter.name
