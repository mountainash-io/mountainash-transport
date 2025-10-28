from typing import Optional, List, Any, Dict, Tuple
from upath import UPath
from pydantic import Field, SecretStr, field_validator
import re
import ipaddress

from mountainash_settings import SettingsParameters
from ...settings import StorageAuthBase

from ...constants import CONST_STORAGE_PROVIDER_TYPE,CONST_STORAGE_AUTH_METHOD

from ..exceptions import (
    StorageValidationError,
    StorageConfigError
)

# class FTPMode(str, Enum):
#     """FTP transfer modes"""
#     ACTIVE = "active"
#     PASSIVE = "passive"

# class FTPDataType(str, Enum):
#     """FTP data types"""
#     ASCII = "ascii"
#     BINARY = "binary"
#     EBCDIC = "ebcdic"

# class FTPEncoding(str, Enum):
#     """FTP character encodings"""
#     UTF8 = "utf-8"
#     ASCII = "ascii"
#     LATIN1 = "latin1"
#     CP437 = "cp437"  # Original IBM PC encoding
#     CP850 = "cp850"  # Western European DOS

class FTPStorageAuthSettings(StorageAuthBase):
    """
    FTP storage authentication settings.

    Handles authentication configuration for FTP/FTPS connections.
    Does not perform actual authentication or connection.
    """

    PROVIDER_TYPE:  str = Field(default=CONST_STORAGE_PROVIDER_TYPE.FTP)

    # Connection Settings
    HOST:           str =     Field(...)  # Required
    PORT:           int =     Field(default=21)
    USERNAME:       str = Field(default="anonymous")

    # Authentication Settings
    AUTH_METHOD:    str = Field(default=CONST_STORAGE_AUTH_METHOD.PASSWORD)
    PASSWORD:       Optional[SecretStr] = Field(default=None)
    ACCOUNT:        Optional[str] = Field(default=None)  # For systems requiring account info

    # # Security Settings
    # USE_TLS: bool = Field(default=True)
    # TLS_MODE: str = Field(default="explicit")  # explicit or implicit
    # VERIFY_SSL: bool = Field(default=True)
    # CA_CERTS: Optional[str] = Field(default=None)
    # CERT_FILE: Optional[str] = Field(default=None)
    # KEY_FILE: Optional[SecretStr] = Field(default=None)
    # CHECK_HOSTNAME: bool = Field(default=True)

    # # Connection Mode Settings
    # MODE: str = Field(default=FTPMode.PASSIVE)
    # ENABLE_IPV6: bool = Field(default=False)
    # PASSIVE_PORTS: Optional[List[int]] = Field(default=None)
    # ACTIVE_PORTS: Optional[List[int]] = Field(default=None)

    # # Transfer Settings
    # DATA_TYPE: str = Field(default=FTPDataType.BINARY)
    # ENCODING: str = Field(default=FTPEncoding.UTF8)
    # BUFFER_SIZE: int = Field(default=8192)  # 8KB

    # Path Settings
    # ROOT_PATH: Optional[str] = Field(default=None)
    # DEFAULT_PATH: Optional[str] = Field(default=None)

    # # Timeout Settings
    # CONNECT_TIMEOUT: float = Field(default=30.0)
    # DATA_TIMEOUT: float = Field(default=30.0)
    # KEEPALIVE_INTERVAL: Optional[int] = Field(default=None)

    # # Advanced Settings
    # SENDCMD_CONNECT_VERIFY: bool = Field(default=True)
    # USE_MLSD: bool = Field(default=True)  # Use MLSD command if available
    # IGNORE_PASV_HOST: bool = Field(default=False)
    # PRESERVE_PERMISSIONS: bool = Field(default=True)
    # MAX_LINE_LENGTH: int = Field(default=2048)

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
    @field_validator("HOST")
    def validate_host(cls, v: str) -> str:
        """Validate FTP host"""
        if not v:
            raise StorageValidationError(
                "Host is required",
                validation_type="host"
            )

        # Check if it's an IP address
        try:
            ipaddress.ip_address(v)
            return v
        except ValueError:
            # If not IP, validate hostname format
            if not re.match(r'^[a-zA-Z0-9](?:[a-zA-Z0-9\-\.]*[a-zA-Z0-9])?$', v):
                raise StorageValidationError(
                    "Invalid host format. Must be valid IP address or hostname",
                    validation_type="host"
                )

            if len(v) > 255:
                raise StorageValidationError(
                    "Hostname too long",
                    validation_type="host"
                )

        return v

    @field_validator("PORT")
    def validate_port(cls, v: int) -> int:
        """Validate FTP port"""
        if not (1 <= v <= 65535):
            raise StorageValidationError(
                "Port must be between 1 and 65535",
                validation_type="port"
            )
        return v

    # @field_validator("MODE")
    # def validate_mode(cls, v: str) -> str:
    #     """Validate FTP mode"""
    #     try:
    #         return FTPMode(v.lower())
    #     except ValueError:
    #         raise StorageValidationError(
    #             f"Invalid FTP mode. Must be one of: {[m.value for m in FTPMode]}",
    #             validation_type="mode"
    #         )

    # @field_validator("DATA_TYPE")
    # def validate_data_type(cls, v: str) -> str:
    #     """Validate FTP data type"""
    #     try:
    #         return FTPDataType(v.lower())
    #     except ValueError:
    #         raise StorageValidationError(
    #             f"Invalid data type. Must be one of: {[t.value for t in FTPDataType]}",
    #             validation_type="data_type"
    #         )

    # @field_validator("ENCODING")
    # def validate_encoding(cls, v: str) -> str:
    #     """Validate FTP encoding"""
    #     try:
    #         return FTPEncoding(v.lower())
    #     except ValueError:
    #         raise StorageValidationError(
    #             f"Invalid encoding. Must be one of: {[e.value for e in FTPEncoding]}",
    #             validation_type="encoding"
    #         )

    # @field_validator("PASSIVE_PORTS", "ACTIVE_PORTS")
    # def validate_port_range(cls, v: Optional[List[int]]) -> Optional[List[int]]:
    #     """Validate port ranges"""
    #     if v is not None:
    #         if not all(1 <= port <= 65535 for port in v):
    #             raise StorageValidationError(
    #                 "Port numbers must be between 1 and 65535",
    #                 validation_type="port_range"
    #             )

    #         if len(v) > 1000:  # Reasonable limit for port range
    #             raise StorageValidationError(
    #                 "Too many ports specified",
    #                 validation_type="port_range"
    #             )

    #     return v

    # @field_validator("TLS_MODE")
    # def validate_tls_mode(cls, v: str) -> str:
    #     """Validate TLS mode"""
    #     valid_modes = {"explicit", "implicit"}
    #     if v.lower() not in valid_modes:
    #         raise StorageValidationError(
    #             f"Invalid TLS mode. Must be one of: {valid_modes}",
    #             validation_type="tls_mode"
    #         )
    #     return v.lower()

    def _init_provider_specific(self, reinitialise: bool) -> None:
        """Initialize provider-specific settings"""
        # Validate authentication configuration
        if self.AUTH_METHOD == CONST_STORAGE_AUTH_METHOD.PASSWORD:
            if not self.PASSWORD and self.USERNAME != "anonymous":
                raise StorageConfigError(
                    "Password required for non-anonymous login",
                    provider=self.PROVIDER_TYPE
                )

        # # Validate TLS configuration
        # if self.USE_TLS:
        #     if self.VERIFY_SSL and not self.CA_CERTS:
        #         raise StorageSecurityError(
        #             "CA certificates required when SSL verification is enabled",
        #             security_check="tls_config"
        #         )

        #     if self.CERT_FILE and not self.KEY_FILE:
        #         raise StorageSecurityError(
        #             "Key file required when certificate file is provided",
        #             security_check="tls_config"
        #         )

        # # Validate path settings
        # if self.ROOT_PATH and self.DEFAULT_PATH:
        #     if not self.DEFAULT_PATH.startswith(self.ROOT_PATH):
        #         raise StorageConfigError(
        #             "Default path must be within root path",
        #             provider=self.PROVIDER_TYPE
        #         )

        # # Validate port ranges
        # if self.MODE == FTPMode.PASSIVE and self.PASSIVE_PORTS:
        #     if len(self.PASSIVE_PORTS) < 2:
        #         raise StorageConfigError(
        #             "At least two ports required for passive mode range",
        #             provider=self.PROVIDER_TYPE
        #         )

        # if self.MODE == FTPMode.ACTIVE and self.ACTIVE_PORTS:
        #     if len(self.ACTIVE_PORTS) < 2:
        #         raise StorageConfigError(
        #             "At least two ports required for active mode range",
        #             provider=self.PROVIDER_TYPE
        #         )

    def get_connection_url(self) -> str:
        """Generate FTP connection URL"""
        scheme = "ftps" if self.USE_TLS else "ftp"
        url = f"{scheme}://{self.USERNAME}"

        if self.PASSWORD:
            url += f":{self.PASSWORD}"

        url += f"@{self.HOST}:{self.PORT}"

        # if self.ROOT_PATH:
        #     url += self.ROOT_PATH

        return url

    def get_connection_args(self) -> Dict[str, Any]:
        """Get connection arguments as dictionary"""
        args = super().get_connection_args()

        # Add FTP-specific arguments
        args.update({
            "host": self.HOST,
            "port": self.PORT,
            "username": self.USERNAME,
            "password": self.PASSWORD if self.PASSWORD else None,
            "account": self.ACCOUNT,
            # "timeout": self.CONNECT_TIMEOUT,
            # "data_timeout": self.DATA_TIMEOUT,
            # "encoding": self.ENCODING,
            # "buffer_size": self.BUFFER_SIZE,
            # "passive": self.MODE == FTPMode.PASSIVE
        })

        # # Add TLS settings if enabled
        # if self.USE_TLS:
        #     args.update({
        #         "use_tls": True,
        #         "tls_mode": self.TLS_MODE,
        #         "verify_ssl": self.VERIFY_SSL,
        #         "ca_certs": self.CA_CERTS,
        #         "certfile": self.CERT_FILE,
        #         "keyfile": self.KEY_FILE if self.KEY_FILE else None,
        #         "check_hostname": self.CHECK_HOSTNAME
        #     })

        # # Add port range settings
        # if self.MODE == FTPMode.PASSIVE and self.PASSIVE_PORTS:
        #     args["passive_ports"] = self.PASSIVE_PORTS
        # elif self.MODE == FTPMode.ACTIVE and self.ACTIVE_PORTS:
        #     args["active_ports"] = self.ACTIVE_PORTS

        # # Add advanced settings
        # args.update({
        #     "sendcmd_connect_verify": self.SENDCMD_CONNECT_VERIFY,
        #     "use_mlsd": self.USE_MLSD,
        #     "ignore_pasv_host": self.IGNORE_PASV_HOST,
        #     "preserve_permissions": self.PRESERVE_PERMISSIONS,
        #     "max_line_length": self.MAX_LINE_LENGTH
        # })

        return {k: v for k, v in args.items() if v is not None}

    # def _validate_permissions(self) -> None:
    #     """Validate storage permissions configuration"""
    #     # Define required permissions based on access type
    #     if self.ACCESS_TYPE == CONST_STORAGE_ACCESS_TYPE.READ_ONLY:
    #         required_perms = {"read", "list"}
    #     elif self.ACCESS_TYPE == CONST_STORAGE_ACCESS_TYPE.WRITE_ONLY:
    #         required_perms = {"write", "mkdir"}
    #     elif self.ACCESS_TYPE == CONST_STORAGE_ACCESS_TYPE.READ_WRITE:
    #         required_perms = {"read", "write", "list", "mkdir"}
    #     else:  # ADMIN
    #         required_perms = {"read", "write", "list", "mkdir", "delete", "chmod"}

    #     # Validate against required permissions
    #     if not required_perms.issubset(self.REQUIRED_PERMISSIONS):
    #         raise StorageValidationError(
    #             f"Missing required permissions for access type {self.ACCESS_TYPE}",
    #             validation_type="permissions"
    #         )
