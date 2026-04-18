"""Path parsing and normalization for storage URLs.

Exports:
    StoragePath — classmethod-only helper (identify_scheme, normalize, join, to_str, matches)
    SchemeSpec  — dataclass describing one canonical scheme
    SCHEMES     — dict of canonical schemes supported by path parsing
    s3          — submodule with s3_bucket(), s3_key()

This module parses paths. It does not imply that a backend exists for
every scheme in SCHEMES; caller is responsible for scheme→provider mapping.
"""
from . import s3
from .scheme import SCHEMES, SchemeSpec
from .storage_path import StoragePath

__all__ = ("StoragePath", "SchemeSpec", "SCHEMES", "s3")
