"""Canonical URL-scheme registry for storage paths.

Parses paths; does not imply a backend exists for the scheme.
Entries here are decoupled from `storage_registry` / `storage_backends`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE


@dataclass(frozen=True)
class SchemeSpec:
    """Metadata for a canonical URL scheme.

    Attributes:
        scheme: Canonical lowercase scheme token (e.g. "s3", "gs", "" for local).
        aliases: Alternative lowercase prefixes that resolve to this canonical scheme
            (e.g. "gcs" is an alias of "gs").
        strict: If True (default), mixed-case scheme input is rejected by
            `StoragePath.normalize`. Only the bare-local entry uses strict=False.
        provider: The storage provider enum this scheme routes to, or None for
            schemes described for registry completeness but with no registered
            backend (e.g. hdfs, dbfs, sharepoint).
    """

    scheme: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    strict: bool = True
    provider: CONST_STORAGE_PROVIDER_TYPE | None = None


SCHEMES: dict[str, SchemeSpec] = {
    "":           SchemeSpec(scheme="",          strict=False, provider=CONST_STORAGE_PROVIDER_TYPE.LOCAL),
    "file":       SchemeSpec(scheme="file",      provider=CONST_STORAGE_PROVIDER_TYPE.LOCAL),
    "s3":         SchemeSpec(scheme="s3",        provider=CONST_STORAGE_PROVIDER_TYPE.S3),
    "s3u":        SchemeSpec(scheme="s3u"),
    "s3express":  SchemeSpec(scheme="s3express", provider=CONST_STORAGE_PROVIDER_TYPE.S3EXPRESS),
    "gs":         SchemeSpec(scheme="gs",        aliases=("gcs",), provider=CONST_STORAGE_PROVIDER_TYPE.GCS),
    "azure":      SchemeSpec(scheme="azure",     aliases=("az",),  provider=CONST_STORAGE_PROVIDER_TYPE.AZURE_BLOB),
    "r2":         SchemeSpec(scheme="r2",        provider=CONST_STORAGE_PROVIDER_TYPE.R2),
    "minio":      SchemeSpec(scheme="minio",     provider=CONST_STORAGE_PROVIDER_TYPE.MINIO),
    "b2":         SchemeSpec(scheme="b2",        provider=CONST_STORAGE_PROVIDER_TYPE.B2),
    "sftp":       SchemeSpec(scheme="sftp",      provider=CONST_STORAGE_PROVIDER_TYPE.SFTP),
    "ssh":        SchemeSpec(scheme="ssh",       provider=CONST_STORAGE_PROVIDER_TYPE.SSH),
    "ftp":        SchemeSpec(scheme="ftp",       provider=CONST_STORAGE_PROVIDER_TYPE.FTP),
    "smb":        SchemeSpec(scheme="smb",       provider=CONST_STORAGE_PROVIDER_TYPE.SMB),
    "github":     SchemeSpec(scheme="github",    provider=CONST_STORAGE_PROVIDER_TYPE.GITHUB),
    "http":       SchemeSpec(scheme="http"),
    "https":      SchemeSpec(scheme="https"),
    "dbfs":       SchemeSpec(scheme="dbfs"),
    "hdfs":       SchemeSpec(scheme="hdfs"),
    "webhdfs":    SchemeSpec(scheme="webhdfs"),
    "spark":      SchemeSpec(scheme="spark"),
    "trino":      SchemeSpec(scheme="trino"),
    "gdrive":     SchemeSpec(scheme="gdrive"),
    "dropbox":    SchemeSpec(scheme="dropbox"),
    "onedrive":   SchemeSpec(scheme="onedrive"),
    "sharepoint": SchemeSpec(scheme="sharepoint"),
}

_ALIAS_TO_CANONICAL: dict[str, str] = {
    alias: spec.scheme for spec in SCHEMES.values() for alias in spec.aliases
}
