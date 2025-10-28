from typing import Optional, List, Any, Dict, Tuple
from upath import UPath

from pydantic import Field, SecretStr, field_validator
import re
from enum import Enum

from mountainash_settings import SettingsParameters
from ...settings import StorageAuthBase

from ...constants import CONST_STORAGE_PROVIDER_TYPE,CONST_STORAGE_AUTH_METHOD

from ..exceptions import (
    StorageValidationError,
    StorageConfigError
)

class GitHubTokenType(str, Enum):
    """GitHub token types"""
    PERSONAL_ACCESS = "personal_access"
    OAUTH = "oauth"
    GITHUB_APP = "github_app"
    FINE_GRAINED = "fine_grained"
    INSTALLATION = "installation"

class GitHubStorageType(str, Enum):
    """GitHub storage types"""
    REPOSITORY = "repository"
    RELEASES = "releases"
    PACKAGES = "packages"
    ACTIONS = "actions"
    PAGES = "pages"

class GitHubVisibility(str, Enum):
    """GitHub repository/package visibility"""
    PUBLIC = "public"
    PRIVATE = "private"
    INTERNAL = "internal"

class GitHubPackageType(str, Enum):
    """GitHub package registry types"""
    CONTAINER = "container"
    NPM = "npm"
    MAVEN = "maven"
    NUGET = "nuget"
    RUBYGEMS = "rubygems"
    DOCKER = "docker"
    PYTHON = "python"

class GitHubStorageAuthSettings(StorageAuthBase):
    """
    GitHub storage authentication settings.

    Handles authentication configuration for GitHub storage (repositories, releases, packages).
    Does not perform actual authentication or connection.
    """

    PROVIDER_TYPE: str = Field(default=CONST_STORAGE_PROVIDER_TYPE.GITHUB)

    # Basic Settings
    STORAGE_TYPE: str = Field(..., description="Type of GitHub storage to use")
    OWNER: str = Field(..., description="Repository owner or organization")
    REPOSITORY: Optional[str] = Field(default=None, description="Repository name if using repo storage")

    # Authentication Settings
    AUTH_METHOD: str = Field(default=CONST_STORAGE_AUTH_METHOD.TOKEN)
    TOKEN_TYPE: str = Field(default=GitHubTokenType.PERSONAL_ACCESS)
    TOKEN: SecretStr = Field(..., description="Authentication token")

    # GitHub App Settings (for GitHub App auth)
    APP_ID: Optional[str] = Field(default=None)
    INSTALLATION_ID: Optional[str] = Field(default=None)
    PRIVATE_KEY: Optional[SecretStr] = Field(default=None)

    # API Settings
    API_VERSION: str = Field(default="2022-11-28")
    API_URL: str = Field(default="api.github.com")
    USE_GRAPHQL: bool = Field(default=False)

    # Package Settings
    PACKAGE_TYPE: Optional[str] = Field(default=None)
    PACKAGE_NAME: Optional[str] = Field(default=None)
    PACKAGE_VISIBILITY: Optional[str] = Field(default=GitHubVisibility.PUBLIC)

    # Repository Settings
    BRANCH: Optional[str] = Field(default="main")
    PATH: Optional[str] = Field(default=None)
    CREATE_PATH: bool = Field(default=False)

    # # Security Settings
    # VERIFY_SSL: bool = Field(default=True)
    # SSL_VERIFY: Union[bool, str] = Field(default=True)
    # TIMEOUT: int = Field(default=30)

    # # Rate Limiting Settings
    # RETRY_COUNT: int = Field(default=3)
    # RETRY_BACKOFF: float = Field(default=1.0)
    # RETRY_ON_RATE_LIMIT: bool = Field(default=True)

    # # Cache Settings
    # CACHE_TTL: int = Field(default=300)  # 5 minutes
    # ENABLE_ETAGS: bool = Field(default=True)

    def __init__(self,
                 config_files: Optional[str|UPath|List[str|UPath]|Tuple[str|UPath]] = None,
                 settings_parameters:   Optional[SettingsParameters] = None,
                #  _dummy: Optional[bool] = False,
                 **kwargs) -> None:


        super().__init__(config_files=config_files,
                         settings_parameters=settings_parameters,
                        #  _dummy=_dummy,
                         **kwargs)



    @field_validator("OWNER")
    def validate_owner(cls, v: str) -> str:
        """Validate GitHub owner/organization name"""
        if not v:
            raise StorageValidationError(
                "Owner is required",
                validation_type="owner"
            )

        if not re.match(r'^[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?$', v):
            raise StorageValidationError(
                "Invalid owner format. Must contain only letters, numbers, and single hyphens",
                validation_type="owner"
            )

        if len(v) > 39:
            raise StorageValidationError(
                "Owner name cannot exceed 39 characters",
                validation_type="owner"
            )

        return v

    @field_validator("REPOSITORY")
    def validate_repository(cls, v: Optional[str]) -> Optional[str]:
        """Validate GitHub repository name"""
        if v is not None:
            if not re.match(r'^[a-zA-Z0-9_.-]+$', v):
                raise StorageValidationError(
                    "Invalid repository name format",
                    validation_type="repository"
                )

            if len(v) > 100:
                raise StorageValidationError(
                    "Repository name cannot exceed 100 characters",
                    validation_type="repository"
                )

        return v

    @field_validator("STORAGE_TYPE")
    def validate_storage_type(cls, v: str) -> str:
        """Validate storage type"""
        try:
            return GitHubStorageType(v.lower())
        except ValueError:
            raise StorageValidationError(
                f"Invalid storage type. Must be one of: {[t.value for t in GitHubStorageType]}",
                validation_type="storage_type"
            )

    @field_validator("TOKEN_TYPE")
    def validate_token_type(cls, v: str) -> str:
        """Validate token type"""
        try:
            return GitHubTokenType(v.lower())
        except ValueError:
            raise StorageValidationError(
                f"Invalid token type. Must be one of: {[t.value for t in GitHubTokenType]}",
                validation_type="token_type"
            )

    @field_validator("PACKAGE_TYPE")
    def validate_package_type(cls, v: Optional[str]) -> Optional[str]:
        """Validate package type if specified"""
        if v is not None:
            try:
                return GitHubPackageType(v.lower())
            except ValueError:
                raise StorageValidationError(
                    f"Invalid package type. Must be one of: {[t.value for t in GitHubPackageType]}",
                    validation_type="package_type"
                )
        return v

    @field_validator("PACKAGE_VISIBILITY")
    def validate_package_visibility(cls, v: Optional[str]) -> Optional[str]:
        """Validate package visibility if specified"""
        if v is not None:
            try:
                return GitHubVisibility(v.lower())
            except ValueError:
                raise StorageValidationError(
                    f"Invalid visibility. Must be one of: {[t.value for t in GitHubVisibility]}",
                    validation_type="package_visibility"
                )
        return v

    def _init_provider_specific(self, reinitialise: bool) -> None:
        """Initialize provider-specific settings"""
        # Validate storage type specific requirements
        if self.STORAGE_TYPE == GitHubStorageType.REPOSITORY:
            if not self.REPOSITORY:
                raise StorageConfigError(
                    "Repository name required for repository storage",
                    provider=self.PROVIDER_TYPE
                )

        elif self.STORAGE_TYPE == GitHubStorageType.PACKAGES:
            if not (self.PACKAGE_TYPE and self.PACKAGE_NAME):
                raise StorageConfigError(
                    "Package type and name required for package storage",
                    provider=self.PROVIDER_TYPE
                )

        # Validate GitHub App authentication
        if self.TOKEN_TYPE == GitHubTokenType.GITHUB_APP:
            if not (self.APP_ID and self.INSTALLATION_ID and self.PRIVATE_KEY):
                raise StorageConfigError(
                    "APP_ID, INSTALLATION_ID, and PRIVATE_KEY required for GitHub App authentication",
                    provider=self.PROVIDER_TYPE
                )

        # Validate path settings
        if self.PATH and self.CREATE_PATH and self.STORAGE_TYPE != GitHubStorageType.REPOSITORY:
            raise StorageConfigError(
                "Path creation only supported for repository storage",
                provider=self.PROVIDER_TYPE
            )

    def get_connection_url(self) -> str:
        """Generate GitHub connection URL"""
        base_url = f"https://{self.API_URL}"

        if self.STORAGE_TYPE == GitHubStorageType.REPOSITORY:
            return f"{base_url}/repos/{self.OWNER}/{self.REPOSITORY}"
        elif self.STORAGE_TYPE == GitHubStorageType.PACKAGES:
            return f"{base_url}/users/{self.OWNER}/packages"
        elif self.STORAGE_TYPE == GitHubStorageType.RELEASES:
            return f"{base_url}/repos/{self.OWNER}/{self.REPOSITORY}/releases"

        return base_url

    def get_connection_args(self) -> Dict[str, Any]:
        """Get connection arguments as dictionary"""
        args = super().get_connection_args()

        # Add GitHub-specific arguments
        args.update({
            "owner": self.OWNER,
            "storage_type": self.STORAGE_TYPE,
            "api_version": self.API_VERSION,
            # "verify_ssl": self.VERIFY_SSL,
            # "ssl_verify": self.SSL_VERIFY,
            "timeout": self.TIMEOUT,
            "use_graphql": self.USE_GRAPHQL
        })

        # Add authentication
        args.update({
            "token_type": self.TOKEN_TYPE,
            "token": self.TOKEN
        })

        # Add GitHub App settings if applicable
        if self.TOKEN_TYPE == GitHubTokenType.GITHUB_APP:
            args.update({
                "app_id": self.APP_ID,
                "installation_id": self.INSTALLATION_ID,
                "private_key": self.PRIVATE_KEY
            })

        # Add storage-type specific settings
        if self.STORAGE_TYPE == GitHubStorageType.REPOSITORY:
            args.update({
                "repository": self.REPOSITORY,
                "branch": self.BRANCH,
                "path": self.PATH,
                "create_path": self.CREATE_PATH
            })
        elif self.STORAGE_TYPE == GitHubStorageType.PACKAGES:
            args.update({
                "package_type": self.PACKAGE_TYPE,
                "package_name": self.PACKAGE_NAME,
                "package_visibility": self.PACKAGE_VISIBILITY
            })

        # # Add rate limiting settings
        # args.update({
        #     "retry_count": self.RETRY_COUNT,
        #     "retry_backoff": self.RETRY_BACKOFF,
        #     "retry_on_rate_limit": self.RETRY_ON_RATE_LIMIT
        # })

        # # Add cache settings
        # if self.CACHE_TTL > 0:
        #     args.update({
        #         "cache_ttl": self.CACHE_TTL,
        #         "enable_etags": self.ENABLE_ETAGS
        #     })

        return {k: v for k, v in args.items() if v is not None}

    # def _validate_permissions(self) -> None:
    #     """Validate storage permissions configuration"""
    #     # Define required permissions based on storage and access type
    #     if self.STORAGE_TYPE == GitHubStorageType.REPOSITORY:
    #         if self.ACCESS_TYPE == CONST_STORAGE_ACCESS_TYPE.READ_ONLY:
    #             required_perms = {"contents:read"}
    #         elif self.ACCESS_TYPE == CONST_STORAGE_ACCESS_TYPE.WRITE_ONLY:
    #             required_perms = {"contents:write"}
    #         elif self.ACCESS_TYPE == CONST_STORAGE_ACCESS_TYPE.READ_WRITE:
    #             required_perms = {"contents:read", "contents:write"}
    #         else:  # ADMIN
    #             required_perms = {"contents:read", "contents:write", "repo:admin"}

    #     elif self.STORAGE_TYPE == GitHubStorageType.PACKAGES:
    #         if self.ACCESS_TYPE == CONST_STORAGE_ACCESS_TYPE.READ_ONLY:
    #             required_perms = {"packages:read"}
    #         elif self.ACCESS_TYPE == CONST_STORAGE_ACCESS_TYPE.WRITE_ONLY:
    #             required_perms = {"packages:write"}
    #         elif self.ACCESS_TYPE == CONST_STORAGE_ACCESS_TYPE.READ_WRITE:
    #             required_perms = {"packages:read", "packages:write"}
    #         else:  # ADMIN
    #             required_perms = {"packages:read", "packages:write", "packages:delete"}

    #     elif self.STORAGE_TYPE == GitHubStorageType.RELEASES:
    #         if self.ACCESS_TYPE == CONST_STORAGE_ACCESS_TYPE.READ_ONLY:
    #             required_perms = {"contents:read"}
    #         elif self.ACCESS_TYPE == CONST_STORAGE_ACCESS_TYPE.WRITE_ONLY:
    #             required_perms = {"contents:write"}
    #         elif self.ACCESS_TYPE == CONST_STORAGE_ACCESS_TYPE.READ_WRITE:
    #             required_perms = {"contents:read", "contents:write"}
    #         else:  # ADMIN
    #             required_perms = {"contents:read", "contents:write", "repo:admin"}

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

    #         # Validate timeout settings
    #         if not StorageValidator.validate_timeout_settings(
    #             connect_timeout=self.TIMEOUT,
    #             read_timeout=self.TIMEOUT
    #         ):
    #             return False

    #         # Validate retry settings
    #         if not StorageValidator.validate_retry_settings(
    #             max_retries=self.RETRY_COUNT,
    #             retry_delay=self.RETRY_BACKOFF,
    #             max_delay=self.RETRY_BACKOFF * (2 ** self.RETRY_COUNT)
    #         ):
    #             return False

    #         return True

    #     except Exception as e:
    #         if isinstance(e, StorageValidationError):
    #             raise
    #         return False
