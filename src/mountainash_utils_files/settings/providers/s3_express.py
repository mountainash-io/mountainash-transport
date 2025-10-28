from typing import Optional, Dict, Any, List, Tuple
from upath import UPath
from pydantic import Field, field_validator
import re

from mountainash_settings import SettingsParameters
from ..exceptions import (
    StorageValidationError,
    StorageConfigError
)
from ...settings.providers.s3 import S3StorageAuthSettings

class S3ExpressStorageAuthSettings(S3StorageAuthSettings):
    """
    AWS S3 Express storage authentication settings.

    Handles authentication configuration for AWS S3 Express directory buckets.
    S3 Express uses directory buckets with a specific naming format and
    provides single-digit millisecond data access with hierarchical
    directory structure.
    """

    # Override the provider type with S3EXPRESS
    # Note: You'll need to add this constant to CONST_STORAGE_PROVIDER_TYPE
    PROVIDER_TYPE: str = Field(default="S3EXPRESS")

    # S3 Express doesn't support certain features of standard S3
    PATH_STYLE: bool = Field(default=False, const=False)
    ACCELERATE_ENDPOINT: bool = Field(default=False, const=False)
    DUALSTACK_ENDPOINT: bool = Field(default=False, const=False)

    # S3 Express requires virtual addressing style
    ADDRESSING_STYLE: str = Field(default="virtual")

    def __init__(self,
                 config_files: Optional[str|UPath|List[str|UPath]|Tuple[str|UPath]] = None,
                 settings_parameters: Optional[SettingsParameters] = None,
                 **kwargs) -> None:
        super().__init__(config_files=config_files,
                         settings_parameters=settings_parameters,
                         **kwargs)

    @field_validator("BUCKET")
    def validate_bucket(cls, v: str) -> str:
        """Validate S3 Express directory bucket name"""
        if not v:
            raise StorageValidationError(
                "Bucket name is required",
                validation_type="bucket"
            )

        # S3 Express directory bucket naming pattern: base-name--zonal-id--x-s3
        # e.g., my-bucket--us-east-1-az1--x-s3
        if not re.match(r'^[a-z0-9][a-z0-9-]{1,61}--[a-z]{2}[a-z0-9]+-[a-z]{2}\d--x-s3$', v):
            raise StorageValidationError(
                "Invalid S3 Express directory bucket name format. Must be: base-name--zonal-id--x-s3",
                validation_type="bucket"
            )

        return v

    @field_validator("ADDRESSING_STYLE")
    def validate_addressing_style(cls, v: str) -> str:
        """Validate S3 Express addressing style - only virtual is supported"""
        if v != "virtual":
            raise StorageValidationError(
                "S3 Express only supports virtual addressing style",
                validation_type="addressing_style"
            )
        return v

    @field_validator("PATH_STYLE")
    def validate_path_style(cls, v: bool) -> bool:
        """Validate path style setting - not supported in S3 Express"""
        if v:
            raise StorageValidationError(
                "Path-style addressing is not supported for S3 Express",
                validation_type="path_style"
            )
        return v

    @field_validator("ACCELERATE_ENDPOINT")
    def validate_accelerate_endpoint(cls, v: bool) -> bool:
        """Validate accelerate endpoint setting - not supported in S3 Express"""
        if v:
            raise StorageValidationError(
                "Accelerate endpoint is not supported for S3 Express",
                validation_type="accelerate_endpoint"
            )
        return v

    @field_validator("DUALSTACK_ENDPOINT")
    def validate_dualstack_endpoint(cls, v: bool) -> bool:
        """Validate dualstack endpoint setting - not supported in S3 Express"""
        if v:
            raise StorageValidationError(
                "Dualstack endpoint is not supported for S3 Express",
                validation_type="dualstack_endpoint"
            )
        return v

    def _init_provider_specific(self, reinitialise: bool) -> None:
        """Initialize provider-specific settings"""
        # Run the parent class initialization first
        super()._init_provider_specific(reinitialise)

        # Extract the zone ID from the bucket name
        bucket_parts = self.BUCKET.split('--')
        if len(bucket_parts) < 3 or not self.BUCKET.endswith('--x-s3'):
            raise StorageConfigError(
                f"Invalid S3 Express bucket name: {self.BUCKET}. Format should be base-name--zonal-id--x-s3",
                provider=self.PROVIDER_TYPE
            )

    def get_connection_url(self) -> str:
        """Generate S3 Express connection URL"""
        if self.ENDPOINT_URL:
            return self.ENDPOINT_URL

        # S3 Express uses a different endpoint format
        # For data operations: {bucket-name}.{region}.amazonaws.com
        return f"https://{self.BUCKET}.{self.REGION}.amazonaws.com"

    def get_connection_args(self) -> Dict[str, Any]:
        """Get connection arguments as dictionary"""
        args = super().get_connection_args()

        # Ensure proper S3 Express configuration
        if "config" not in args:
            args["config"] = {}
        if "s3" not in args["config"]:
            args["config"]["s3"] = {}

        # Override settings for S3 Express
        args["config"]["s3"]["addressing_style"] = "virtual"

        # Remove unsupported options
        args["config"]["s3"].pop("use_accelerate_endpoint", None)
        args["config"]["s3"].pop("use_dualstack_endpoint", None)

        # Extract zone ID from bucket name for client configuration
        bucket_parts = self.BUCKET.split('--')
        zone_id = bucket_parts[1] if len(bucket_parts) >= 3 else None

        # Add zone ID to arguments if available
        if zone_id:
            args["zone_id"] = zone_id

        return args
