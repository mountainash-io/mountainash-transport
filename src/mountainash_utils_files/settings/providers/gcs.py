from typing import Optional, List, Any, Dict, Tuple
from upath import UPath

from pydantic import Field, SecretStr, field_validator
import re

from mountainash_settings import SettingsParameters
from ...settings import StorageAuthBase

from ...constants import CONST_STORAGE_PROVIDER_TYPE,CONST_STORAGE_AUTH_METHOD

from ..exceptions import (
    StorageValidationError,
    StorageConfigError
)

class GCSStorageAuthSettings(StorageAuthBase):
    """
    Google Cloud Storage authentication settings.

    Handles authentication configuration for Google Cloud Storage.
    Does not perform actual authentication or connection.
    """

    PROVIDER_TYPE: str = Field(default=CONST_STORAGE_PROVIDER_TYPE.GCS)

    # GCP Settings
    PROJECT_ID: str = Field(...)  # Required
    BUCKET_NAME: str = Field(...)  # Required
    LOCATION: Optional[str] = Field(default=None)
    API_ENDPOINT: Optional[str] = Field(default="storage.googleapis.com")

    # Authentication Settings
    AUTH_METHOD: str = Field(default=CONST_STORAGE_AUTH_METHOD.SERVICE_ACCOUNT)
    SERVICE_ACCOUNT_INFO: Optional[Dict[str, Any]] = Field(default=None)
    SERVICE_ACCOUNT_FILE: Optional[str] = Field(default=None)
    OAUTH_CREDENTIALS: Optional[Dict[str, Any]] = Field(default=None)
    OAUTH_TOKEN: Optional[SecretStr] = Field(default=None)

    # Security Settings
    # USE_ENCRYPTION: bool = Field(default=True)
    # ENCRYPTION_KEY: Optional[SecretStr] = Field(default=None)
    # KMS_KEY_NAME: Optional[str] = Field(default=None)

    # # Performance Settings
    # CHUNK_SIZE: int = Field(default=256 * 1024)  # 256 KB
    # RETRY_TIMEOUT: float = Field(default=120.0)
    # MAX_RETRY_DELAY: float = Field(default=60.0)
    # EXPONENTIAL_BACKOFF: bool = Field(default=True)

    # # Request Settings
    # READ_TIMEOUT: Optional[float] = Field(default=None)
    # CONNECT_TIMEOUT: Optional[float] = Field(default=None)
    # MAX_POOL_SIZE: int = Field(default=10)

    # # Advanced Settings
    # API_VERSION: str = Field(default="v1")
    # USE_RESUMABLE_UPLOAD: bool = Field(default=True)
    # RESUMABLE_THRESHOLD: int = Field(default=8 * 1024 * 1024)  # 8 MB
    # USER_PROJECT: Optional[str] = Field(default=None)

    def __init__(self,
                 config_files: Optional[str|UPath|List[str|UPath]|Tuple[str|UPath]] = None,
                 settings_parameters:   Optional[SettingsParameters] = None,
                #  _dummy: Optional[bool] = False,
                 **kwargs) -> None:


        super().__init__(config_files=config_files,
                         settings_parameters=settings_parameters,
                        #  _dummy=_dummy,
                         **kwargs)



    @field_validator("PROJECT_ID")
    def validate_project_id(cls, v: str) -> str:
        """Validate GCP project ID"""
        if not v:
            raise StorageValidationError(
                "Project ID is required",
                validation_type="project_id"
            )

        if not (6 <= len(v) <= 30):
            raise StorageValidationError(
                "Project ID must be between 6 and 30 characters",
                validation_type="project_id"
            )

        # Project ID format: can contain lowercase letters, digits, and hyphens
        if not re.match(r'^[a-z][a-z0-9-]{4,28}[a-z0-9]$', v):
            raise StorageValidationError(
                "Invalid project ID format. Must start with letter and contain only lowercase letters, numbers, and hyphens",
                validation_type="project_id"
            )

        return v

    @field_validator("BUCKET_NAME")
    def validate_bucket_name(cls, v: str) -> str:
        """Validate GCS bucket name"""
        if not v:
            raise StorageValidationError(
                "Bucket name is required",
                validation_type="bucket_name"
            )

        if not (3 <= len(v) <= 63):
            raise StorageValidationError(
                "Bucket name must be between 3 and 63 characters",
                validation_type="bucket_name"
            )

        # GCS bucket naming rules
        if not re.match(r'^[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$', v):
            raise StorageValidationError(
                "Invalid bucket name format. Must contain only lowercase letters, numbers, dots, hyphens, and underscores",
                validation_type="bucket_name"
            )

        if ".." in v:
            raise StorageValidationError(
                "Bucket name cannot contain consecutive dots",
                validation_type="bucket_name"
            )

        if re.match(r'\d+\.\d+\.\d+\.\d+$', v):
            raise StorageValidationError(
                "Bucket name cannot be formatted as an IP address",
                validation_type="bucket_name"
            )

        if v.startswith('goog'):
            raise StorageValidationError(
                "Bucket name cannot start with 'goog'",
                validation_type="bucket_name"
            )

        return v

    @field_validator("LOCATION")
    def validate_location(cls, v: Optional[str]) -> Optional[str]:
        """Validate GCS location if provided"""
        if v is not None:
            valid_regions = {
                # Multi-region locations
                'us', 'eu', 'asia',
                # Dual-region locations
                'us-central1', 'us-east1', 'europe-north1', 'europe-west1',
                'asia-northeast1', 'asia-southeast1',
                # Regional locations
                'northamerica-northeast1', 'southamerica-east1', 'europe-west2',
                'europe-west3', 'europe-west4', 'europe-west6', 'asia-east1',
                'asia-south1', 'australia-southeast1'
            }

            if v not in valid_regions:
                raise StorageValidationError(
                    f"Invalid location. Must be one of: {sorted(valid_regions)}",
                    validation_type="location"
                )

        return v

    # @field_validator("KMS_KEY_NAME")
    # def validate_kms_key_name(cls, v: Optional[str]) -> Optional[str]:
    #     """Validate KMS key name if provided"""
    #     if v is not None:
    #         # KMS key name format: projects/{project}/locations/{location}/keyRings/{keyring}/cryptoKeys/{key}
    #         pattern = r'^projects/[^/]+/locations/[^/]+/keyRings/[^/]+/cryptoKeys/[^/]+$'
    #         if not re.match(pattern, v):
    #             raise StorageValidationError(
    #                 "Invalid KMS key name format",
    #                 validation_type="kms_key_name"
    #             )

    #     return v

    # @field_validator("SERVICE_ACCOUNT_INFO")
    # def validate_service_account_info(cls, v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    #     """Validate service account info if provided"""
    #     if v is not None:
    #         required_fields = {
    #             'type', 'project_id', 'private_key_id', 'private_key',
    #             'client_email', 'client_id', 'auth_uri', 'token_uri'
    #         }

    #         missing_fields = required_fields - v.keys()
    #         if missing_fields:
    #             raise StorageValidationError(
    #                 f"Missing required service account fields: {missing_fields}",
    #                 validation_type="service_account_info"
    #             )

    #         # Validate service account type
    #         if v.get('type') != 'service_account':
    #             raise StorageValidationError(
    #                 "Invalid service account type",
    #                 validation_type="service_account_info"
    #             )

    #     return v

    # @field_validator("SERVICE_ACCOUNT_FILE")
    # def validate_service_account_file(cls, v: Optional[str]) -> Optional[str]:
    #     """Validate service account file path if provided"""
    #     if v is not None:
    #         try:
    #             path = UPath(v)
    #             if not path.exists():
    #                 raise StorageValidationError(
    #                     f"Service account file not found: {v}",
    #                     validation_type="service_account_file"
    #                 )

    #             # Try to load and validate JSON content
    #             with open(path) as f:
    #                 content = json.load(f)

    #             if content.get('type') != 'service_account':
    #                 raise StorageValidationError(
    #                     "Invalid service account file content",
    #                     validation_type="service_account_file"
    #                 )

    #         except Exception as e:
    #             if isinstance(e, StorageValidationError):
    #                 raise
    #             raise StorageValidationError(
    #                 f"Invalid service account file: {str(e)}",
    #                 validation_type="service_account_file"
    #             )

    #     return v

    def _init_provider_specific(self, reinitialise: bool) -> None:
        """Initialize provider-specific settings"""
        # Validate authentication method configuration
        if self.AUTH_METHOD == CONST_STORAGE_AUTH_METHOD.SERVICE_ACCOUNT:
            if not (self.SERVICE_ACCOUNT_INFO or self.SERVICE_ACCOUNT_FILE):
                raise StorageConfigError(
                    "Either service account info or file required for service account authentication",
                    provider=self.PROVIDER_TYPE
                )
        elif self.AUTH_METHOD == CONST_STORAGE_AUTH_METHOD.TOKEN:
            if not self.OAUTH_TOKEN:
                raise StorageConfigError(
                    "OAuth token required for token authentication",
                    provider=self.PROVIDER_TYPE
                )

        # # Validate encryption configuration
        # if self.USE_ENCRYPTION:
        #     if not (self.ENCRYPTION_KEY or self.KMS_KEY_NAME):
        #         raise StorageSecurityError(
        #             "Either encryption key or KMS key name required when encryption is enabled",
        #             security_check="encryption_config"
        #         )

        # # Validate performance settings
        # if self.CHUNK_SIZE < 256 * 1024:  # Min 256 KB
        #     raise StorageConfigError(
        #         "Chunk size must be at least 256 KB",
        #         provider=self.PROVIDER_TYPE
        #     )

        # if self.RESUMABLE_THRESHOLD < 8 * 1024 * 1024:  # Min 8 MB
        #     raise StorageConfigError(
        #         "Resumable upload threshold must be at least 8 MB",
        #         provider=self.PROVIDER_TYPE
        #     )

    def get_connection_url(self) -> str:
        """Generate GCS connection URL"""
        if self.API_ENDPOINT:
            base_url = f"https://{self.API_ENDPOINT}"
        else:
            base_url = "https://storage.googleapis.com"

        # Add bucket and project
        url = f"{base_url}/{self.BUCKET_NAME}"

        # # Add query parameters
        # params = []
        # if self.USER_PROJECT:
        #     params.append(f"userProject={self.USER_PROJECT}")

        # if params:
        #     url += "?" + "&".join(params)

        return url

    def get_connection_args(self) -> Dict[str, Any]:
        """Get connection arguments as dictionary"""
        args = super().get_connection_args()

        # Add GCS-specific arguments
        args.update({
            "project": self.PROJECT_ID,
            "bucket_name": self.BUCKET_NAME,
            "location": self.LOCATION,
            "api_endpoint": self.API_ENDPOINT,
            "api_version": self.API_VERSION
        })

        # Add authentication credentials based on method
        if self.AUTH_METHOD == CONST_STORAGE_AUTH_METHOD.SERVICE_ACCOUNT:
            if self.SERVICE_ACCOUNT_INFO:
                args["credentials_info"] = self.SERVICE_ACCOUNT_INFO
            elif self.SERVICE_ACCOUNT_FILE:
                args["credentials_path"] = self.SERVICE_ACCOUNT_FILE
        elif self.AUTH_METHOD == CONST_STORAGE_AUTH_METHOD.TOKEN:
            args["credentials"] = {
                "token": self.OAUTH_TOKEN
            }

        # # Add encryption settings if enabled
        # if self.USE_ENCRYPTION:
        #     if self.ENCRYPTION_KEY:
        #         args["encryption_key"] = self.ENCRYPTION_KEY
        #     if self.KMS_KEY_NAME:
        #         args["kms_key_name"] = self.KMS_KEY_NAME

        # # Add performance settings
        # args.update({
        #     "chunk_size": self.CHUNK_SIZE,
        #     "retry_timeout": self.RETRY_TIMEOUT,
        #     "max_retry_delay": self.MAX_RETRY_DELAY,
        #     "retry_exponential_backoff": self.EXPONENTIAL_BACKOFF,
        #     "read_timeout": self.READ_TIMEOUT,
        #     "connect_timeout": self.CONNECT_TIMEOUT,
        #     "max_pool_size": self.MAX_POOL_SIZE
        # })

        # # Add upload settings
        # if self.USE_RESUMABLE_UPLOAD:
        #     args.update({
        #         "resumable_upload": True,
        #         "resumable_threshold": self.RESUMABLE_THRESHOLD
        #     })

        return {k: v for k, v in args.items() if v is not None}

    # def _validate_permissions(self) -> None:
    #     """Validate storage permissions configuration"""
    #     # Define required permissions based on access type
    #     if self.ACCESS_TYPE == CONST_STORAGE_ACCESS_TYPE.READ_ONLY:
    #         required_perms = {"storage.objects.get", "storage.objects.list"}
    #     elif self.ACCESS_TYPE == CONST_STORAGE_ACCESS_TYPE.WRITE_ONLY:
    #         required_perms = {"storage.objects.create", "storage.objects.delete"}
    #     elif self.ACCESS_TYPE == CONST_STORAGE_ACCESS_TYPE.READ_WRITE:
    #         required_perms = {
    #             "storage.objects.get",
    #             "storage.objects.list",
    #             "storage.objects.create",
    #             "storage.objects.delete"
    #         }
    #     else:  # ADMIN
    #         required_perms = {"storage.objects.*"}

    #     # Validate against required permissions
    #     if not required_perms.issubset(self.REQUIRED_PERMISSIONS):
    #         raise StorageValidationError(
    #             f"Missing required permissions for access type {self.ACCESS_TYPE}",
    #             validation_type="permissions"
    #         )
