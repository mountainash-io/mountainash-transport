"""Path parsing and normalization for storage URLs.

Exports:
    StoragePath       — classmethod-only helper (identify_scheme, normalize, join, to_str, matches)
    SUFFIX_TRANSFORMS — dict of file-extension suffixes to transform kinds
    infer_pipeline    — parse a path's suffix chain into a Pipeline of transforms
    s3                — submodule with s3_bucket(), s3_key()

This module parses paths. It does not imply that a backend exists for
every scheme in mountainash_transport._schemes.SCHEMES; caller is responsible for scheme→provider mapping.
"""
from __future__ import annotations

import importlib
import typing as t

from .suffixes import SUFFIX_TRANSFORMS, infer_pipeline

if t.TYPE_CHECKING:
    from . import s3
    from .storage_path import StoragePath


def __getattr__(name: str) -> t.Any:
    if name not in ("StoragePath", "s3"):
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    try:
        module = importlib.import_module(".storage_path" if name == "StoragePath" else ".s3", __name__)
    except ImportError as exc:
        from mountainash_transport._core.extras import raise_for_missing_extra
        raise_for_missing_extra(name, "http", exc)
    return module.StoragePath if name == "StoragePath" else module


__all__ = ("StoragePath", "s3", "SUFFIX_TRANSFORMS", "infer_pipeline")
