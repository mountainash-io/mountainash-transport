#constants.py

from enum import StrEnum

class CONST_STORAGE_PROVIDER_TYPE(StrEnum):
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

class CONST_STORAGE_AUTH_METHOD(StrEnum):
    """Authentication methods"""
    NONE = "none"
    KEY = "key"
    PASSWORD = "password"
    TOKEN = "token"
    CERTIFICATE = "certificate"
    IAM = "iam"
    MANAGED_IDENTITY = "managed_identity"
    KERBEROS = "kerberos"
    SERVICE_ACCOUNT = "service_account"

class CONST_STORAGE_ACCESS_TYPE(StrEnum):
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


