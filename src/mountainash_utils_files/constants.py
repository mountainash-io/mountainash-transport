#constants.py

from enum import StrEnum
import typing as t


class _FindMemberMixin(StrEnum):
    """Shared ``find_member`` classmethod for storage enums.

    Returns the enum member whose *value* matches ``v`` (case-insensitive),
    or ``None`` if no match is found.
    """

    @classmethod
    def find_member(cls, v: t.Any) -> t.Optional["_FindMemberMixin"]:
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
    AZURE_FILES = "azure_files"
    GCS = "gcs"
    SFTP = "sftp"
    FTP = "ftp"
    SMB = "smb"
    NFS = "nfs"
    MINIO = "minio"
    SSH = "ssh"
    B2 = "b2"
    GITHUB = "github"
    R2 = "r2"
    HTTP = "http"

class CONST_STORAGE_ACCESS_TYPE(_FindMemberMixin):
    """Storage access types"""
    READ_ONLY = "read_only"
    WRITE_ONLY = "write_only"
    READ_WRITE = "read_write"
    ADMIN = "admin"

class CONST_STORAGE_ENCRYPTION_TYPE(StrEnum):
    """Storage encryption types"""
    NONE = "none"
    AES256 = "aes256"
    AES256_GCM = "aes256_gcm"
    CLIENT_SIDE = "client_side"
    SERVER_SIDE = "server_side"

class CONST_STORAGE_CONNECTION_STATUS(StrEnum):
    """Storage connection status"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    CLOSED = "closed"

class CONST_STORAGE_TRANSFER_MODE(StrEnum):
    """Storage transfer modes"""
    BINARY = "binary"
    TEXT = "text"
    AUTO = "auto"

class CONST_STORAGE_COMPRESSION_TYPE(StrEnum):
    """Storage compression types"""
    NONE = "none"
    GZIP = "gzip"
    BZIP2 = "bzip2"
    ZSTD = "zstd"
    LZ4 = "lz4"


