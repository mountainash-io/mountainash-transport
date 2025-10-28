#path: mountainash_settings/auth/storage/providers/cloud/s3.py

from typing import Optional, Dict, Any, List, Tuple
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

class S3StorageAuthSettings(StorageAuthBase):
    """
    AWS S3 storage authentication settings.

    Handles authentication configuration for AWS S3 storage.
    Does not perform actual authentication or connection.
    """

    PROVIDER_TYPE: str = Field(default=CONST_STORAGE_PROVIDER_TYPE.S3)

    # AWS Settings
    REGION: str =                   Field(...)  # Required
    BUCKET: str =                   Field(...)  # Required
    ENDPOINT_URL: Optional[str] =   Field(default=None)
    ACCOUNT_ID: str = Field(...)

    # Authentication Settings
    AUTH_METHOD: Optional[str] =            Field(default=CONST_STORAGE_AUTH_METHOD.KEY)
    ACCESS_KEY_ID: Optional[str] =          Field(default=None)
    SECRET_ACCESS_KEY: Optional[SecretStr] = Field(default=None)
    SESSION_TOKEN: Optional[SecretStr] =    Field(default=None)
    ROLE_ARN: Optional[str] =               Field(default=None)
    EXTERNAL_ID: Optional[str] =            Field(default=None)

    # S3 Specific Settings
    ADDRESSING_STYLE: str =         Field(default="auto")  # auto, path, virtual
    PATH_STYLE: bool =              Field(default=False)
    ACCELERATE_ENDPOINT: bool =     Field(default=False)
    DUALSTACK_ENDPOINT: bool =      Field(default=False)

    # Security Settings
    USE_SSL: bool = Field(default=False)
    # VERIFY_SSL: bool = Field(default=False)
    # CA_BUNDLE: Optional[str] = Field(default=None)

    # # Transfer Settings
    # MAX_POOL_CONNECTIONS: int = Field(default=10)
    # MULTIPART_THRESHOLD: int = Field(default=8 * 1024 * 1024)  # 8 MB
    # MULTIPART_CHUNKSIZE: int = Field(default=8 * 1024 * 1024)  # 8 MB
    # MAX_CONCURRENCY: int = Field(default=10)

    # # Timeout Settings
    # CONNECT_TIMEOUT: float = Field(default=30.0)
    # READ_TIMEOUT: float = Field(default=60.0)


    def __init__(self,
                 config_files: Optional[str|UPath|List[str|UPath]|Tuple[str|UPath]] = None,
                 settings_parameters:   Optional[SettingsParameters] = None,
                #  _dummy: Optional[bool] = False,
                 **kwargs) -> None:


        super().__init__(config_files=config_files,
                         settings_parameters=settings_parameters,
                        #  _dummy=_dummy,
                         **kwargs)




    def post_init(self, reinitialise: bool = False):
        super().post_init(reinitialise=reinitialise)


    # ## Field Validators ##
    # @field_validator("REGION")
    # def validate_region(cls, v: str) -> str:
    #     """Validate AWS region format"""
    #     if not v:
    #         raise StorageValidationError(
    #             "Region is required",
    #             validation_type="region"
    #         )

    #     # AWS region format validation
    #     if not re.match(r'^[a-z]{2}-[a-z]+-\d{1}$', v):
    #         raise StorageValidationError(
    #             "Invalid AWS region format (e.g., us-east-1)",
    #             validation_type="region"
    #         )

    #     return v

    # @field_validator("BUCKET")
    # def validate_bucket(cls, v: str) -> str:
    #     """Validate S3 bucket name"""
    #     if not v:
    #         raise StorageValidationError(
    #             "Bucket name is required",
    #             validation_type="bucket"
    #         )

    #     # S3 bucket naming rules
    #     if not (3 <= len(v) <= 63):
    #         raise StorageValidationError(
    #             "Bucket name must be between 3 and 63 characters",
    #             validation_type="bucket"
    #         )

    #     if not v[0].isalnum():
    #         raise StorageValidationError(
    #             "Bucket name must start with a letter or number",
    #             validation_type="bucket"
    #         )

    #     if not all(c.isalnum() or c in '.-' for c in v):
    #         raise StorageValidationError(
    #             "Bucket name can only contain letters, numbers, periods, and hyphens",
    #             validation_type="bucket"
    #         )

    #     if '..' in v:
    #         raise StorageValidationError(
    #             "Bucket name cannot contain consecutive periods",
    #             validation_type="bucket"
    #         )

    #     if re.match(r'\d+\.\d+\.\d+\.\d+$', v):
    #         raise StorageValidationError(
    #             "Bucket name cannot be formatted as an IP address",
    #             validation_type="bucket"
    #         )

    #     return v

    @field_validator("ROLE_ARN")
    def validate_role_arn(cls, v: Optional[str]) -> Optional[str]:
        """Validate AWS IAM role ARN format"""
        if v is not None:
            if not re.match(r'^arn:aws:iam::\d{12}:role/[\w+=,.@-]+$', v):
                raise StorageValidationError(
                    "Invalid IAM role ARN format",
                    validation_type="role_arn"
                )
        return v

    @field_validator("ADDRESSING_STYLE")
    def validate_addressing_style(cls, v: str) -> str:
        """Validate S3 addressing style"""
        valid_styles = {"auto", "path", "virtual"}
        if v not in valid_styles:
            raise StorageValidationError(
                f"Invalid addressing style. Must be one of: {valid_styles}",
                validation_type="addressing_style"
            )
        return v

    def _init_provider_specific(self, reinitialise: bool) -> None:
        """Initialize provider-specific settings"""
        # Validate authentication method
        if self.AUTH_METHOD == CONST_STORAGE_AUTH_METHOD.KEY:
            if not (self.ACCESS_KEY_ID and self.SECRET_ACCESS_KEY):
                raise StorageConfigError(
                    "Access key ID and secret access key required for key authentication",
                    provider=self.PROVIDER_TYPE
                )
        elif self.AUTH_METHOD == CONST_STORAGE_AUTH_METHOD.IAM:
            if not self.ROLE_ARN:
                raise StorageConfigError(
                    "Role ARN required for IAM authentication",
                    provider=self.PROVIDER_TYPE
                )

        # Validate endpoint configuration
        if self.ACCELERATE_ENDPOINT and self.PATH_STYLE:
            raise StorageConfigError(
                "Path-style addressing is not compatible with S3 acceleration",
                provider=self.PROVIDER_TYPE
            )

        # # Validate SSL configuration
        # if self.USE_SSL and self.VERIFY_SSL and not self.CA_BUNDLE:
        #     # This is just a warning condition, not an error
        #     pass

    def get_connection_url(self) -> str:
        """Generate S3 connection URL"""
        if self.ENDPOINT_URL:
            base_url = self.ENDPOINT_URL
        else:
            endpoint = "s3-accelerate" if self.ACCELERATE_ENDPOINT else "s3"
            if self.DUALSTACK_ENDPOINT:
                endpoint += ".dualstack"
            base_url = f"https://{endpoint}.{self.REGION}.amazonaws.com"

        # Add bucket if using virtual-hosted style
        if not self.PATH_STYLE and self.BUCKET:
            bucket_url = f"https://{self.BUCKET}.{base_url}"
            return bucket_url.replace("https://https://", "https://")  # Clean up possible double prefix

        return base_url

    def get_connection_args(self) -> Dict[str, Any]:
        """Get connection arguments as dictionary"""
        args = super().get_connection_args()

        # Add AWS-specific arguments
        args.update({
            "region_name": self.REGION,
            "bucket": self.BUCKET,
            # "use_ssl": self.USE_SSL,
            # "verify": self.CA_BUNDLE if self.VERIFY_SSL and self.CA_BUNDLE else self.VERIFY_SSL,
            "endpoint_url": self.ENDPOINT_URL,
            "config": {
                "s3": {
                    "addressing_style": self.ADDRESSING_STYLE,
                    "use_accelerate_endpoint": self.ACCELERATE_ENDPOINT,
                    "use_dualstack_endpoint": self.DUALSTACK_ENDPOINT,
                    # "max_pool_connections": self.MAX_POOL_CONNECTIONS
                }
            }
        })

        # Add authentication credentials
        if self.AUTH_METHOD == CONST_STORAGE_AUTH_METHOD.KEY:
            args.update({
                "aws_access_key_id": self.ACCESS_KEY_ID,
                "aws_secret_access_key": self.SECRET_ACCESS_KEY if self.SECRET_ACCESS_KEY else None,
                "aws_session_token": self.SESSION_TOKEN if self.SESSION_TOKEN else None
            })

        # # Add transfer configuration
        # args["config"]["s3"]["multipart_threshold"] = self.MULTIPART_THRESHOLD
        # args["config"]["s3"]["multipart_chunksize"] = self.MULTIPART_CHUNKSIZE
        # args["config"]["s3"]["max_concurrency"] = self.MAX_CONCURRENCY

        return {k: v for k, v in args.items() if v is not None}

    # def _validate_permissions(self) -> None:
    #     """Validate storage permissions configuration"""
    #     # Define required permissions based on access type
    #     if self.ACCESS_TYPE == CONST_STORAGE_ACCESS_TYPE.READ_ONLY:
    #         required_perms = {"s3:GetObject", "s3:ListBucket"}
    #     elif self.ACCESS_TYPE == CONST_STORAGE_ACCESS_TYPE.WRITE_ONLY:
    #         required_perms = {"s3:PutObject", "s3:DeleteObject"}
    #     elif self.ACCESS_TYPE == CONST_STORAGE_ACCESS_TYPE.READ_WRITE:
    #         required_perms = {
    #             "s3:GetObject", "s3:ListBucket",
    #             "s3:PutObject", "s3:DeleteObject"
    #         }
    #     else:  # ADMIN
    #         required_perms = {
    #             "s3:*"
    #         }

        # # Validate against required permissions
        # if not required_perms.issubset(self.REQUIRED_PERMISSIONS):
        #     raise StorageValidationError(
        #         f"Missing required permissions for access type {self.ACCESS_TYPE}",
        #         validation_type="permissions"
        #     )

    # def _test_connection(self) -> bool:
    #     """
    #     Validate connection parameters without making actual connection

    #     Returns:
    #         bool: True if configuration is valid
    #     """
    #     try:
    #         # Validate endpoint URL if provided
    #         if self.ENDPOINT_URL:
    #             if not StorageValidator.validate_url(
    #                 self.ENDPOINT_URL,
    #                 allowed_schemes={'http', 'https'},
    #                 required_parts={'netloc'}
    #             ):
    #                 return False

    #         # Validate timeout settings
    #         if not StorageValidator.validate_timeout_settings(
    #             connect_timeout=self.CONNECT_TIMEOUT,
    #             read_timeout=self.READ_TIMEOUT
    #         ):
    #             return False

    #         return True

    #     except Exception as e:
    #         if isinstance(e, StorageValidationError):
    #             raise
    #         return False
