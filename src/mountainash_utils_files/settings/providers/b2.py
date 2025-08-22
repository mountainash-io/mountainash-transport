from typing import Optional, List, Any, Dict, Tuple, Set
from upath import UPath
from pydantic import Field, SecretStr, field_validator
import re
from enum import Enum

from mountainash_settings import SettingsParameters
from ...settings import StorageAuthBase

from ...constants import CONST_STORAGE_PROVIDER_TYPE

from ..exceptions import (
    StorageValidationError,
    StorageConfigError
)

class B2CapabilityType(str, Enum):
    """B2 capability types"""
    LIST_BUCKETS = "listBuckets"
    LIST_FILES = "listFiles"
    READ_FILES = "readFiles"
    WRITE_FILES = "writeFiles"
    DELETE_FILES = "deleteFiles"
    READ_BUCKETS = "readBuckets"
    WRITE_BUCKETS = "writeBuckets"
    DELETE_BUCKETS = "deleteBuckets"
    SHARE_FILES = "shareFiles"
    READ_BUCKET_ENCRYPTION = "readBucketEncryption"
    WRITE_BUCKET_ENCRYPTION = "writeBucketEncryption"

class B2BucketType(str, Enum):
    """B2 bucket types"""
    PUBLIC = "allPublic"
    PRIVATE = "allPrivate"
    SNAPSHOT = "snapshot"

class B2ServerSideEncryption(str, Enum):
    """B2 server-side encryption modes"""
    NONE = "none"
    SSE_B2 = "SSE-B2"
    SSE_C = "SSE-C"

class BackblazeB2StorageAuthSettings(StorageAuthBase):
    """
    Backblaze B2 storage authentication settings.

    Handles authentication configuration for Backblaze B2 cloud storage.
    Does not perform actual authentication or connection.
    """

    PROVIDER_TYPE: str = Field(default=CONST_STORAGE_PROVIDER_TYPE.B2)

    # Authentication Settings
    APPLICATION_KEY_ID: str = Field(...)  # Required
    APPLICATION_KEY: SecretStr = Field(...)  # Required

    # Bucket Settings
    BUCKET_NAME: str = Field(...)  # Required
    BUCKET_ID: Optional[str] = Field(default=None)  # Optional, can be looked up
    BUCKET_TYPE: str = Field(default=B2BucketType.PRIVATE)

    # Endpoint Settings
    API_ENDPOINT: Optional[str] = Field(default="api.backblazeb2.com")
    DOWNLOAD_ENDPOINT: Optional[str] = Field(default=None)  # Set by auth response

    # Encryption Settings
    SERVER_SIDE_ENCRYPTION: str = Field(default=B2ServerSideEncryption.SSE_B2)
    CUSTOMER_KEY: Optional[SecretStr] = Field(default=None)  # For SSE-C
    KEY_ID: Optional[str] = Field(default=None)  # For key identification

    # Lifecycle Settings
    FILE_RETENTION_DAYS: Optional[int] = Field(default=None)
    FILE_PREFIX: Optional[str] = Field(default=None)
    DELETE_OLD_VERSIONS: bool = Field(default=False)
    KEEP_LAST_N_VERSIONS: Optional[int] = Field(default=None)

    # Performance Settings
    # RECOMMENDED_PART_SIZE: int = Field(default=100 * 1024 * 1024)  # 100MB
    # MIN_PART_SIZE: int = Field(default=5 * 1024 * 1024)  # 5MB
    # MAX_CONNECTIONS: int = Field(default=4)

    # # Cache Settings
    # AUTH_CACHE_TTL: int = Field(default=86400)  # 24 hours
    # UPLOAD_URL_CACHE_TTL: int = Field(default=1800)  # 30 minutes

    # # Rate Limiting
    # MAX_RETRIES: int = Field(default=5)
    # RETRY_BACKOFF_FACTOR: float = Field(default=1.5)
    # MIN_RETRY_DELAY: float = Field(default=1.0)
    # MAX_RETRY_DELAY: float = Field(default=60.0)

    # # CORS Settings
    # ALLOWED_ORIGINS: Optional[List[str]] = Field(default=None)
    # ALLOWED_OPERATIONS: Optional[List[str]] = Field(default=None)
    # EXPOSE_HEADERS: Optional[List[str]] = Field(default=None)
    # MAX_AGE_SECONDS: int = Field(default=3600)

    # Capabilities
    CAPABILITIES: Set[str] = Field(
        default={
            B2CapabilityType.LIST_FILES,
            B2CapabilityType.READ_FILES,
            B2CapabilityType.WRITE_FILES
        }
    )

    def __init__(self,
                 config_files: Optional[str|UPath|List[str|UPath]|Tuple[str|UPath]] = None,
                 settings_parameters:   Optional[SettingsParameters] = None,
                #  _dummy: Optional[bool] = False,
                 **kwargs) -> None:


        super().__init__(config_files=config_files,
                         settings_parameters=settings_parameters,
                        #  _dummy=_dummy,
                         **kwargs)



    ## Field Validators ##
    @field_validator("APPLICATION_KEY_ID")
    def validate_key_id(cls, v: str) -> str:
        """Validate application key ID"""
        if not v:
            raise StorageValidationError(
                "Application key ID is required",
                validation_type="application_key_id"
            )

        if not re.match(r'^[a-zA-Z0-9]{24}$', v):
            raise StorageValidationError(
                "Invalid application key ID format",
                validation_type="application_key_id"
            )

        return v

    @field_validator("BUCKET_NAME")
    def validate_bucket_name(cls, v: str) -> str:
        """Validate bucket name"""
        if not v:
            raise StorageValidationError(
                "Bucket name is required",
                validation_type="bucket_name"
            )

        if not (6 <= len(v) <= 50):
            raise StorageValidationError(
                "Bucket name must be between 6 and 50 characters",
                validation_type="bucket_name"
            )

        if not re.match(r'^[a-z0-9-]+$', v):
            raise StorageValidationError(
                "Bucket name can only contain lowercase letters, numbers, and hyphens",
                validation_type="bucket_name"
            )

        return v

    @field_validator("BUCKET_ID")
    def validate_bucket_id(cls, v: Optional[str]) -> Optional[str]:
        """Validate bucket ID if provided"""
        if v is not None:
            if not re.match(r'^[a-zA-Z0-9]{24}$', v):
                raise StorageValidationError(
                    "Invalid bucket ID format",
                    validation_type="bucket_id"
                )

        return v

    @field_validator("BUCKET_TYPE")
    def validate_bucket_type(cls, v: str) -> str:
        """Validate bucket type"""
        try:
            return B2BucketType(v)
        except ValueError:
            raise StorageValidationError(
                f"Invalid bucket type. Must be one of: {[t.value for t in B2BucketType]}",
                validation_type="bucket_type"
            )

    @field_validator("SERVER_SIDE_ENCRYPTION")
    def validate_encryption(cls, v: str) -> str:
        """Validate server-side encryption setting"""
        try:
            return B2ServerSideEncryption(v)
        except ValueError:
            raise StorageValidationError(
                f"Invalid encryption type. Must be one of: {[t.value for t in B2ServerSideEncryption]}",
                validation_type="encryption"
            )

    @field_validator("FILE_RETENTION_DAYS")
    def validate_retention_days(cls, v: Optional[int]) -> Optional[int]:
        """Validate file retention days"""
        if v is not None:
            if v < 1:
                raise StorageValidationError(
                    "File retention days must be at least 1",
                    validation_type="retention_days"
                )
            if v > 36500:  # 100 years
                raise StorageValidationError(
                    "File retention days cannot exceed 36500 (100 years)",
                    validation_type="retention_days"
                )
        return v

    @field_validator("CAPABILITIES")
    def validate_capabilities(cls, v: Set[str]) -> Set[str]:
        """Validate capabilities"""
        valid_capabilities = {cap.value for cap in B2CapabilityType}
        invalid_caps = v - valid_capabilities
        if invalid_caps:
            raise StorageValidationError(
                f"Invalid capabilities: {invalid_caps}",
                validation_type="capabilities"
            )
        return v

    def _init_provider_specific(self, reinitialise: bool) -> None:
        """Initialize provider-specific settings"""
        # Validate encryption configuration
        if self.SERVER_SIDE_ENCRYPTION == B2ServerSideEncryption.SSE_C:
            if not self.CUSTOMER_KEY:
                raise StorageConfigError(
                    "Customer key required for SSE-C encryption",
                    provider=self.PROVIDER_TYPE
                )

        # Validate lifecycle settings
        if self.DELETE_OLD_VERSIONS and not self.KEEP_LAST_N_VERSIONS:
            raise StorageConfigError(
                "Must specify number of versions to keep when deleting old versions",
                provider=self.PROVIDER_TYPE
            )

        # Validate capabilities for bucket type
        if self.BUCKET_TYPE == B2BucketType.PUBLIC:
            if B2CapabilityType.WRITE_FILES in self.CAPABILITIES:
                raise StorageConfigError(
                    "Public buckets cannot have write capabilities",
                    provider=self.PROVIDER_TYPE
                )

        # # Validate CORS settings
        # if self.ALLOWED_ORIGINS and not self.ALLOWED_OPERATIONS:
        #     raise StorageConfigError(
        #         "Must specify allowed operations with CORS origins",
        #         provider=self.PROVIDER_TYPE
        #     )

    def get_connection_url(self) -> str:
        """Generate B2 connection URL"""
        endpoint = self.DOWNLOAD_ENDPOINT or self.API_ENDPOINT
        return f"b2://{endpoint}/{self.BUCKET_NAME}"

    def get_connection_args(self) -> Dict[str, Any]:
        """Get connection arguments as dictionary"""
        args = super().get_connection_args()

        # Add B2-specific arguments
        args.update({
            "application_key_id": self.APPLICATION_KEY_ID,
            "application_key": self.APPLICATION_KEY,
            "bucket_name": self.BUCKET_NAME,
            "bucket_id": self.BUCKET_ID,
            "bucket_type": self.BUCKET_TYPE,
            "api_endpoint": self.API_ENDPOINT,
            "download_endpoint": self.DOWNLOAD_ENDPOINT
        })

        # Add encryption settings
        args.update({
            "server_side_encryption": self.SERVER_SIDE_ENCRYPTION,
            "key_id": self.KEY_ID
        })

        if self.SERVER_SIDE_ENCRYPTION == B2ServerSideEncryption.SSE_C:
            args["customer_key"] = self.CUSTOMER_KEY

        # Add lifecycle settings
        if self.FILE_RETENTION_DAYS:
            args["lifecycle_rules"] = {
                "daysFromHiding": self.FILE_RETENTION_DAYS,
                "fileNamePrefix": self.FILE_PREFIX or ""
            }

        if self.DELETE_OLD_VERSIONS:
            args.update({
                "delete_old_versions": True,
                "keep_versions": self.KEEP_LAST_N_VERSIONS
            })

        # # Add performance settings
        # args.update({
        #     "recommended_part_size": self.RECOMMENDED_PART_SIZE,
        #     "min_part_size": self.MIN_PART_SIZE,
        #     "max_connections": self.MAX_CONNECTIONS,
        #     "auth_cache_ttl": self.AUTH_CACHE_TTL,
        #     "upload_url_cache_ttl": self.UPLOAD_URL_CACHE_TTL
        # })

        # # Add retry settings
        # args.update({
        #     "max_retries": self.MAX_RETRIES,
        #     "retry_backoff_factor": self.RETRY_BACKOFF_FACTOR,
        #     "min_retry_delay": self.MIN_RETRY_DELAY,
        #     "max_retry_delay": self.MAX_RETRY_DELAY
        # })

        # # Add CORS settings if configured
        # if self.ALLOWED_ORIGINS:
        #     args["cors_rules"] = {
        #         "corsRules": [{
        #             "allowedOrigins": self.ALLOWED_ORIGINS,
        #             "allowedOperations": self.ALLOWED_OPERATIONS,
        #             "exposeHeaders": self.EXPOSE_HEADERS,
        #             "maxAgeSeconds": self.MAX_AGE_SECONDS
        #         }]
        #     }

        return {k: v for k, v in args.items() if v is not None}

    # def _validate_permissions(self) -> None:
    #     """Validate storage permissions configuration"""
    #     # Convert access type to required capabilities
    #     if self.ACCESS_TYPE == CONST_STORAGE_ACCESS_TYPE.READ_ONLY:
    #         required_caps = {
    #             B2CapabilityType.LIST_FILES,
    #             B2CapabilityType.READ_FILES
    #         }
    #     elif self.ACCESS_TYPE == CONST_STORAGE_ACCESS_TYPE.WRITE_ONLY:
    #         required_caps = {
    #             B2CapabilityType.WRITE_FILES
    #         }
    #     elif self.ACCESS_TYPE == CONST_STORAGE_ACCESS_TYPE.READ_WRITE:
    #         required_caps = {
    #             B2CapabilityType.LIST_FILES,
    #             B2CapabilityType.READ_FILES,
    #             B2CapabilityType.WRITE_FILES
    #         }
    #     else:  # ADMIN
    #         required_caps = {cap.value for cap in B2CapabilityType}

    #     # Validate against required capabilities
    #     if not required_caps.issubset(self.CAPABILITIES):
    #         raise StorageValidationError(
    #             f"Missing required capabilities for access type {self.ACCESS_TYPE}",
    #             validation_type="capabilities"
    #         )

    # def _test_connection(self) -> bool:
    #     """
    #     Validate connection parameters without making actual connection

    #     Returns:
    #         bool: True if configuration is valid
    #     """
    #     try:
    #         # Validate connection URL
    #         if not StorageValidator.validate_url(
    #             self.get_connection_url(),
    #             allowed_schemes={'b2'},
    #             required_parts={'netloc'}
    #         ):
    #             return False

    #         # Validate part sizes
    #         if not (5 * 1024 * 1024 <= self.MIN_PART_SIZE <= self.RECOMMENDED_PART_SIZE):
    #             return False

    #         if not (self.RECOMMENDED_PART_SIZE <= 5 * 1024 * 1024 * 1024):  # 5GB max
    #             return False

    #         # Validate retry settings
    #         if not StorageValidator.validate_retry_settings(
    #             max_retries=self.MAX_RETRIES,
    #             retry_delay=self.MIN_RETRY_DELAY,
    #             max_delay=self.MAX_RETRY_DELAY
    #         ):
    #             return False

    #         return True

    #     except Exception as e:
    #         if isinstance(e, StorageValidationError):
    #             raise
    #         return False
