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

class AzureFilesStorageAuthSettings(StorageAuthBase):
    """
    Azure Files storage authentication settings.

    Handles authentication configuration for Azure Files storage.
    Does not perform actual authentication or connection.
    """

    PROVIDER_TYPE: str = Field(default=CONST_STORAGE_PROVIDER_TYPE.AZURE_FILES)

    # Azure Settings
    ACCOUNT_NAME: str = Field(...)  # Required
    SHARE_NAME: str = Field(...)    # Required

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

    # # SMB Settings
    # SMB_VERSION: Optional[str] = Field(default="3.0")  # 2.1, 3.0, 3.1.1
    # SMB_ENCRYPTION: bool = Field(default=True)
    # SMB_CONTINUOUS_AVAILABILITY: bool = Field(default=True)
    # SMB_MULTICHANNEL: bool = Field(default=True)

    # # Performance Settings
    # MAX_RANGE_SIZE: int = Field(default=4 * 1024 * 1024)  # 4 MB
    # MAX_SINGLE_GET_SIZE: int = Field(default=32 * 1024 * 1024)  # 32 MB
    # ENABLE_WRITE_BUFFERING: bool = Field(default=True)
    # WRITE_BUFFER_SIZE: int = Field(default=4 * 1024 * 1024)  # 4 MB

    # # Security Settings
    # REQUIRE_ENCRYPTION: bool = Field(default=True)
    # HTTPS_ONLY: bool = Field(default=True)
    # ENABLE_KERBEROS: bool = Field(default=False)
    # KERBEROS_TICKET_PATH: Optional[str] = Field(default=None)

    # # Retry Settings
    # MAX_RETRIES: int = Field(default=3)
    # RETRY_WAIT: int = Field(default=1)
    # MAX_RETRY_WAIT: int = Field(default=60)

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

    @field_validator("SHARE_NAME")
    def validate_share_name(cls, v: str) -> str:
        """Validate Azure Files share name"""
        if not v:
            raise StorageValidationError(
                "Share name is required",
                validation_type="share_name"
            )

        if not (3 <= len(v) <= 63):
            raise StorageValidationError(
                "Share name must be between 3 and 63 characters",
                validation_type="share_name"
            )

        if not v.islower():
            raise StorageValidationError(
                "Share name must be lowercase",
                validation_type="share_name"
            )

        if not re.match(r'^[a-z0-9](?!.*--)[a-z0-9-]{1,61}[a-z0-9]$', v):
            raise StorageValidationError(
                "Invalid share name format. Must contain only lowercase letters, numbers, and single hyphens",
                validation_type="share_name"
            )

        return v

    # @field_validator("SMB_VERSION")
    # def validate_smb_version(cls, v: Optional[str]) -> Optional[str]:
    #     """Validate SMB version"""
    #     if v is not None:
    #         valid_versions = {"2.1", "3.0", "3.1.1"}
    #         if v not in valid_versions:
    #             raise StorageValidationError(
    #                 f"Invalid SMB version. Must be one of: {valid_versions}",
    #                 validation_type="smb_version"
    #             )
    #     return v

    # @field_validator("KERBEROS_TICKET_PATH")
    # def validate_kerberos_ticket_path(cls, v: Optional[str]) -> Optional[str]:
    #     """Validate Kerberos ticket path if Kerberos is enabled"""
    #     if v is not None:
    #         if not StorageValidator.validate_path(
    #             v,
    #             must_exist=True,
    #             writable=False,
    #             allowed_types={"file"}
    #         ):
    #             raise StorageValidationError(
    #                 "Invalid Kerberos ticket path",
    #                 validation_type="kerberos_ticket_path"
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

        # # Validate Kerberos configuration
        # if self.ENABLE_KERBEROS and not self.KERBEROS_TICKET_PATH:
        #     raise StorageConfigError(
        #         "Kerberos ticket path required when Kerberos is enabled",
        #         provider=self.PROVIDER_TYPE
        #     )

        # # Validate SMB security settings
        # if self.SMB_VERSION == "2.1" and self.SMB_ENCRYPTION:
        #     raise StorageConfigError(
        #         "SMB encryption is not supported with SMB 2.1",
        #         provider=self.PROVIDER_TYPE
        #     )

    def get_connection_url(self) -> str:
        """Generate Azure Files connection URL"""
        if self.CUSTOM_DOMAIN:
            base_url = f"https://{self.CUSTOM_DOMAIN}"
        else:
            base_url = f"https://{self.ACCOUNT_NAME}.file.{self.ENDPOINT_SUFFIX}"

        # Add share if specified
        if self.SHARE_NAME:
            base_url = f"{base_url}/{self.SHARE_NAME}"

        return base_url

    def get_connection_args(self) -> Dict[str, Any]:
        """Get connection arguments as dictionary"""
        args = super().get_connection_args()

        # Add Azure Files specific arguments
        args.update({
            "account_name": self.ACCOUNT_NAME,
            "share_name": self.SHARE_NAME,
            "endpoint_suffix": self.ENDPOINT_SUFFIX,
            "custom_domain": self.CUSTOM_DOMAIN,
            # "require_encryption": self.REQUIRE_ENCRYPTION,
            # "https_only": self.HTTPS_ONLY
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

        # # Add SMB settings
        # args.update({
        #     "smb_version": self.SMB_VERSION,
        #     "smb_encryption": self.SMB_ENCRYPTION,
        #     "smb_continuous_availability": self.SMB_CONTINUOUS_AVAILABILITY,
        #     "smb_multichannel": self.SMB_MULTICHANNEL
        # })

        # # Add performance settings
        # args.update({
        #     "max_range_size": self.MAX_RANGE_SIZE,
        #     "max_single_get_size": self.MAX_SINGLE_GET_SIZE,
        #     "enable_write_buffering": self.ENABLE_WRITE_BUFFERING,
        #     "write_buffer_size": self.WRITE_BUFFER_SIZE
        # })

        # # Add Kerberos settings if enabled
        # if self.ENABLE_KERBEROS:
        #     args.update({
        #         "enable_kerberos": True,
        #         "kerberos_ticket_path": self.KERBEROS_TICKET_PATH
        #     })

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
    #         required_perms = {"Storage.Files.Read", "Storage.Files.List"}
    #     elif self.ACCESS_TYPE == CONST_STORAGE_ACCESS_TYPE.WRITE_ONLY:
    #         required_perms = {"Storage.Files.Create", "Storage.Files.Delete"}
    #     elif self.ACCESS_TYPE == CONST_STORAGE_ACCESS_TYPE.READ_WRITE:
    #         required_perms = {
    #             "Storage.Files.Read",
    #             "Storage.Files.List",
    #             "Storage.Files.Create",
    #             "Storage.Files.Delete"
    #         }
    #     else:  # ADMIN
    #         required_perms = {"Storage.Files.FullControl"}

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

    #         # Validate SMB settings
    #         if self.SMB_VERSION == "2.1":
    #             if self.SMB_ENCRYPTION or self.SMB_CONTINUOUS_AVAILABILITY:
    #                 return False

    #         # Validate performance settings
    #         if not (0 < self.MAX_RANGE_SIZE <= 4 * 1024 * 1024):  # Max 4MB
    #             return False

    #         if not (0 < self.MAX_SINGLE_GET_SIZE <= 32 * 1024 * 1024):  # Max 32MB
    #             return False

    #         if not (0 < self.WRITE_BUFFER_SIZE <= 4 * 1024 * 1024):  # Max 4MB
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
