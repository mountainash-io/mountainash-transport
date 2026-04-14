from typing import Optional, Dict, Any, List, Tuple
from upath import UPath

from pydantic import Field, SecretStr, field_validator

from mountainash_settings import SettingsParameters
from ...settings import StorageAuthBase

from ...constants import CONST_STORAGE_PROVIDER_TYPE,CONST_STORAGE_AUTH_METHOD

from ..exceptions import (
    StorageValidationError,
    StorageSecurityError
)
# from mountainash_settings.auth.storage.utils.validation import StorageValidator

class MinIOStorageAuthSettings(StorageAuthBase):
    """
    MinIO storage authentication settings.

    Handles authentication configuration for MinIO object storage.
    Does not perform actual authentication or connection.
    """

    PROVIDER_TYPE: str = Field(default=CONST_STORAGE_PROVIDER_TYPE.MINIO)

    # Connection Settings
    ENDPOINT: str = Field(...)  # Required
    PORT: int = Field(default=9000)
    BUCKET: str = Field(...)  # Required
    REGION: Optional[str] = Field(default=None)

    # Authentication Settings
    AUTH_METHOD: str = Field(default=CONST_STORAGE_AUTH_METHOD.KEY)
    ACCESS_KEY: str = Field(...)  # Required
    SECRET_KEY: SecretStr = Field(...)  # Required

    # Security Settings
    USE_SSL: bool = Field(default=True)
    VERIFY_SSL: bool = Field(default=True)
    CERT_VERIFY: bool = Field(default=True)
    CERT_PATH: Optional[str] = Field(default=None)

    # # Advanced Settings
    # HTTP_CLIENT: Optional[str] = Field(default=None)  # For custom HTTP client
    # RETENTION_MODE: Optional[str] = Field(default=None)  # 'COMPLIANCE' or 'GOVERNANCE'
    # RETENTION_DURATION: Optional[int] = Field(default=None)  # In days

    # # Performance Settings
    # CONN_TIMEOUT: float = Field(default=30.0)  # Connection timeout in seconds
    # READ_TIMEOUT: float = Field(default=30.0)  # Read timeout in seconds
    # RETRY_COUNT: int = Field(default=3)

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
    # @field_validator("ENDPOINT")
    # def validate_endpoint(cls, v: str) -> str:
    #     """Validate MinIO endpoint format"""
    #     if not v:
    #         raise StorageValidationError(
    #             "Endpoint is required",
    #             validation_type="endpoint"
    #         )

    #     try:
    #         parsed = urlparse(v)
    #         if parsed.scheme and parsed.scheme not in {'http', 'https'}:
    #             raise StorageValidationError(
    #                 "Endpoint must use HTTP or HTTPS scheme",
    #                 validation_type="endpoint"
    #             )

    #         # Strip scheme if provided
    #         endpoint = parsed.netloc if parsed.netloc else parsed.path

    #         # Basic hostname validation
    #         if not StorageValidator.validate_url(
    #             f"https://{endpoint}",
    #             allowed_schemes={'https'},
    #             required_parts={'netloc'}
    #         ):
    #             raise StorageValidationError(
    #                 "Invalid endpoint format",
    #                 validation_type="endpoint"
    #             )

    #         return endpoint

    #     except Exception as e:
    #         if isinstance(e, StorageValidationError):
    #             raise
    #         raise StorageValidationError(
    #             f"Invalid endpoint: {str(e)}",
    #             validation_type="endpoint"
    #         )

    @field_validator("BUCKET")
    def validate_bucket(cls, v: str) -> str:
        """Validate MinIO bucket name"""
        if not v:
            raise StorageValidationError(
                "Bucket name is required",
                validation_type="bucket"
            )

        # MinIO bucket naming rules
        if not (3 <= len(v) <= 63):
            raise StorageValidationError(
                "Bucket name must be between 3 and 63 characters",
                validation_type="bucket"
            )

        if not v.islower():
            raise StorageValidationError(
                "Bucket name must be lowercase",
                validation_type="bucket"
            )

        # Check for valid characters (letters, numbers, dots, and hyphens)
        if not all(c.islower() or c.isdigit() or c in '.-' for c in v):
            raise StorageValidationError(
                "Bucket name can only contain lowercase letters, numbers, dots, and hyphens",
                validation_type="bucket"
            )

        # Must start and end with letter or number
        if not (v[0].isalnum() and v[-1].isalnum()):
            raise StorageValidationError(
                "Bucket name must start and end with a letter or number",
                validation_type="bucket"
            )

        return v

    # @field_validator("RETENTION_MODE")
    # def validate_retention_mode(cls, v: Optional[str]) -> Optional[str]:
    #     """Validate retention mode if specified"""
    #     if v is not None:
    #         valid_modes = {'COMPLIANCE', 'GOVERNANCE'}
    #         if v.upper() not in valid_modes:
    #             raise StorageValidationError(
    #                 f"Invalid retention mode. Must be one of: {valid_modes}",
    #                 validation_type="retention_mode"
    #             )
    #         return v.upper()
    #     return v

    # @field_validator("RETENTION_DURATION")
    # def validate_retention_duration(cls, v: Optional[int]) -> Optional[int]:
    #     """Validate retention duration if specified"""
    #     if v is not None:
    #         if v <= 0:
    #             raise StorageValidationError(
    #                 "Retention duration must be positive",
    #                 validation_type="retention_duration"
    #             )
    #     return v

    def _init_provider_specific(self, reinitialise: bool) -> None:
        """Initialize provider-specific settings"""
        # Validate SSL configuration if enabled
        if self.USE_SSL:
            if self.VERIFY_SSL and self.CERT_VERIFY and not self.CERT_PATH:
                raise StorageSecurityError(
                    "Certificate path required when SSL verification is enabled",
                    security_check="ssl_config"
                )

        # # Validate retention settings
        # if self.RETENTION_DURATION and not self.RETENTION_MODE:
        #     raise StorageConfigError(
        #         "Retention mode must be specified when duration is set",
        #         provider=self.PROVIDER_TYPE
        #     )

    def get_connection_url(self) -> str:

        """Generate MinIO connection URL"""
        scheme = 'https' if self.USE_SSL else 'http'
        base_url = f"{scheme}://{self.ENDPOINT}:{self.PORT}"

        # Add bucket if specified
        if self.BUCKET:
            base_url = f"{base_url}/{self.BUCKET}"

        # Add region if specified
        if self.REGION:
            base_url = f"{base_url}?region={self.REGION}"

        return base_url

    def get_connection_args(self) -> Dict[str, Any]:
        """Get connection arguments as dictionary"""
        args = super().get_connection_args()

        # Add MinIO-specific arguments
        args.update({
            "endpoint": self.ENDPOINT,
            "port": self.PORT,
            "bucket": self.BUCKET,
            "access_key": self.ACCESS_KEY,
            "secret_key": self.SECRET_KEY,
            "region": self.REGION,
            "secure": self.USE_SSL,
            "cert_verify": self.CERT_VERIFY,
            "cert_path": self.CERT_PATH,
            # "http_client": self.HTTP_CLIENT,
            # "connect_timeout": self.CONN_TIMEOUT,
            # "read_timeout": self.READ_TIMEOUT,
            # "retry_count": self.RETRY_COUNT
        })

        # # Add retention settings if specified
        # if self.RETENTION_MODE:
        #     args.update({
        #         "retention_mode": self.RETENTION_MODE,
        #         "retention_duration": self.RETENTION_DURATION
        #     })

        return {k: v for k, v in args.items() if v is not None}

    # def _validate_permissions(self) -> None:
    #     """
    #     Validate storage permissions configuration

    #     Note: This only validates the permission configuration,
    #     not the actual permissions on the MinIO server.
    #     """
    #     # Define required permissions based on access type
    #     if self.ACCESS_TYPE == CONST_STORAGE_ACCESS_TYPE.READ_ONLY:
    #         required_perms = {"read"}
    #     elif self.ACCESS_TYPE == CONST_STORAGE_ACCESS_TYPE.WRITE_ONLY:
    #         required_perms = {"write"}
    #     elif self.ACCESS_TYPE == CONST_STORAGE_ACCESS_TYPE.READ_WRITE:
    #         required_perms = {"read", "write"}
    #     else:  # ADMIN
    #         required_perms = {"read", "write", "admin"}

    #     # Validate against required permissions
    #     if not required_perms.issubset(self.REQUIRED_PERMISSIONS):
    #         raise StorageValidationError(
    #             f"Missing required permissions for access type {self.ACCESS_TYPE}",
    #             validation_type="permissions"
    #         )

    # def _test_connection(self) -> bool:
    #     """
    #     Validate connection parameters without making actual connection

    #     Returns:
    #         bool: True if configuration is valid
    #     """
    #     try:
    #         # Validate endpoint and port
    #         if not StorageValidator.validate_url(
    #             self.get_connection_url(),
    #             allowed_schemes={'http', 'https'},
    #             required_parts={'netloc'},
    #             max_port=65535
    #         ):
    #             return False

    #         # Validate timeout settings
    #         if not StorageValidator.validate_timeout_settings(
    #             connect_timeout=self.CONN_TIMEOUT,
    #             read_timeout=self.READ_TIMEOUT
    #         ):
    #             return False

    #         return True

    #     except Exception as e:
    #         if isinstance(e, StorageValidationError):
    #             raise
    #         return False
