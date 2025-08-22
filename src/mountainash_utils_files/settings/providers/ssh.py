from typing import Optional, List, Any, Dict, Tuple
from upath import UPath
from pydantic import Field, SecretStr, field_validator
import re
from enum import Enum
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

from mountainash_utils_ssh import SSHKeyType, SSHHostKeyPolicy

class SSHStorageAuthSettings(StorageAuthBase):
    """
    SSH storage authentication settings.

    Handles authentication configuration for SSH connections.
    Does not perform actual authentication or connection.
    """

    PROVIDER_TYPE: str = Field(default=CONST_STORAGE_PROVIDER_TYPE.SSH)

    # Connection Settings
    HOST: str = Field(...)  # Required
    PORT: int = Field(default=22)
    USERNAME: str = Field(...)  # Required

    # Authentication Settings
    AUTH_METHOD: str = Field(default=CONST_STORAGE_AUTH_METHOD.KEY)
    PASSWORD: Optional[SecretStr] = Field(default=None)
    PRIVATE_KEY_PATH: Optional[str] = Field(default=None)
    PRIVATE_KEY_STRING: Optional[SecretStr] = Field(default=None)
    PRIVATE_KEY_TYPE: Optional[str] = Field(default=SSHKeyType.ED25519)
    PRIVATE_KEY_PASSPHRASE: Optional[SecretStr] = Field(default=None)

    # SSH Security Settings
    KNOWN_HOSTS_FILE: Optional[str] = Field(default=None)
    HOST_KEY_POLICY: str = Field(default=SSHHostKeyPolicy.REJECT)
    HOST_KEY_ALGORITHMS: Optional[List[str]] = Field(default=None)
    CIPHERS: Optional[List[str]] = Field(default=None)
    KEX_ALGORITHMS: Optional[List[str]] = Field(default=None)
    MAC_ALGORITHMS: Optional[List[str]] = Field(default=None)
    STRICT_HOST_KEY_CHECKING: bool = Field(default=True)

    # # Authentication Options
    # ALLOW_AGENT: bool = Field(default=True)
    # LOOK_FOR_KEYS: bool = Field(default=True)
    # PREFERRED_AUTH_METHODS: List[str] = Field(
    #     default=["publickey", "keyboard-interactive", "password"]
    # )

    # # Connection Settings
    # TIMEOUT: float = Field(default=30.0)
    # TCP_KEEPALIVE: bool = Field(default=True)
    # KEEPALIVE_INTERVAL: int = Field(default=30)
    # COMPRESSION: bool = Field(default=True)
    # COMPRESSION_LEVEL: int = Field(default=6)  # 0-9

    # # Channel Settings
    # CHANNEL_TIMEOUT: float = Field(default=30.0)
    # WINDOW_SIZE: int = Field(default=2097152)  # 2MB
    # MAX_PACKET_SIZE: int = Field(default=32768)  # 32KB

    # # Advanced Settings
    # BANNER_TIMEOUT: float = Field(default=60.0)
    # AUTH_TIMEOUT: float = Field(default=30.0)
    # SOCK_CONNECT_TIMEOUT: Optional[float] = Field(default=None)
    # DISABLED_ALGORITHMS: Optional[Dict[str, List[str]]] = Field(default=None)

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
        """Validate SSH host"""
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
        """Validate SSH port"""
        if not (1 <= v <= 65535):
            raise StorageValidationError(
                "Port must be between 1 and 65535",
                validation_type="port"
            )
        return v

    @field_validator("USERNAME")
    def validate_username(cls, v: str) -> str:
        """Validate SSH username"""
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

    @field_validator("PRIVATE_KEY_TYPE")
    def validate_key_type(cls, v: Optional[str]) -> Optional[str]:
        """Validate private key type"""
        if v is not None:
            try:
                return SSHKeyType(v.lower())
            except ValueError:
                raise StorageValidationError(
                    f"Invalid key type. Must be one of: {[kt.value for kt in SSHKeyType]}",
                    validation_type="key_type"
                )
        return v

    @field_validator("HOST_KEY_POLICY")
    def validate_host_key_policy(cls, v: str) -> str:
        """Validate host key policy"""
        try:
            return SSHHostKeyPolicy(v.lower())
        except ValueError:
            raise StorageValidationError(
                f"Invalid host key policy. Must be one of: {[p.value for p in SSHHostKeyPolicy]}",
                validation_type="host_key_policy"
            )

    @field_validator("PRIVATE_KEY_PATH")
    def validate_private_key_path(cls, v: Optional[str]) -> Optional[str]:
        """Validate private key file path"""
        if v is not None:
            try:
                path = UPath(v).resolve()
                if not path.exists():
                    raise StorageValidationError(
                        f"Private key file not found: {v}",
                        validation_type="private_key_path"
                    )

                # Check file permissions (Unix-like systems)
                if os.name == 'posix':
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
                    path.touch(mode=0o600)  # Create with secure permissions

                # Check file permissions (Unix-like systems)
                if os.name == 'posix':
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

    # @field_validator("COMPRESSION_LEVEL")
    # def validate_compression_level(cls, v: int) -> int:
    #     """Validate compression level"""
    #     if not (0 <= v <= 9):
    #         raise StorageValidationError(
    #             "Compression level must be between 0 and 9",
    #             validation_type="compression_level"
    #         )
    #     return v

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

        # Validate host key verification
        if self.STRICT_HOST_KEY_CHECKING and not self.KNOWN_HOSTS_FILE:
            if self.HOST_KEY_POLICY == SSHHostKeyPolicy.REJECT:
                raise StorageSecurityError(
                    "Known hosts file required when strict host key checking is enabled",
                    security_check="host_key_verification"
                )

        # # Validate disabled algorithms
        # if self.DISABLED_ALGORITHMS:
        #     valid_categories = {"kex", "cipher", "mac", "key", "hostkey"}
        #     invalid_categories = set(self.DISABLED_ALGORITHMS.keys()) - valid_categories
        #     if invalid_categories:
        #         raise StorageConfigError(
        #             f"Invalid algorithm categories: {invalid_categories}",
        #             provider=self.PROVIDER_TYPE
        #         )

    def get_connection_url(self) -> str:
        """Generate SSH connection URL"""
        return f"ssh://{self.USERNAME}@{self.HOST}:{self.PORT}"

    def get_connection_args(self) -> Dict[str, Any]:
        """Get connection arguments as dictionary"""
        args = super().get_connection_args()

        # Add SSH-specific arguments
        args.update({
            "hostname": self.HOST,
            "port": self.PORT,
            "username": self.USERNAME,
            "timeout": self.TIMEOUT,
            # "banner_timeout": self.BANNER_TIMEOUT,
            # "auth_timeout": self.AUTH_TIMEOUT,
            # "sock_connect_timeout": self.SOCK_CONNECT_TIMEOUT,
            # "allow_agent": self.ALLOW_AGENT,
            # "look_for_keys": self.LOOK_FOR_KEYS,
            # "compress": self.COMPRESSION,
            # "compression_level": self.COMPRESSION_LEVEL if self.COMPRESSION else None,
            # "keepalive_interval": self.KEEPALIVE_INTERVAL if self.TCP_KEEPALIVE else None
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
        if self.HOST_KEY_ALGORITHMS:
            args["hostkey_algorithms"] = self.HOST_KEY_ALGORITHMS

        if self.CIPHERS:
            args["ciphers"] = self.CIPHERS

        if self.KEX_ALGORITHMS:
            args["kex_algorithms"] = self.KEX_ALGORITHMS

        if self.MAC_ALGORITHMS:
            args["mac_algorithms"] = self.MAC_ALGORITHMS

        # if self.DISABLED_ALGORITHMS:
        #     args["disabled_algorithms"] = self.DISABLED_ALGORITHMS

        # # Add channel settings
        # args.update({
        #     "channel_timeout": self.CHANNEL_TIMEOUT,
        #     "window_size": self.WINDOW_SIZE,
        #     "max_packet_size": self.MAX_PACKET_SIZE
        # })

        return {k: v for k, v in args.items() if v is not None}

    # def _validate_permissions(self) -> None:
    #     """Validate storage permissions configuration"""
    #     # Define required permissions based on access type
    #     if self.ACCESS_TYPE == CONST_STORAGE_ACCESS_TYPE.READ_ONLY:
    #         required_perms = {"read", "execute"}
    #     elif self.ACCESS_TYPE == CONST_STORAGE_ACCESS_TYPE.WRITE_ONLY:
    #         required_perms = {"write", "execute"}
    #     elif self.ACCESS_TYPE == CONST_STORAGE_ACCESS_TYPE.READ_WRITE:
    #         required_perms = {"read", "write", "execute"}
    #     else:  # ADMIN
    #         required_perms = {"read", "write", "execute", "delete", "sudo"}

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
    #             allowed_schemes={'ssh'},
    #             required_parts={'netloc'}
    #         ):
    #             return False

    #         # Validate packet and window sizes
    #         if not (1024 <= self.MAX_PACKET_SIZE <= 32768):  # 1KB to 32KB
    #             return False

    #         if not (131072 <= self.WINDOW_SIZE <= 2097152):  # 128KB to 2MB
    #             return False

    #         # Validate timeout settings
    #         if not StorageValidator.validate_timeout_settings(
    #             connect_timeout=self.TIMEOUT,
    #             read_timeout=self.CHANNEL_TIMEOUT
    #         ):
    #             return False

    #         return True

    #     except Exception as e:
