#path: mountainash_settings/settings/auth/storage/base.py

from typing import Optional, Dict, Any, List, Set, Tuple
from pydantic import Field, SecretStr, field_validator
from upath import UPath

from mountainash_settings import MountainAshBaseSettings, SettingsParameters
from ..constants import (
    CONST_STORAGE_PROVIDER_TYPE,
    CONST_STORAGE_AUTH_METHOD,
    CONST_STORAGE_ACCESS_TYPE
)
from .exceptions import (
    StorageConfigError,
    StorageValidationError
)

class StorageAuthBase(MountainAshBaseSettings):
    """Base class for storage authentication settings"""

    # Provider Configuration
    PROVIDER_TYPE:  str = Field(...)
    AUTH_METHOD:    str = Field(default=CONST_STORAGE_AUTH_METHOD.KEY)

    # Connection Settings
    ENDPOINT:       Optional[str] = Field(default=None)
    PORT:           Optional[int] = Field(default=None)
    TIMEOUT:        float = Field(default=30.0)

    # Path Settings
    ROOT_PATH:      Optional[str] = Field(default=None)
    CREATE_PATH:    bool = Field(default=False)


    # Authentication
    USERNAME:       Optional[str] = Field(default=None)
    PASSWORD:       Optional[SecretStr] = Field(default=None)
    ACCESS_KEY_ID:  Optional[str] = Field(default=None)
    SECRET_KEY:     Optional[SecretStr] = Field(default=None)
    TOKEN:          Optional[SecretStr] = Field(default=None)


    #File Management
    COMPRESSION_TYPE: Optional[str] = Field(default=None)
    ENCRYPTION_TYPE: Optional[int] = Field(default=None)


    # # Security
    # ENCRYPTION_ENABLED: bool = Field(default=False)
    # ENCRYPTION_TYPE: str = Field(default=CONST_STORAGE_ENCRYPTION_TYPE.AES256)
    # ENCRYPTION_KEY: Optional[SecretStr] = Field(default=None)
    # ENCRYPTION_KEY_FILE: Optional[str] = Field(default=None)

    # # Connection Pool
    # POOL_SIZE: int = Field(default=5)
    # POOL_TIMEOUT: float = Field(default=30.0)
    # MAX_OVERFLOW: int = Field(default=10)

    # # Access Control
    REQUIRED_PERMISSIONS: Set[str] = Field(default_factory=lambda: {"read", "write"})
    ACCESS_TYPE: str = Field(default=CONST_STORAGE_ACCESS_TYPE.READ_WRITE)

    # # Integration
    # SECRETS_NAMESPACE: Optional[str] = Field(default=None)
    # USE_SSL: bool = Field(default=False)
    # VERIFY_SSL: bool = Field(default=False)
    # CA_CERT: Optional[str] = Field(default=None)



    def __init__(self,
                 config_files: Optional[str|UPath|List[str|UPath]|Tuple[str|UPath]] = None,
                 settings_parameters: Optional[SettingsParameters] = None,
                #  _dummy: Optional[bool] = False,
                 **kwargs) -> None:

        super().__init__(config_files=config_files,
                         settings_parameters = settings_parameters,
                        #  _dummy=_dummy,
                         **kwargs)


    @field_validator("PROVIDER_TYPE")
    def validate_provider_type(cls, v: str) -> str:
        """Validate provider type"""
        if CONST_STORAGE_PROVIDER_TYPE.find_member(v) is None:
            raise StorageValidationError(
                f"Invalid provider type: {v}",
                validation_type="provider_type"
            )
        return v

    @field_validator("AUTH_METHOD")
    def validate_auth_method(cls, v: str) -> str:
        """Validate authentication method"""
        if CONST_STORAGE_AUTH_METHOD.find_member(v) is None:
            raise StorageValidationError(
                f"Invalid authentication method: {v}",
                validation_type="auth_method"
            )
        return v

    @field_validator("ACCESS_TYPE")
    def validate_access_type(cls, v: str) -> str:
        """Validate access type"""
        if CONST_STORAGE_ACCESS_TYPE.find_member(v) is None:
            raise StorageValidationError(
                f"Invalid access type: {v}",
                validation_type="access_type"
            )
        return v

    @field_validator("PORT")
    def validate_port(cls, v: Optional[int]) -> Optional[int]:
        """Validate port number"""
        if v is not None and not (1 <= v <= 65535):
            raise StorageValidationError(
                f"Invalid port number: {v}",
                validation_type="port"
            )
        return v

    def post_init(
        self,
        template_settings_parameters: Optional[SettingsParameters] = None,
        reinitialise: Optional[bool] = False,
    ) -> None:
        """Post-initialization validation and setup.

        Signature matches ``MountainAshBaseSettings.post_init`` and
        ``Profile.post_init`` so subclasses adopting the
        spec-driven pattern (``StorageProfile``) inherit cleanly
        without a signature-bridging override.
        """
        super().post_init(
            template_settings_parameters=template_settings_parameters,
            reinitialise=reinitialise,
        )
        self._init_provider_specific(bool(reinitialise))

    # def _validate_security_config(self) -> None:
    #     """Validate security configuration"""
    #     if self.ENCRYPTION_ENABLED:
    #         if not (self.ENCRYPTION_KEY or self.ENCRYPTION_KEY_FILE):
    #             raise StorageSecurityError(
    #                 "Encryption enabled but no encryption key provided",
    #                 security_check="encryption_config"
    #             )

    #         if self.ENCRYPTION_KEY_FILE and not os.path.exists(self.ENCRYPTION_KEY_FILE):
    #             raise StorageSecurityError(
    #                 f"Encryption key file not found: {self.ENCRYPTION_KEY_FILE}",
    #                 security_check="encryption_key_file"
    #             )

    #     if self.USE_SSL and self.VERIFY_SSL and not self.CA_CERT:
    #         raise StorageSecurityError(
    #             "SSL verification enabled but no CA certificate provided",
    #             security_check="ssl_config"
    #         )

    def _init_provider_specific(self, reinitialise: bool) -> None:
        """Hook for legacy (pre-descriptor) provider classes to run setup.

        No-op by default. Legacy provider classes (the 10 not yet migrated to
        ``StorageProfile``) override this. Descriptor-driven providers do all
        setup in their ``__adapter__``.
        """
        return None

    def get_connection_url(self) -> str:
        """Generate a connection URL for inspection/logging.

        Legacy provider classes override this. Descriptor-driven providers
        typically return a template-resolved URL; callers should prefer the
        adapter output for actual SDK kwargs.
        """
        return ""

    def get_connection_args(self) -> Dict[str, Any]:
        """Get connection arguments as dictionary"""
        args = {
            "endpoint": self.ENDPOINT,
            "port": self.PORT,
            "timeout": self.TIMEOUT,
            "username": self.USERNAME,
            "password": self.PASSWORD if self.PASSWORD else None,
            "access_key": self.ACCESS_KEY_ID,
            "secret_key": self.SECRET_KEY if self.SECRET_KEY else None,
            "token": self.TOKEN if self.TOKEN else None
        }

        # # Add SSL configuration if enabled
        # if self.USE_SSL:
        #     args.update({
        #         "use_ssl": True,
        #         "verify_ssl": self.VERIFY_SSL,
        #         "ca_cert": self.CA_CERT
        #     })

        # # Add encryption configuration if enabled
        # if self.ENCRYPTION_ENABLED:
        #     args["encryption"] = {
        #         "type": self.ENCRYPTION_TYPE,
        #         "key": (
        #             self.ENCRYPTION_KEY if self.ENCRYPTION_KEY
        #             else self._load_encryption_key()
        #         )
        #     }

        return {k: v for k, v in args.items() if v is not None}

    # def get_pool_config(self) -> Dict[str, Any]:
    #     """Get connection pool configuration"""
    #     return {
    #         "pool_size": self.POOL_SIZE,
    #         "pool_timeout": self.POOL_TIMEOUT,
    #         "max_overflow": self.MAX_OVERFLOW
    #     }

    # def _load_encryption_key(self) -> str:
    #     """Load encryption key from file"""
    #     try:
    #         if not self.ENCRYPTION_KEY_FILE:
    #             raise StorageSecurityError(
    #                 "No encryption key file specified",
    #                 security_check="encryption_key_load"
    #             )

    #         with open(self.ENCRYPTION_KEY_FILE, 'rb') as f:
    #             return f.read().strip().decode('utf-8')

    #     except Exception as e:
    #         raise StorageSecurityError(
    #             f"Failed to load encryption key: {str(e)}",
    #             security_check="encryption_key_load"
    #         )

    # def validate_connection(self) -> bool:
    #     """Validate connection parameters"""
    #     try:
    #         if not self._connection_tested:
    #             self._connection_valid = self._test_connection()
    #             self._connection_tested = True
    #         return self._connection_valid
    #     except Exception as e:
    #         raise StorageConnectionError(
    #             f"Connection validation failed: {str(e)}",
    #             provider=self.PROVIDER_TYPE
    #         )

    # def validate_permissions(self) -> bool:
    #     """Validate storage permissions"""
    #     try:
    #         if not self._permissions_validated:
    #             self._validate_permissions()
    #             self._permissions_validated = True
    #         return True
    #     except Exception as e:
    #         raise StorageValidationError(
    #             f"Permission validation failed: {str(e)}",
    #             validation_type="permissions"
    #         )

    # @abstractmethod
    # def _test_connection(self) -> bool:
    #     """Test storage connection"""
    #     pass

    # @abstractmethod
    # def _validate_permissions(self) -> None:
    #     """Validate storage permissions"""
    #     pass

    def format_connection_url(self, template: str) -> str:
        """Format connection URL using template"""
        try:
            # Get connection parameters
            params = self.get_connection_args()

            # Format the template
            return template.format(**params)
        except KeyError as e:
            raise StorageConfigError(
                f"Missing required parameter in connection template: {str(e)}",
                provider=self.PROVIDER_TYPE
            )
        except Exception as e:
            raise StorageConfigError(
                f"Failed to format connection URL: {str(e)}",
                provider=self.PROVIDER_TYPE
            )
