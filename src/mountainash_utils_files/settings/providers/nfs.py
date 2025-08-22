from typing import Optional, List, Any, Dict, Tuple
from upath import UPath
from pydantic import Field, field_validator
import re
from enum import Enum
import ipaddress
import os

from mountainash_settings import SettingsParameters
from ...settings import StorageAuthBase

from ...constants import CONST_STORAGE_PROVIDER_TYPE

from ..exceptions import (
    StorageValidationError,
    StorageConfigError,
    StorageSecurityError
)

class NFSVersion(str, Enum):
    """NFS protocol versions"""
    NFSv3 = "3"
    NFSv4 = "4"
    NFSv4_1 = "4.1"
    NFSv4_2 = "4.2"

class NFSSecurityType(str, Enum):
    """NFS security types"""
    SYS = "sys"      # Traditional Unix-style (uid/gid)
    KRB5 = "krb5"    # Kerberos v5 authentication
    KRB5I = "krb5i"  # Kerberos v5 with integrity
    KRB5P = "krb5p"  # Kerberos v5 with privacy

class NFSMountProtocol(str, Enum):
    """NFS mount protocols"""
    UDP = "udp"
    TCP = "tcp"
    RDMA = "rdma"

class NFSStorageAuthSettings(StorageAuthBase):
    """
    NFS storage authentication settings.

    Handles authentication configuration for NFS mounts.
    Does not perform actual authentication or mounting.
    """

    PROVIDER_TYPE: str = Field(default=CONST_STORAGE_PROVIDER_TYPE.NFS)

    # Server Settings
    SERVER: str = Field(...)  # Required
    EXPORT_PATH: str = Field(...)  # Required

    # Protocol Settings
    VERSION: str = Field(default=NFSVersion.NFSv4)
    MOUNT_PROTOCOL: str = Field(default=NFSMountProtocol.TCP)

    # Security Settings
    SECURITY_TYPE: str = Field(default=NFSSecurityType.SYS)
    USE_KERBEROS: bool = Field(default=False)
    KERBEROS_KDC: Optional[str] = Field(default=None)
    KERBEROS_REALM: Optional[str] = Field(default=None)
    KERBEROS_PRINCIPAL: Optional[str] = Field(default=None)
    KERBEROS_KEYTAB: Optional[str] = Field(default=None)

    # ID Mapping Settings
    LOCAL_UID: Optional[int] = Field(default=None)
    LOCAL_GID: Optional[int] = Field(default=None)
    UID_MAPPING: Optional[Dict[int, int]] = Field(default=None)  # remote_uid: local_uid
    GID_MAPPING: Optional[Dict[int, int]] = Field(default=None)  # remote_gid: local_gid

    # Mount Options
    READ_ONLY: bool = Field(default=False)
    NO_LOCK: bool = Field(default=False)
    HARD_MOUNT: bool = Field(default=True)
    RETRY_COUNT: int = Field(default=3)
    TIMEOUT: int = Field(default=600)  # 10 minutes
    RETRANS: int = Field(default=3)
    ACREGMIN: int = Field(default=3)
    ACREGMAX: int = Field(default=60)
    ACDIRMIN: int = Field(default=30)
    ACDIRMAX: int = Field(default=60)

    # # Performance Settings
    # RW_SIZE: int = Field(default=1048576)  # 1MB
    # READ_AHEAD: int = Field(default=1)  # In blocks
    # WRITE_BACK_CACHE: bool = Field(default=False)
    # ASYNC: bool = Field(default=False)

    # # Advanced Settings
    MOUNT_POINT: Optional[str] = Field(default=None)
    # NO_DEV: bool = Field(default=True)
    # NO_SUID: bool = Field(default=True)
    # NO_EXEC: bool = Field(default=False)

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
        """Validate NFS server"""
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
            # If not IP, validate hostname format
            if not re.match(r'^[a-zA-Z0-9](?:[a-zA-Z0-9\-\.]*[a-zA-Z0-9])?$', v):
                raise StorageValidationError(
                    "Invalid server format. Must be valid IP address or hostname",
                    validation_type="server"
                )

            if len(v) > 255:
                raise StorageValidationError(
                    "Server name too long",
                    validation_type="server"
                )

        return v

    @field_validator("EXPORT_PATH")
    def validate_export_path(cls, v: str) -> str:
        """Validate NFS export path"""
        if not v:
            raise StorageValidationError(
                "Export path is required",
                validation_type="export_path"
            )

        # Basic path validation
        if not v.startswith('/'):
            raise StorageValidationError(
                "Export path must be absolute",
                validation_type="export_path"
            )

        # Check for invalid characters
        if re.search(r'[^a-zA-Z0-9/._-]', v):
            raise StorageValidationError(
                "Export path contains invalid characters",
                validation_type="export_path"
            )

        return v

    @field_validator("VERSION")
    def validate_version(cls, v: str) -> str:
        """Validate NFS version"""
        try:
            return NFSVersion(v)
        except ValueError:
            raise StorageValidationError(
                f"Invalid NFS version. Must be one of: {[ver.value for ver in NFSVersion]}",
                validation_type="version"
            )

    @field_validator("MOUNT_PROTOCOL")
    def validate_mount_protocol(cls, v: str) -> str:
        """Validate mount protocol"""
        try:
            return NFSMountProtocol(v.lower())
        except ValueError:
            raise StorageValidationError(
                f"Invalid mount protocol. Must be one of: {[p.value for p in NFSMountProtocol]}",
                validation_type="mount_protocol"
            )

    @field_validator("SECURITY_TYPE")
    def validate_security_type(cls, v: str) -> str:
        """Validate security type"""
        try:
            return NFSSecurityType(v.lower())
        except ValueError:
            raise StorageValidationError(
                f"Invalid security type. Must be one of: {[t.value for t in NFSSecurityType]}",
                validation_type="security_type"
            )

    @field_validator("LOCAL_UID", "LOCAL_GID")
    def validate_id(cls, v: Optional[int]) -> Optional[int]:
        """Validate UID/GID"""
        if v is not None:
            if not (0 <= v <= 65535):
                raise StorageValidationError(
                    "UID/GID must be between 0 and 65535",
                    validation_type="id_mapping"
                )
        return v

    @field_validator("KERBEROS_KEYTAB")
    def validate_keytab(cls, v: Optional[str]) -> Optional[str]:
        """Validate Kerberos keytab file"""
        if v is not None:
            try:
                path = UPath(v).resolve()
                if not path.exists():
                    raise StorageValidationError(
                        f"Keytab file not found: {v}",
                        validation_type="keytab"
                    )

                # Check file permissions (Unix-like systems)
                if os.name == 'posix':
                    mode = os.stat(path).st_mode
                    if mode & 0o077:  # Check if group or others have any access
                        raise StorageSecurityError(
                            "Keytab file has unsafe permissions",
                            security_check="keytab_permissions"
                        )

            except Exception as e:
                if isinstance(e, (StorageValidationError, StorageSecurityError)):
                    raise
                raise StorageValidationError(
                    f"Invalid keytab file: {str(e)}",
                    validation_type="keytab"
                )

        return v

    def _init_provider_specific(self, reinitialise: bool) -> None:
        """Initialize provider-specific settings"""
        # Validate Kerberos configuration
        if self.USE_KERBEROS:
            if self.SECURITY_TYPE not in {NFSSecurityType.KRB5, NFSSecurityType.KRB5I, NFSSecurityType.KRB5P}:
                raise StorageConfigError(
                    "Kerberos security type required when Kerberos is enabled",
                    provider=self.PROVIDER_TYPE
                )

            if not (self.KERBEROS_KDC and self.KERBEROS_REALM):
                raise StorageConfigError(
                    "KDC and realm required for Kerberos authentication",
                    provider=self.PROVIDER_TYPE
                )

            if not (self.KERBEROS_PRINCIPAL or self.KERBEROS_KEYTAB):
                raise StorageConfigError(
                    "Either principal or keytab required for Kerberos authentication",
                    provider=self.PROVIDER_TYPE
                )

        # Validate version-specific settings
        if self.VERSION == NFSVersion.NFSv3:
            if self.SECURITY_TYPE not in {NFSSecurityType.SYS, NFSSecurityType.KRB5}:
                raise StorageConfigError(
                    "NFSv3 only supports sys and krb5 security types",
                    provider=self.PROVIDER_TYPE
                )

        # Validate mount point if provided
        if self.MOUNT_POINT:
            try:
                path = UPath(self.MOUNT_POINT)
                if path.exists() and not path.is_dir():
                    raise StorageConfigError(
                        "Mount point exists but is not a directory",
                        provider=self.PROVIDER_TYPE
                    )
            except Exception as e:
                raise StorageConfigError(
                    f"Invalid mount point: {str(e)}",
                    provider=self.PROVIDER_TYPE
                )

    def get_connection_url(self) -> str:
        """Generate NFS connection URL"""
        return f"nfs://{self.SERVER}{self.EXPORT_PATH}"

    def get_connection_args(self) -> Dict[str, Any]:
        """Get connection arguments as dictionary"""
        args = super().get_connection_args()

        # Add NFS-specific arguments
        args.update({
            "server": self.SERVER,
            "export_path": self.EXPORT_PATH,
            "version": self.VERSION,
            "proto": self.MOUNT_PROTOCOL,
            "sec": self.SECURITY_TYPE
        })

        # Add mount options
        mount_opts = []

        if self.READ_ONLY:
            mount_opts.append("ro")
        else:
            mount_opts.append("rw")

        if self.NO_LOCK:
            mount_opts.append("nolock")

        if not self.HARD_MOUNT:
            mount_opts.append("soft")

        mount_opts.extend([
            f"retrans={self.RETRANS}",
            f"retry={self.RETRY_COUNT}",
            f"timeo={self.TIMEOUT}",
            f"acregmin={self.ACREGMIN}",
            f"acregmax={self.ACREGMAX}",
            f"acdirmin={self.ACDIRMIN}",
            f"acdirmax={self.ACDIRMAX}"
        ])

        # Add security options
        if self.USE_KERBEROS:
            args.update({
                "kdc_host": self.KERBEROS_KDC,
                "realm": self.KERBEROS_REALM,
                "principal": self.KERBEROS_PRINCIPAL,
                "keytab": self.KERBEROS_KEYTAB
            })

        # Add ID mapping
        if self.LOCAL_UID is not None:
            args["local_uid"] = self.LOCAL_UID

        if self.LOCAL_GID is not None:
            args["local_gid"] = self.LOCAL_GID

        if self.UID_MAPPING:
            args["uid_mapping"] = self.UID_MAPPING

        if self.GID_MAPPING:
            args["gid_mapping"] = self.GID_MAPPING

        # # Add performance settings
        # mount_opts.extend([
        #     f"rsize={self.RW_SIZE}",
        #     f"wsize={self.RW_SIZE}",
        #     f"readahead={self.READ_AHEAD}"
        # ])

        # if self.WRITE_BACK_CACHE:
        #     mount_opts.append("wback")

        # if self.ASYNC:
        #     mount_opts.append("async")
        # else:
        #     mount_opts.append("sync")

        # # Add security mount options
        # if self.NO_DEV:
        #     mount_opts.append("nodev")

        # if self.NO_SUID:
        #     mount_opts.append("nosuid")

        # if self.NO_EXEC:
        #     mount_opts.append("noexec")

        # args["mount_options"] = ",".join(mount_opts)

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
    #         required_perms = {"read", "write", "execute", "root_squash", "no_squash"}

    #     # Validate against required permissions
    #     if not required_perms.issubset(self.REQUIRED_PERMISSIONS):
    #         raise StorageValidationError(
    #             f"Missing required permissions for access type {self.ACCESS_TYPE}",
    #             validation_type="permissions"
    #         )
