
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
# from mountainash_settings.settings.auth.storage.utils.validation import StorageValidator

class AzureBlobStorageAuthSettings(StorageAuthBase):
    """
    Azure Blob Storage authentication settings.

    Handles authentication configuration for Azure Blob Storage.
    Does not perform actual authentication or connection.
    """

    PROVIDER_TYPE: str = Field(default=CONST_STORAGE_PROVIDER_TYPE.AZURE_BLOB)

    # Azure Settings
    ACCOUNT_NAME: str = Field(...)  # Required
    CONTAINER_NAME: str = Field(...)  # Required

    # Authentication Settings
    AUTH_METHOD: str = Field(default=CONST_STORAGE_AUTH_METHOD.KEY)
    ACCOUNT_KEY: Optional[SecretStr] = Field(default=None)
    CONNECTION_STRING: Optional[SecretStr] = Field(default=None)
    SAS_TOKEN: Optional[SecretStr] = Field(default=None)

    # AAD Settings
    TENANT_ID: Optional[str] = Field(default=None)
    CLIENT_ID: Optional[str] = Field(default=None)
    CLIENT_SECRET: Optional[SecretStr] = Field(default=None)

    # Endpoint Settings
    ENDPOINT_SUFFIX: str = Field(default="core.windows.net")
    CUSTOM_DOMAIN: Optional[str] = Field(default=None)

    # # Performance Settings
    # MAX_CHUNK_SIZE: int = Field(default=4 * 1024 * 1024)  # 4 MB
    # MAX_SINGLE_PUT_SIZE: int = Field(default=64 * 1024 * 1024)  # 64 MB
    # MIN_LARGE_BLOCK_UPLOAD_THRESHOLD: int = Field(default=128 * 1024 * 1024)  # 128 MB

    # # Retry Settings
    # MAX_RETRIES: int = Field(default=3)
    # RETRY_WAIT: int = Field(default=1)
    # MAX_RETRY_WAIT: int = Field(default=60)

    # # Security Settings
    # REQUIRE_ENCRYPTION: bool = Field(default=True)
    # KEY_ENCRYPTION_KEY: Optional[SecretStr] = Field(default=None)
    # KEY_RESOLVER_FUNCTION: Optional[str] = Field(default=None)

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
    @field_validator("ACCOUNT_NAME")
    def validate_account_name(cls, v: str) -> str:
        """Validate Azure Storage account name"""
        if not v:
            raise StorageValidationError(
                "Account name is required",
                validation_type="account_name"
            )

        if not (3 <= len(v) <= 24):
            raise StorageValidationError(
                "Account name must be between 3 and 24 characters",
                validation_type="account_name"
            )

        if not v.islower():
            raise StorageValidationError(
                "Account name must be lowercase",
                validation_type="account_name"
            )

        if not all(c.isalnum() for c in v):
            raise StorageValidationError(
                "Account name can only contain letters and numbers",
                validation_type="account_name"
            )

        return v

    @field_validator("CONTAINER_NAME")
    def validate_container_name(cls, v: str) -> str:
        """Validate Azure Storage container name"""
        if not v:
            raise StorageValidationError(
                "Container name is required",
                validation_type="container_name"
            )

        if not (3 <= len(v) <= 63):
            raise StorageValidationError(
                "Container name must be between 3 and 63 characters",
                validation_type="container_name"
            )

        if not v.islower():
            raise StorageValidationError(
                "Container name must be lowercase",
                validation_type="container_name"
            )

        if not re.match(r'^[a-z0-9](?!.*--)[a-z0-9-]{1,61}[a-z0-9]$', v):
            raise StorageValidationError(
                "Invalid container name format. Must contain only lowercase letters, numbers, and single hyphens",
                validation_type="container_name"
            )

        return v

    @field_validator("ENDPOINT_SUFFIX")
    def validate_endpoint_suffix(cls, v: str) -> str:
        """Validate endpoint suffix"""
        if not v:
            raise StorageValidationError(
                "Endpoint suffix is required",
                validation_type="endpoint_suffix"
            )

        if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9](\.[a-z0-9][a-z0-9-]*[a-z0-9])*$', v):
            raise StorageValidationError(
                "Invalid endpoint suffix format",
                validation_type="endpoint_suffix"
            )

        return v

    # @field_validator("CUSTOM_DOMAIN")
    # def validate_custom_domain(cls, v: Optional[str]) -> Optional[str]:
    #     """Validate custom domain if provided"""
    #     if v is not None:
    #         if not StorageValidator.validate_url(
    #             f"https://{v}",
    #             allowed_schemes={'https'},
    #             required_parts={'netloc'}
    #         ):
    #             raise StorageValidationError(
    #                 "Invalid custom domain format",
    #                 validation_type="custom_domain"
    #             )
    #     return v



    def _init_provider_specific(self, reinitialise: bool) -> None:
        """Initialize provider-specific settings"""
        # Validate authentication method configuration
        if self.AUTH_METHOD == CONST_STORAGE_AUTH_METHOD.KEY:
            if not self.ACCOUNT_KEY and not self.CONNECTION_STRING:
                raise StorageConfigError(
                    "Either account key or connection string required for key authentication",
                    provider=self.PROVIDER_TYPE
                )
        elif self.AUTH_METHOD == CONST_STORAGE_AUTH_METHOD.TOKEN:
            if not self.SAS_TOKEN:
                raise StorageConfigError(
                    "SAS token required for token authentication",
                    provider=self.PROVIDER_TYPE
                )
        elif self.AUTH_METHOD == CONST_STORAGE_AUTH_METHOD.MANAGED_IDENTITY:
            if not (self.CLIENT_ID and self.TENANT_ID and self.CLIENT_SECRET):
                raise StorageConfigError(
                    "Client ID, tenant ID, and client secret required for managed identity authentication",
                    provider=self.PROVIDER_TYPE
                )

        # # Validate encryption settings
        # if self.REQUIRE_ENCRYPTION and not (self.KEY_ENCRYPTION_KEY or self.KEY_RESOLVER_FUNCTION):
        #     raise StorageSecurityError(
        #         "Encryption key or key resolver required when encryption is enabled",
        #         security_check="encryption_config"
        #     )

    def get_connection_url(self) -> str:
        """Generate Azure Blob Storage connection URL"""
        if self.CUSTOM_DOMAIN:
            base_url = f"https://{self.CUSTOM_DOMAIN}"
        else:
            base_url = f"https://{self.ACCOUNT_NAME}.blob.{self.ENDPOINT_SUFFIX}"

        # Add container if specified
        if self.CONTAINER_NAME:
            base_url = f"{base_url}/{self.CONTAINER_NAME}"

        return base_url

    def get_connection_args(self) -> Dict[str, Any]:
        """Get connection arguments as dictionary"""
        args = super().get_connection_args()

        # Add Azure-specific arguments
        args.update({
            "account_name": self.ACCOUNT_NAME,
            "container_name": self.CONTAINER_NAME,
            "endpoint_suffix": self.ENDPOINT_SUFFIX,
            "custom_domain": self.CUSTOM_DOMAIN,
            # "require_encryption": self.REQUIRE_ENCRYPTION,
            # "max_chunk_size": self.MAX_CHUNK_SIZE,
            # "max_single_put_size": self.MAX_SINGLE_PUT_SIZE,
            # "min_large_block_upload_threshold": self.MIN_LARGE_BLOCK_UPLOAD_THRESHOLD
        })

        # Add authentication credentials based on method
        if self.AUTH_METHOD == CONST_STORAGE_AUTH_METHOD.KEY:
            if self.CONNECTION_STRING:
                args["connection_string"] = self.CONNECTION_STRING
            else:
                args["credential"] = self.ACCOUNT_KEY
        elif self.AUTH_METHOD == CONST_STORAGE_AUTH_METHOD.TOKEN:
            args["sas_token"] = self.SAS_TOKEN
        elif self.AUTH_METHOD == CONST_STORAGE_AUTH_METHOD.MANAGED_IDENTITY:
            args.update({
                "tenant_id": self.TENANT_ID,
                "client_id": self.CLIENT_ID,
                "client_secret": self.CLIENT_SECRET
            })

        # # Add encryption settings if required
        # if self.REQUIRE_ENCRYPTION:
        #     if self.KEY_ENCRYPTION_KEY:
        #         args["key_encryption_key"] = self.KEY_ENCRYPTION_KEY
        #     if self.KEY_RESOLVER_FUNCTION:
        #         args["key_resolver_function"] = self.KEY_RESOLVER_FUNCTION

        # # Add retry settings
        # args.update({
        #     "max_retries": self.MAX_RETRIES,
        #     "retry_wait": self.RETRY_WAIT,
        #     "max_retry_wait": self.MAX_RETRY_WAIT
        # })

        return {k: v for k, v in args.items() if v is not None}

    # def _validate_permissions(self) -> None:
    #     """Validate storage permissions configuration"""
    #     # Define required permissions based on access type
    #     if self.ACCESS_TYPE == CONST_STORAGE_ACCESS_TYPE.READ_ONLY:
    #         required_perms = {"Storage.Blobs.Read"}
    #     elif self.ACCESS_TYPE == CONST_STORAGE_ACCESS_TYPE.WRITE_ONLY:
    #         required_perms = {"Storage.Blobs.Create", "Storage.Blobs.Delete"}
    #     elif self.ACCESS_TYPE == CONST_STORAGE_ACCESS_TYPE.READ_WRITE:
    #         required_perms = {
    #             "Storage.Blobs.Read",
    #             "Storage.Blobs.Create",
    #             "Storage.Blobs.Delete"
    #         }
    #     else:  # ADMIN
    #         required_perms = {"Storage.Blobs.FullControl"}

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
    #         # Validate connection URL
    #         if not StorageValidator.validate_url(
    #             self.get_connection_url(),
    #             allowed_schemes={'https'},
    #             required_parts={'netloc'}
    #         ):
    #             return False

    #         # Validate performance settings
    #         if not (0 < self.MAX_CHUNK_SIZE <= 100 * 1024 * 1024):  # Max 100MB
    #             return False

    #         if not (0 < self.MAX_SINGLE_PUT_SIZE <= 256 * 1024 * 1024):  # Max 256MB
    #             return False

    #         # Validate retry settings
    #         if not StorageValidator.validate_retry_settings(
    #             max_retries=self.MAX_RETRIES,
    #             retry_delay=self.RETRY_WAIT,
    #             max_delay=self.MAX_RETRY_WAIT
    #         ):
    #             return False

    #         return True

    #     except Exception as e:
    #         if isinstance(e, StorageValidationError):
    #             raise
    #         return False
