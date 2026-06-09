#templates.py

from pydantic import Field
from pydantic_settings import BaseSettings
from functools import lru_cache

class StorageAuthTemplates(BaseSettings):
    """Templates for storage connection strings and configurations"""
    
    # Local Storage Templates
    LOCAL_PATH_TEMPLATE: str = Field(
        default="file://{root_path}"
    )
    
    # Cloud Storage Templates
    S3_URL_TEMPLATE: str = Field(
        default="s3://{access_key}:{secret_key}@{endpoint}/{bucket}"
    )
    
    AZURE_BLOB_URL_TEMPLATE: str = Field(
        default="azure://{account_name}.blob.core.windows.net/{container}"
    )
    
    AZURE_FILES_URL_TEMPLATE: str = Field(
        default="azure://{account_name}.file.core.windows.net/{share}"
    )
    
    GCS_URL_TEMPLATE: str = Field(
        default="gs://{bucket}"
    )
    
    # Network Storage Templates
    SFTP_URL_TEMPLATE: str = Field(
        default="sftp://{username}@{host}:{port}"
    )
    
    FTP_URL_TEMPLATE: str = Field(
        default="ftp://{username}@{host}:{port}"
    )
    
    SMB_URL_TEMPLATE: str = Field(
        default="smb://{username}@{server}/{share}"
    )
    
    NFS_URL_TEMPLATE: str = Field(
        default="nfs://{server}:{export_path}"
    )
    
    # Object Storage Templates
    MINIO_URL_TEMPLATE: str = Field(
        default="minio://{access_key}:{secret_key}@{endpoint}/{bucket}"
    )
    
    # Authentication Templates
    TOKEN_AUTH_TEMPLATE: str = Field(
        default="?token={token}"
    )
    
    CERT_AUTH_TEMPLATE: str = Field(
        default="?cert={cert_path}&key={key_path}"
    )
    
    # SSL/TLS Templates
    SSL_CONFIG_TEMPLATE: str = Field(
        default="?ssl=true&verify={verify_ssl}&ca_cert={ca_cert}"
    )
    
    # Composite Templates
    CONNECTION_STRING_TEMPLATE: str = Field(
        default="{protocol}://{credentials}@{host}:{port}/{path}"
    )
    
    AZURE_CONNECTION_STRING_TEMPLATE: str = Field(
        default="DefaultEndpointsProtocol=https;AccountName={account_name};AccountKey={account_key};EndpointSuffix=core.windows.net"
    )

@lru_cache()
def get_storage_auth_templates() -> StorageAuthTemplates:
    """Get cached instance of storage authentication templates"""
    return StorageAuthTemplates()