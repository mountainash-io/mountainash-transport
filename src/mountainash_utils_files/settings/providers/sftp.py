from typing import Optional, List, Any, Dict, Tuple
from upath import UPath
from pydantic import Field, SecretStr, field_validator
import re
import os
import ipaddress

from mountainash_settings import SettingsParameters
from ...settings import StorageAuthBase

from ...constants import CONST_STORAGE_PROVIDER_TYPE,CONST_STORAGE_AUTH_METHOD

from ..exceptions import (
    StorageValidationError,
    StorageConfigError,
    StorageSecurityError
)

class SFTPStorageAuthSettings(StorageAuthBase):
    """
    SFTP storage authentication settings.

    Handles authentication configuration for SFTP connections.
    Does not perform actual authentication or connection.
    """

    PROVIDER_TYPE: str = Field(default=CONST_STORAGE_PROVIDER_TYPE.SFTP)

    # Connection Settings
    HOST: str = Field(...)  # Required
    PORT: int = Field(default=22)
    USERNAME: str = Field(...)  # Required

    # Authentication Settings
    AUTH_METHOD: str = Field(default=CONST_STORAGE_AUTH_METHOD.KEY)  # password, key, agent
    PASSWORD: Optional[SecretStr] = Field(default=None)
    PRIVATE_KEY_PATH: Optional[str] = Field(default=None)
    PRIVATE_KEY_STRING: Optional[SecretStr] = Field(default=None)
    PRIVATE_KEY_PASSPHRASE: Optional[SecretStr] = Field(default=None)

    # SSH Settings
    KNOWN_HOSTS_FILE: Optional[str] = Field(default=None)
    HOST_KEY_POLICY: str = Field(default="reject")  # reject, warn, auto_add, ignore
    PREFERRED_AUTH_METHODS: List[str] = Field(default=["publickey", "password"])
    COMPRESSION: bool = Field(default=True)
    COMPRESSION_LEVEL: int = Field(default=6)  # 0-9

    # # Path Settings
    # ROOT_PATH: Optional[str] = Field(default=None)
    # DEFAULT_PATH: Optional[str] = Field(default=None)

    # # Security Settings
    # CIPHERS: Optional[List[str]] = Field(default=None)
    # KEX_ALGORITHMS: Optional[List[str]] = Field(default=None)
    # HOSTKEY_ALGORITHMS: Optional[List[str]] = Field(default=None)
    # ALLOW_AGENT: bool = Field(default=True)
    # LOOK_FOR_KEYS: bool = Field(default=True)

    # # Transfer Settings
    # BUFFER_SIZE: int = Field(default=32768)  # 32KB
    # MAX_PACKET_SIZE: int = Field(default=32768)
    # WINDOW_SIZE: int = Field(default=2097152)  # 2MB

    # # Timeout Settings
    # TIMEOUT: float = Field(default=30.0)
    # BANNER_TIMEOUT: float = Field(default=60.0)
    # AUTH_TIMEOUT: float = Field(default=30.0)
    # KEEPALIVE_INTERVAL: int = Field(default=30)

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
        """Validate SFTP host"""
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
        """Validate SFTP port"""
        if not (1 <= v <= 65535):
            raise StorageValidationError(
                "Port must be between 1 and 65535",
                validation_type="port"
            )
        return v

    @field_validator("USERNAME")
    def validate_username(cls, v: str) -> str:
        """Validate SFTP username"""
        if not v:
            raise StorageValidationError(
                "Username is required",
                validation_type="username"
            )

        # Unix username validation rules
        if not re.match(r'^[a-z_][a-z0-9_-]*[$]?$', v):
            raise StorageValidationError(
                "Invalid username format",
                validation_type="username"
            )

        if len(v) > 32:
            raise StorageValidationError(
                "Username too long",
                validation_type="username"
            )

        return v

    @field_validator("PRIVATE_KEY_PATH")
    def validate_private_key_path(cls, v: Optional[str]) -> Optional[str]:
        """Validate private key path"""
        if v is not None:
            try:
                path = UPath(v).resolve()
                if not path.exists():
                    raise StorageValidationError(
                        f"Private key file not found: {v}",
                        validation_type="private_key_path"
                    )

                # Check file permissions
                mode = os.stat(path).st_mode
                if mode & 0o077:  # Check if group or others have any access
                    raise StorageSecurityError(
                        "Private key file has unsafe permissions",
                        security_check="key_permissions"
                    )

            except Exception as e:
                if isinstance(e, (StorageValidationError, StorageSecurityError)):
                    raise
                raise StorageValidationError(
                    f"Invalid private key path: {str(e)}",
                    validation_type="private_key_path"
                )

        return v

    @field_validator("KNOWN_HOSTS_FILE")
    def validate_known_hosts_file(cls, v: Optional[str]) -> Optional[str]:
        """Validate known hosts file path"""
        if v is not None:
            try:
                path = UPath(v).resolve()
                if not path.exists():
                    # Create empty file if it doesn't exist
                    path.touch(mode=0o600)

                # Check file permissions
                mode = os.stat(path).st_mode
                if mode & 0o077:  # Check if group or others have any access
                    raise StorageSecurityError(
                        "Known hosts file has unsafe permissions",
                        security_check="known_hosts_permissions"
                    )

            except Exception as e:
                if isinstance(e, StorageSecurityError):
                    raise
                raise StorageValidationError(
                    f"Invalid known hosts file: {str(e)}",
                    validation_type="known_hosts_file"
                )

        return v

    @field_validator("HOST_KEY_POLICY")
    def validate_host_key_policy(cls, v: str) -> str:
        """Validate host key policy"""
        valid_policies = {"reject", "warn", "auto_add", "ignore"}
        if v not in valid_policies:
            raise StorageValidationError(
                f"Invalid host key policy. Must be one of: {valid_policies}",
                validation_type="host_key_policy"
            )
        return v

    @field_validator("COMPRESSION_LEVEL")
    def validate_compression_level(cls, v: int) -> int:
        """Validate compression level"""
        if not (0 <= v <= 9):
            raise StorageValidationError(
                "Compression level must be between 0 and 9",
                validation_type="compression_level"
            )
        return v

    def _init_provider_specific(self, reinitialise: bool) -> None:
        """Initialize provider-specific settings"""
        # Validate authentication method configuration
        if self.AUTH_METHOD == CONST_STORAGE_AUTH_METHOD.PASSWORD:
            if not self.PASSWORD:
                raise StorageConfigError(
                    "Password required for password authentication",
                    provider=self.PROVIDER_TYPE
                )
        elif self.AUTH_METHOD == CONST_STORAGE_AUTH_METHOD.KEY:
            if not (self.PRIVATE_KEY_PATH or self.PRIVATE_KEY_STRING):
                raise StorageConfigError(
                    "Either private key path or string required for key authentication",
                    provider=self.PROVIDER_TYPE
                )

        # # Validate path settings
        # if self.ROOT_PATH and self.DEFAULT_PATH:
        #     if not self.DEFAULT_PATH.startswith(self.ROOT_PATH):
        #         raise StorageConfigError(
        #             "Default path must be within root path",
        #             provider=self.PROVIDER_TYPE
        #         )

        # Validate security settings
        if self.HOST_KEY_POLICY == "reject" and not self.KNOWN_HOSTS_FILE:
            raise StorageSecurityError(
                "Known hosts file required when host key policy is 'reject'",
                security_check="host_key_policy"
            )

    def get_connection_url(self) -> str:
        """Generate SFTP connection URL"""
        url = f"sftp://{self.USERNAME}@{self.HOST}:{self.PORT}"

        if self.ROOT_PATH:
            url = f"{url}{self.ROOT_PATH}"

        return url

    def get_connection_args(self) -> Dict[str, Any]:
        """Get connection arguments as dictionary"""
        args = super().get_connection_args()

        # Add SFTP-specific arguments
        args.update({
            "hostname": self.HOST,
            "port": self.PORT,
            "username": self.USERNAME,
            "compress": self.COMPRESSION,
            "compression_level": self.COMPRESSION_LEVEL if self.COMPRESSION else None,
            "timeout": self.TIMEOUT,
            # "banner_timeout": self.BANNER_TIMEOUT,
            # "auth_timeout": self.AUTH_TIMEOUT,
            # "allow_agent": self.ALLOW_AGENT,
            # "look_for_keys": self.LOOK_FOR_KEYS
        })

        # Add authentication credentials based on method
        if self.AUTH_METHOD == CONST_STORAGE_AUTH_METHOD.PASSWORD:
            args["password"] = self.PASSWORD
        elif self.AUTH_METHOD == CONST_STORAGE_AUTH_METHOD.KEY:
            if self.PRIVATE_KEY_STRING:
                args["pkey"] = self.PRIVATE_KEY_STRING
            else:
                args["key_filename"] = self.PRIVATE_KEY_PATH

            if self.PRIVATE_KEY_PASSPHRASE:
                args["passphrase"] = self.PRIVATE_KEY_PASSPHRASE

        # Add security settings
        if self.KNOWN_HOSTS_FILE:
            args["host_keys_filename"] = self.KNOWN_HOSTS_FILE

        # if self.CIPHERS:
        #     args["ciphers"] = self.CIPHERS

        # if self.KEX_ALGORITHMS:
        #     args["kex_algorithms"] = self.KEX_ALGORITHMS

        # if self.HOSTKEY_ALGORITHMS:
        #     args["hostkey_algorithms"] = self.HOSTKEY_ALGORITHMS

        # # Add transfer settings
        # args.update({
        #     "buffer_size": self.BUFFER_SIZE,
        #     "max_packet_size": self.MAX_PACKET_SIZE,
        #     "window_size": self.WINDOW_SIZE,
        #     "keepalive_interval": self.KEEPALIVE_INTERVAL
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
