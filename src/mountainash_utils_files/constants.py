#constants.py

from mountainash_constants import BaseIdentityConstant, BaseValueConstant

class CONST_STORAGE_PROVIDER_TYPE(BaseValueConstant):
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

class CONST_STORAGE_AUTH_METHOD(BaseValueConstant):
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

class CONST_STORAGE_ACCESS_TYPE(BaseValueConstant):
    """Storage access types"""
    READ_ONLY = "read_only"
    WRITE_ONLY = "write_only"
    READ_WRITE = "read_write"
    ADMIN = "admin"

class CONST_STORAGE_ENCRYPTION_TYPE(BaseValueConstant):
    """Storage encryption types"""
    NONE = "none"
    AES256 = "aes256"
    AES256_GCM = "aes256_gcm"
    CLIENT_SIDE = "client_side"
    SERVER_SIDE = "server_side"

class CONST_STORAGE_CONNECTION_STATUS(BaseValueConstant):
    """Storage connection status"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    CLOSED = "closed"

class CONST_STORAGE_TRANSFER_MODE(BaseValueConstant):
    """Storage transfer modes"""
    BINARY = "binary"
    TEXT = "text"
    AUTO = "auto"

class CONST_STORAGE_COMPRESSION_TYPE(BaseValueConstant):
    """Storage compression types"""
    NONE = "none"
    GZIP = "gzip"
    BZIP2 = "bzip2"
    ZSTD = "zstd"
    LZ4 = "lz4"


class CONST_DATAFILEFORMAT(BaseValueConstant):
    """
    Enumeration for different file formats.

    Attributes:
        - PARQUET (str): Parquet file format.
        - CSV (str): CSV file format.
        - JSON (str): JSON file format.
        - DELTA (str): Delta file format.
    """
    PARQUET =   "parquet"
    CSV =       "csv"
    JSON =      "json"
    DELTA =     "delta"



# TODO: Move to mountainash-files
class CONST_STORAGESYSTEM(BaseValueConstant):
    """
    Enumeration for different types of filesystems.

    Attributes:
        - LOCAL_MEMORY (str): Local memory filesystem.
        - LOCAL_DISK (str): Local disk filesystem.
        - S3 (str): Amazon S3 filesystem.
        - GCS (str): Google Cloud Storage filesystem.
        - AZ (str): Azure Blob Storage filesystem.
        - DBFS (str): Databricks File System.
    """
    LOCAL_DISK =  "LOCAL_DISK"
    B2 =          "B2"
    S3 =          "S3"
    S3U =         "S3U"
    GCS =         "GCS"
    AZ =          "AZ"
    DBFS =        "DBFS"
    HDFS =        "HDFS"
    SFTP =        "SFTP"
    FTP =         "FTP"
    WEBHDFS =     "WEBHDFS"
    SSH =         "SSH"
    SPARK =       "SPARK"
    TRINO =       "TRINO"
    GDRIVE =      "GDRIVE"
    DROPBOX =     "DROPBOX"
    ONEDRIVE =    "ONEDRIVE"
    SHAREPOINT =  "SHAREPOINT"
    GITHUB =      "GITHUB"



# TODO: Move to mountainash-files
class CONST_STORAGESYSTEM_PREFIX(BaseValueConstant):
    """
    Enumeration for different types of filesystems.

    Attributes:
        - LOCAL_MEMORY (str): Local memory filesystem.
        - LOCAL_DISK (str): Local disk filesystem.
        - S3 (str): Amazon S3 filesystem.
        - GCS (str): Google Cloud Storage filesystem.
        - AZ (str): Azure Blob Storage filesystem.
        - DBFS (str): Databricks File System.
    """

    LOCAL_DISK =   ""
    B2 =           "b2"
    S3 =           "s3"
    S3U =          "s3u"
    GCS =          "gs"
    AZ =           "azure"
    DBFS =         "dbfs"
    HDFS =         "hdfs"
    SFTP =         "sftp"
    FTP =          "ftp"
    WEBHDFS =      "webhdfs"
    SSH =          "ssh"
    SPARK =        "spark"
    TRINO =        "trino"
    GDRIVE =       "gdrive"
    DROPBOX =      "dropbox"
    ONEDRIVE =     "onedrive"
    SHAREPOINT =   "sharepoint"
    GITHUB =       "github"
