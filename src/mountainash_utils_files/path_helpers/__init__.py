"""Path parsing and normalization for storage URLs.

Public Exports:
    StoragePath — classmethod-only helper (identify_scheme, normalize, join, to_str, matches)
    SchemeSpec  — dataclass describing one canonical scheme
    SCHEMES     — dict of canonical schemes supported by path parsing
    s3          — submodule with s3_bucket(), s3_key()

Internal Exports (legacy, not re-exported from top-level package):
    BasePathHelper, LocalPathHelper, S3PathHelper, GCSPathHelper, AZPathHelper,
    SFTPPathHelper, SSHPathHelper, PathHelper — deprecated legacy classes

This module parses paths. It does not imply that a backend exists for
every scheme in SCHEMES; caller is responsible for scheme→provider mapping.
"""
from . import s3
from .base_path_helper import BasePathHelper
from .az_path_helper import AZPathHelper
from .gcs_path_helper import GCSPathHelper
from .s3_path_helper import S3PathHelper
from .sftp_path_helper import SFTPPathHelper
from .ssh_path_helper import SSHPathHelper
from .local_path_helper import LocalPathHelper
from .path_helper import PathHelper
from .scheme import SCHEMES, SchemeSpec
from .storage_path import StoragePath

# Public API
__all__ = ("StoragePath", "SchemeSpec", "SCHEMES", "s3")

# Legacy exports (available for backward compatibility, but not in top-level package __all__)
__all__ += (
    "BasePathHelper",
    "LocalPathHelper",
    "AZPathHelper",
    "GCSPathHelper",
    "S3PathHelper",
    "SFTPPathHelper",
    "SSHPathHelper",
    "PathHelper"
)
