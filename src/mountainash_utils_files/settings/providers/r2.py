#path: mountainash_settings/auth/storage/providers/cloud/r2.py

from typing import Optional, Dict, Any, List, Tuple
from upath import UPath
from pydantic import Field, SecretStr, field_validator
import re

from mountainash_settings import SettingsParameters
from ...settings import StorageAuthBase

from ...constants import CONST_STORAGE_AUTH_METHOD

from ..exceptions import (
    StorageValidationError,
    StorageConfigError
)

class R2StorageAuthSettings(StorageAuthBase):
    """
    Cloudflare R2 storage authentication settings.

    Handles authentication configuration for Cloudflare R2 storage.
    Does not perform actual authentication or connection.
    """

    PROVIDER_TYPE: str = Field(default="R2")  # Need to add R2 to CONST_STORAGE_PROVIDER_TYPE

    # R2 Settings
    ACCOUNT_ID: str = Field(...)  # Required - Cloudflare account ID
    BUCKET: str = Field(...)  # Required - R2 bucket name
    ENDPOINT_URL: str = Field(...)  # Required - Cloudflare R2 endpoint
    ENDPOINT: str = Field(...)  # Required - Cloudflare R2 endpoint


    # Authentication Settings
    AUTH_METHOD: str = Field(default=CONST_STORAGE_AUTH_METHOD.KEY)
    ACCESS_KEY_ID: str = Field(...)  # Required - R2 Access Key ID
    SECRET_ACCESS_KEY: SecretStr = Field(...)  # Required - R2 Secret Access Key
    TOKEN: Optional[SecretStr] = Field(default=None)

    # Connection Settings
    USE_SSL: bool = Field(default=False)
    VERIFY_SSL: bool = Field(default=True)
    PATH_STYLE: bool = Field(default=False)

    def __init__(self,
                 config_files: Optional[str|UPath|List[str|UPath]|Tuple[str|UPath]] = None,
                 settings_parameters: Optional[SettingsParameters] = None,
                 **kwargs) -> None:
        super().__init__(config_files=config_files,
                         settings_parameters=settings_parameters,
                         **kwargs)

    @field_validator("ACCOUNT_ID")
    def validate_account_id(cls, v: str) -> str:
        """Validate Cloudflare account ID format"""
        if not v:
            raise StorageValidationError(
                "Account ID is required",
                validation_type="account_id"
            )

        # Basic format validation - Cloudflare account IDs are typically hexadecimal strings
        if not re.match(r'^[0-9a-f]{32}$', v):
            raise StorageValidationError(
                "Invalid Cloudflare account ID format",
                validation_type="account_id"
            )

        return v

    @field_validator("BUCKET")
    def validate_bucket(cls, v: str) -> str:
        """Validate R2 bucket name"""
        if not v:
            raise StorageValidationError(
                "Bucket name is required",
                validation_type="bucket"
            )

        # R2 bucket naming rules (similar to S3)
        if not (3 <= len(v) <= 63):
            raise StorageValidationError(
                "Bucket name must be between 3 and 63 characters",
                validation_type="bucket"
            )

        if not v[0].isalnum():
            raise StorageValidationError(
                "Bucket name must start with a letter or number",
                validation_type="bucket"
            )

        if not all(c.isalnum() or c in '.-' for c in v):
            raise StorageValidationError(
                "Bucket name can only contain letters, numbers, periods, and hyphens",
                validation_type="bucket"
            )

        return v

    def _init_provider_specific(self, reinitialise: bool) -> None:
        """Initialize provider-specific settings"""
        # Validate authentication requirements
        if not (self.ACCESS_KEY_ID and self.SECRET_ACCESS_KEY):
            raise StorageConfigError(
                "Access key ID and secret access key required for R2 authentication",
                provider=self.PROVIDER_TYPE
            )

        # Validate endpoint URL
        if not self.ENDPOINT_URL:
            raise StorageConfigError(
                "Endpoint URL is required for Cloudflare R2",
                provider=self.PROVIDER_TYPE
            )

    def get_connection_url(self) -> str:
        """Generate R2 connection URL"""
        protocol = "https" if self.USE_SSL else "http"

        # Standard R2 endpoint format: https://<account_id>.r2.cloudflarestorage.com
        if not self.ENDPOINT_URL.startswith("http"):
            base_url = f"{protocol}://{self.ENDPOINT_URL}"
        else:
            base_url = self.ENDPOINT_URL

        # Add bucket if using virtual-hosted style
        if not self.PATH_STYLE and self.BUCKET:
            bucket_url = f"{protocol}://{self.BUCKET}.{base_url.replace(f'{protocol}://', '')}"
            return bucket_url

        return base_url

    def get_connection_args(self) -> Dict[str, Any]:
        """Get connection arguments as dictionary"""
        args = super().get_connection_args()

        # Add R2-specific arguments
        args.update({
            "endpoint_url": self.get_connection_url(),
            "bucket": self.BUCKET,
            "use_ssl": self.USE_SSL,
            "verify": self.VERIFY_SSL,
            "aws_access_key_id": self.ACCESS_KEY_ID,
            "aws_secret_access_key": self.SECRET_ACCESS_KEY if self.SECRET_ACCESS_KEY else None,
            "region_name": "auto"  # R2 doesn't use regions in the same way as S3
        })

        return {k: v for k, v in args.items() if v is not None}
