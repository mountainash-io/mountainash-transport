from typing import Optional, List, Any, Dict, Tuple
from upath import UPath
from pydantic import Field

from mountainash_settings import SettingsParameters
from ...settings import StorageAuthBase

from ...constants import CONST_STORAGE_PROVIDER_TYPE


class LocalStorageAuthSettings(StorageAuthBase):
    """
    SFTP storage authentication settings.

    Handles authentication configuration for SFTP connections.
    Does not perform actual authentication or connection.
    """

    PROVIDER_TYPE: str = Field(default=CONST_STORAGE_PROVIDER_TYPE.LOCAL)


    def __init__(self,
                 config_files: Optional[str|UPath|List[str|UPath]|Tuple[str|UPath]] = None,
                 settings_parameters:   Optional[SettingsParameters] = None,
                 **kwargs) -> None:


        super().__init__(config_files=config_files,
                         settings_parameters=settings_parameters,
                        #  _dummy=_dummy,
                         **kwargs)


    def get_connection_url(self) -> str:
        """Generate SFTP connection URL"""
        return ""

    def get_connection_args(self) -> Dict[str, Any]:
        """Get connection arguments as dictionary"""

        return {}

    def _init_provider_specific(self, reinitialise: bool) -> None:
        """Initialize provider-specific settings"""
        # Validate storage type specific requirements
        pass
