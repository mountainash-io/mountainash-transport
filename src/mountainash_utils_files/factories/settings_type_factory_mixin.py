"""
Settings Type Detection Mixin for Storage Factory Pattern.

Detects storage provider type from SettingsParameters.settings_class,
similar to DataFrame type detection in mountainash-dataframes.
"""

import logging
import re
from typing import Optional, Type

from mountainash_settings import SettingsParameters, MountainAshBaseSettings

from ..constants import CONST_STORAGE_PROVIDER_TYPE

logger = logging.getLogger(__name__)


class SettingsTypeFactoryMixin:
    """
    Mixin for detecting storage provider type from settings class.

    Uses three-tier detection system:
        1. Exact Match (fast path): Direct mapping of known settings classes
        2. Pattern Matching (flexible): Regex-based class name matching
        3. Logging: Track unmapped types for future registration
    """

    # Layer 1: Exact Match - Direct settings class mapping (O(1) lookup)
    TYPE_MAP = {
        # Map settings class → provider type
        # These will be populated when settings classes are imported
    }

    # Layer 2: Pattern Matching - Class name patterns for flexible detection
    PATTERN_MAP = {
        # Regex pattern → provider type
        r"Local.*Settings": CONST_STORAGE_PROVIDER_TYPE.LOCAL,
        r"S3.*Settings": CONST_STORAGE_PROVIDER_TYPE.S3,
        r"S3Express.*Settings": CONST_STORAGE_PROVIDER_TYPE.S3EXPRESS,
        r"R2.*Settings": CONST_STORAGE_PROVIDER_TYPE.R2,
        r"GCS.*Settings": CONST_STORAGE_PROVIDER_TYPE.GCS,
        r"Azure.*Blob.*Settings": CONST_STORAGE_PROVIDER_TYPE.AZURE_BLOB,
        r"Azure.*Files.*Settings": CONST_STORAGE_PROVIDER_TYPE.AZURE_FILES,
        r"SFTP.*Settings": CONST_STORAGE_PROVIDER_TYPE.SFTP,
        r"FTP.*Settings": CONST_STORAGE_PROVIDER_TYPE.FTP,
        r"SSH.*Settings": CONST_STORAGE_PROVIDER_TYPE.SSH,
        r"MinIO.*Settings": CONST_STORAGE_PROVIDER_TYPE.MINIO,
        r"SMB.*Settings": CONST_STORAGE_PROVIDER_TYPE.SMB,
        r"NFS.*Settings": CONST_STORAGE_PROVIDER_TYPE.NFS,
        r"B2.*Settings": CONST_STORAGE_PROVIDER_TYPE.B2,
        r"GitHub.*Settings": CONST_STORAGE_PROVIDER_TYPE.GITHUB,
    }

    @classmethod
    def _get_strategy_key(
        cls, settings_parameters: SettingsParameters, **kwargs
    ) -> Optional[CONST_STORAGE_PROVIDER_TYPE]:
        """
        Detect storage provider type from SettingsParameters.

        Args:
            settings_parameters: SettingsParameters with settings_class
            **kwargs: Additional context (unused)

        Returns:
            Provider type enum or None if detection fails
        """
        if settings_parameters is None:
            logger.warning("SettingsParameters is None, cannot detect provider")
            return None

        settings_class = settings_parameters.settings_class

        if settings_class is None:
            logger.warning("settings_class is None in SettingsParameters")
            return None

        # Layer 1: Exact Match (Fast Path)
        provider_type = cls._detect_from_exact_match(settings_class)
        if provider_type:
            return provider_type

        # Layer 2: Pattern Matching (Flexible Fallback)
        provider_type = cls._detect_from_pattern_match(settings_class)
        if provider_type:
            # Auto-register for future fast-path lookup
            cls._register_settings_class(settings_class, provider_type)
            return provider_type

        # Layer 3: Logging (Detection Failed)
        cls._log_unmapped_settings_class(settings_class)
        return None

    @classmethod
    def _detect_from_exact_match(
        cls, settings_class: Type[MountainAshBaseSettings]
    ) -> Optional[CONST_STORAGE_PROVIDER_TYPE]:
        """
        Fast path: Direct lookup in TYPE_MAP.

        Args:
            settings_class: Settings class to detect

        Returns:
            Provider type or None
        """
        return cls.TYPE_MAP.get(settings_class)

    @classmethod
    def _detect_from_pattern_match(
        cls, settings_class: Type[MountainAshBaseSettings]
    ) -> Optional[CONST_STORAGE_PROVIDER_TYPE]:
        """
        Flexible fallback: Regex pattern matching on class name.

        Args:
            settings_class: Settings class to detect

        Returns:
            Provider type or None
        """
        class_name = settings_class.__name__

        for pattern, provider_type in cls.PATTERN_MAP.items():
            if re.match(pattern, class_name):
                logger.debug(
                    f"Pattern matched: {class_name} → {provider_type} (pattern: {pattern})"
                )
                return provider_type

        return None

    @classmethod
    def _register_settings_class(
        cls,
        settings_class: Type[MountainAshBaseSettings],
        provider_type: CONST_STORAGE_PROVIDER_TYPE,
    ) -> None:
        """
        Register settings class in TYPE_MAP for future fast-path lookup.

        Args:
            settings_class: Settings class to register
            provider_type: Detected provider type
        """
        cls.TYPE_MAP[settings_class] = provider_type
        logger.debug(
            f"Auto-registered {settings_class.__name__} → {provider_type} for fast lookup"
        )

    @classmethod
    def _log_unmapped_settings_class(
        cls, settings_class: Type[MountainAshBaseSettings]
    ) -> None:
        """
        Log unmapped settings class for debugging.

        Args:
            settings_class: Unmapped settings class
        """
        class_name = settings_class.__name__
        module_name = settings_class.__module__

        logger.warning(
            f"Unmapped settings class: {class_name} (module: {module_name}). "
            f"Consider adding to TYPE_MAP or PATTERN_MAP."
        )

    @classmethod
    def register_settings_class_mapping(
        cls,
        settings_class: Type[MountainAshBaseSettings],
        provider_type: CONST_STORAGE_PROVIDER_TYPE,
    ) -> None:
        """
        Manually register a settings class mapping.

        Useful for custom settings classes or explicit registration.

        Args:
            settings_class: Settings class to register
            provider_type: Provider type to map to
        """
        cls.TYPE_MAP[settings_class] = provider_type
        logger.info(f"Manually registered {settings_class.__name__} → {provider_type}")
