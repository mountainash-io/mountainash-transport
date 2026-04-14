from typing import Optional, List, Any, Dict, Tuple
from upath import UPath
from pydantic import Field, SecretStr, field_validator
import re
from enum import Enum
import ipaddress

from mountainash_settings import SettingsParameters
from ...settings import StorageAuthBase

from ...constants import CONST_STORAGE_PROVIDER_TYPE,CONST_STORAGE_AUTH_METHOD

from ..exceptions import (
    StorageValidationError,
    StorageConfigError
)

class SMBVersion(str, Enum):
    """SMB protocol versions"""
    SMB1 = "1.0"
    SMB2_0 = "2.0"
    SMB2_1 = "2.1"
    SMB3_0 = "3.0"
    SMB3_1_1 = "3.1.1"

class SMBSignOptions(str, Enum):
    """SMB signing options"""
    WHEN_REQUIRED = "when_required"
    WHEN_SUPPORTED = "when_supported"
    REQUIRED = "required"
    OFF = "off"

class SMBDialects(str, Enum):
    """SMB dialect options"""
    NT_LM_0_12 = "NT-LM-0.12"  # SMB 1
    SMB_2_0_2 = "2.002"        # SMB 2.0
    SMB_2_1_0 = "2.100"        # SMB 2.1
    SMB_3_0_0 = "3.000"        # SMB 3.0
    SMB_3_0_2 = "3.002"        # SMB 3.0.2
    SMB_3_1_1 = "3.1.1"        # SMB 3.1.1

class SMBStorageAuthSettings(StorageAuthBase):
    """
    SMB storage authentication settings.

    Handles authentication configuration for SMB/CIFS connections.
    Does not perform actual authentication or connection.
    """

    PROVIDER_TYPE: str = Field(default=CONST_STORAGE_PROVIDER_TYPE.SMB)

    # Connection Settings
    SERVER: str = Field(...)  # Required
    SHARE: str = Field(...)   # Required
    PORT: int = Field(default=445)  # SMB direct port

    # Authentication Settings
    AUTH_METHOD: str = Field(default=CONST_STORAGE_AUTH_METHOD.PASSWORD)
    USERNAME: Optional[str] = Field(default=None)
    PASSWORD: Optional[SecretStr] = Field(default=None)
    DOMAIN: Optional[str] = Field(default=None)
    USE_KERBEROS: bool = Field(default=False)
    KERBEROS_KDC: Optional[str] = Field(default=None)

    # Protocol Settings
    VERSION: str = Field(default=SMBVersion.SMB3_0)
    MIN_VERSION: Optional[str] = Field(default=None)
    MAX_VERSION: Optional[str] = Field(default=None)
    PREFERRED_DIALECT: Optional[str] = Field(default=None)
    FALLBACK_VERSIONS: List[str] = Field(default_factory=list)

    # # Security Settings
    # ENCRYPTION: bool = Field(default=True)
    # SIGN_OPTIONS: str = Field(default=SMBSignOptions.WHEN_REQUIRED)
    # REQUIRE_SECURE_NEGOTIATE: bool = Field(default=True)
    # USE_NTLM: bool = Field(default=True)
    # USE_NTLMv2: bool = Field(default=True)

    # # Connection Settings
    # TIMEOUT: float = Field(default=60.0)
    # KEEPALIVE: bool = Field(default=True)
    # KEEPALIVE_INTERVAL: int = Field(default=30)
    # MAX_CHANNELS: int = Field(default=4)

    # # Performance Settings
    # BUFFER_SIZE: int = Field(default=16384)  # 16KB
    # MAX_WRITE_SIZE: int = Field(default=1048576)  # 1MB
    # MAX_READ_SIZE: int = Field(default=1048576)  # 1MB
    # USE_OPLOCKS: bool = Field(default=True)
    # USE_LEASES: bool = Field(default=True)

    # # Caching Settings
    # CACHE_ENABLED: bool = Field(default=True)
    # CACHE_TTL: int = Field(default=60)  # seconds
    # DIR_CACHE_TTL: int = Field(default=300)  # seconds

    # # DFS Settings
    # USE_DFS: bool = Field(default=True)
    # DFS_DOMAIN_CONTROLLER: Optional[str] = Field(default=None)
    # DFS_ROOT: Optional[str] = Field(default=None)

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
    @field_validator("SERVER")
    def validate_server(cls, v: str) -> str:
        """Validate SMB server"""
        if not v:
            raise StorageValidationError(
                "Server is required",
                validation_type="server"
            )

        # Check if it's an IP address
        try:
            ipaddress.ip_address(v)
            return v
        except ValueError:
            # If not IP, validate hostname or NetBIOS name
            if not re.match(r'^[a-zA-Z0-9](?:[a-zA-Z0-9\-\.]*[a-zA-Z0-9])?$', v):
                raise StorageValidationError(
                    "Invalid server format. Must be valid IP address, hostname, or NetBIOS name",
                    validation_type="server"
                )

            if len(v) > 255:  # DNS limit
                raise StorageValidationError(
                    "Server name too long",
                    validation_type="server"
                )

        return v

    @field_validator("SHARE")
    def validate_share(cls, v: str) -> str:
        """Validate SMB share name"""
        if not v:
            raise StorageValidationError(
                "Share name is required",
                validation_type="share"
            )

        # Basic share name validation
        if not re.match(r'^[a-zA-Z0-9\$](?:[a-zA-Z0-9\s\-_\$]*[a-zA-Z0-9\$])?$', v):
            raise StorageValidationError(
                "Invalid share name format",
                validation_type="share"
            )

        if len(v) > 80:  # Common share name limit
            raise StorageValidationError(
                "Share name too long",
                validation_type="share"
            )

        return v

    @field_validator("VERSION", "MIN_VERSION", "MAX_VERSION")
    def validate_version(cls, v: Optional[str]) -> Optional[str]:
        """Validate SMB version"""
        if v is not None:
            try:
                return SMBVersion(v)
            except ValueError:
                raise StorageValidationError(
                    f"Invalid SMB version. Must be one of: {[ver.value for ver in SMBVersion]}",
                    validation_type="version"
                )
        return v

    @field_validator("PREFERRED_DIALECT")
    def validate_dialect(cls, v: Optional[str]) -> Optional[str]:
        """Validate SMB dialect"""
        if v is not None:
            try:
                return SMBDialects(v)
            except ValueError:
                raise StorageValidationError(
                    f"Invalid SMB dialect. Must be one of: {[d.value for d in SMBDialects]}",
                    validation_type="dialect"
                )
        return v

    # @field_validator("SIGN_OPTIONS")
    # def validate_sign_options(cls, v: str) -> str:
    #     """Validate signing options"""
    #     try:
    #         return SMBSignOptions(v.lower())
    #     except ValueError:
    #         raise StorageValidationError(
    #             f"Invalid signing options. Must be one of: {[opt.value for opt in SMBSignOptions]}",
    #             validation_type="sign_options"
    #         )

    @field_validator("DOMAIN")
    def validate_domain(cls, v: Optional[str]) -> Optional[str]:
        """Validate domain name"""
        if v is not None:
            if not re.match(r'^[a-zA-Z0-9](?:[a-zA-Z0-9\-\.]*[a-zA-Z0-9])?$', v):
                raise StorageValidationError(
                    "Invalid domain format",
                    validation_type="domain"
                )

            if len(v) > 255:
                raise StorageValidationError(
                    "Domain name too long",
                    validation_type="domain"
                )

        return v

    def _init_provider_specific(self, reinitialise: bool) -> None:
        """Initialize provider-specific settings"""
        # Validate authentication configuration
        if self.AUTH_METHOD == CONST_STORAGE_AUTH_METHOD.PASSWORD:
            if not (self.USERNAME and self.PASSWORD):
                raise StorageConfigError(
                    "Username and password required for password authentication",
                    provider=self.PROVIDER_TYPE
                )

        # Validate Kerberos configuration
        if self.USE_KERBEROS:
            if not self.KERBEROS_KDC and not self.DOMAIN:
                raise StorageConfigError(
                    "Either Kerberos KDC or domain required for Kerberos authentication",
                    provider=self.PROVIDER_TYPE
                )

        # Validate version settings
        if self.MIN_VERSION and self.MAX_VERSION:
            if SMBVersion(self.MIN_VERSION).value > SMBVersion(self.MAX_VERSION).value:
                raise StorageConfigError(
                    "Minimum version cannot be higher than maximum version",
                    provider=self.PROVIDER_TYPE
                )

        # # Validate DFS settings
        # if self.USE_DFS and not (self.DFS_DOMAIN_CONTROLLER or self.DOMAIN):
        #     raise StorageConfigError(
        #         "Either DFS domain controller or domain required when DFS is enabled",
        #         provider=self.PROVIDER_TYPE
        #     )

    def get_connection_url(self) -> str:
        """Generate SMB connection URL"""
        url = "smb://"

        # Add domain if specified
        if self.DOMAIN:
            url += f"{self.DOMAIN}/"

        # Add server and share
        url += f"{self.SERVER}/{self.SHARE}"

        return url

    def get_connection_args(self) -> Dict[str, Any]:
        """Get connection arguments as dictionary"""
        args = super().get_connection_args()

        # Add SMB-specific arguments
        args.update({
            "server": self.SERVER,
            "share": self.SHARE,
            "port": self.PORT,
            "timeout": self.TIMEOUT,
            "username": self.USERNAME,
            "password": self.PASSWORD.get_secret_value() if self.PASSWORD else None,
            "domain": self.DOMAIN
        })

        # Add version settings
        args.update({
            "version": self.VERSION,
            "min_version": self.MIN_VERSION,
            "max_version": self.MAX_VERSION,
            "preferred_dialect": self.PREFERRED_DIALECT,
            "fallback_versions": self.FALLBACK_VERSIONS
        })

        # # Add security settings
        # args.update({
        #     "encrypt": self.ENCRYPTION,
        #     "sign_options": self.SIGN_OPTIONS,
        #     "require_secure_negotiate": self.REQUIRE_SECURE_NEGOTIATE,
        #     "use_ntlm": self.USE_NTLM,
        #     "use_ntlmv2": self.USE_NTLMv2
        # })

        # Add Kerberos settings if enabled
        if self.USE_KERBEROS:
            args.update({
                "use_kerberos": True,
                "kerberos_kdc": self.KERBEROS_KDC
            })

        # Add performance settings
        # args.update({
        #     "buffer_size": self.BUFFER_SIZE,
        #     "max_write_size": self.MAX_WRITE_SIZE,
        #     "max_read_size": self.MAX_READ_SIZE,
        #     "use_oplocks": self.USE_OPLOCKS,
        #     "use_leases": self.USE_LEASES,
        #     "max_channels": self.MAX_CHANNELS
        # })

        # # Add caching settings
        # if self.CACHE_ENABLED:
        #     args.update({
        #         "cache_enabled": True,
        #         "cache_ttl": self.CACHE_TTL,
        #         "dir_cache_ttl": self.DIR_CACHE_TTL
        #     })

        # # Add DFS settings if enabled
        # if self.USE_DFS:
        #     args.update({
        #         "use_dfs": True,
        #         "dfs_domain_controller": self.DFS_DOMAIN_CONTROLLER,
        #         "dfs_root": self.DFS_ROOT
        #     })

        return {k: v for k, v in args.items() if v is not None}

    # def _validate_permissions(self) -> None:
    #     """Validate storage permissions configuration"""
    #     # Define required permissions based on access type
    #     if self.ACCESS_TYPE == CONST_STORAGE_ACCESS_TYPE.READ_ONLY:
    #         required_perms = {"FILE_READ_DATA", "FILE_READ_EA", "FILE_READ_ATTRIBUTES"}
    #     elif self.ACCESS_TYPE == CONST_STORAGE_ACCESS_TYPE.WRITE_ONLY:
    #         required_perms = {"FILE_WRITE_DATA", "FILE_WRITE_EA", "FILE_WRITE_ATTRIBUTES"}
    #     elif self.ACCESS_TYPE == CONST_STORAGE_ACCESS_TYPE.READ_WRITE:
    #         required_perms = {
    #             "FILE_READ_DATA", "FILE_WRITE_DATA",
    #             "FILE_READ_EA", "FILE_WRITE_EA",
    #             "FILE_READ_ATTRIBUTES", "FILE_WRITE_ATTRIBUTES"
    #         }
    #     else:  # ADMIN
    #         required_perms = {
    #             "FILE_ALL_ACCESS",
    #             "FILE_DELETE",
    #             "FILE_WRITE_ATTRIBUTES",
    #             "FILE_WRITE_EA",
    #             "FILE_WRITE_DATA",
    #             "FILE_READ_ATTRIBUTES",
    #             "FILE_READ_EA",
    #             "FILE_READ_DATA"
    #         }

    #     # Validate against required permissions
    #     if not required_perms.issubset(self.REQUIRED_PERMISSIONS):
    #         raise StorageValidationError(
    #             f"Missing required permissions for access type {self.ACCESS_TYPE}",
    #             validation_type="permissions"
    #         )
