"""Canonical URL-scheme registry for storage paths.

Parses paths; does not imply a backend exists for the scheme.
Entries here are decoupled from `storage_registry` / `storage_backends`.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SchemeSpec:
    """Metadata for a canonical URL scheme.

    Attributes:
        scheme: Canonical lowercase scheme token (e.g. "s3", "gs", "" for local).
        aliases: Alternative lowercase prefixes that resolve to this canonical scheme
            (e.g. "gcs" is an alias of "gs").
        strict: If True (default), mixed-case scheme input is rejected by
            `StoragePath.normalize`. Only the bare-local entry uses strict=False.
    """

    scheme: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    strict: bool = True


SCHEMES: dict[str, SchemeSpec] = {
    "":           SchemeSpec(scheme="",         strict=False),
    "file":       SchemeSpec(scheme="file"),
    "s3":         SchemeSpec(scheme="s3"),
    "s3u":        SchemeSpec(scheme="s3u"),
    "gs":         SchemeSpec(scheme="gs",     aliases=("gcs",)),
    "azure":      SchemeSpec(scheme="azure",  aliases=("az",)),
    "sftp":       SchemeSpec(scheme="sftp"),
    "ftp":        SchemeSpec(scheme="ftp"),
    "ssh":        SchemeSpec(scheme="ssh"),
    "smb":        SchemeSpec(scheme="smb"),
    "b2":         SchemeSpec(scheme="b2"),
    "github":     SchemeSpec(scheme="github"),
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
