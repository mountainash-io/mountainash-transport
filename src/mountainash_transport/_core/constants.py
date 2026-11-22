#constants.py

from enum import StrEnum
import typing as t

DEFAULT_CHUNK_SIZE = 64 * 1024
"""Bytes read or sent per chunk when transport moves a stream (local writes, uploads, codecs)."""

DEFAULT_BUFFER_MEMORY_LIMIT = 64 * 1024 * 1024
"""Bytes a spooled buffer keeps in memory before rolling to a temp file (``materialize``, buffered reads)."""


class _FindMemberMixin(StrEnum):
    """Shared ``find_member`` classmethod for storage enums.

    Returns the enum member whose *value* matches ``v`` (case-insensitive),
    or ``None`` if no match is found.
    """

    @classmethod
    def find_member(cls, v: t.Any) -> t.Self | None:
        if v is None:
            return None
        try:
            return cls(v)
        except (ValueError, KeyError):
            pass
        # Case-insensitive fallback against values.
        try:
            text = str(v).lower()
        except Exception:
            return None
        for member in cls:
            if member.value.lower() == text:
                return member
        return None


class CONST_STORAGE_PROVIDER_TYPE(_FindMemberMixin):
    """Storage provider types"""
    LOCAL = "local"
    S3 = "s3"
    S3EXPRESS = "s3express"
    AZURE_BLOB = "azure_blob"
    GCS = "gcs"
    SFTP = "sftp"
    FTP = "ftp"
    SMB = "smb"
    MINIO = "minio"
    SSH = "ssh"
    B2 = "b2"
    GITHUB = "github"
    R2 = "r2"
    HTTP = "http"

