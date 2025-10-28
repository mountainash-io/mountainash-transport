"""
Base Strategy Factory with dual-generic pattern for storage file helpers.

This module implements the factory pattern using lazy loading and runtime strategy selection,
adapted from mountainash-dataframes architecture for storage backend strategies.
"""

import importlib
import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import ClassVar, Dict, Generic, Optional, Type, TypeVar

# Type variables for dual-generic pattern
InputT = TypeVar("InputT")  # Input type (SettingsParameters)
StrategyT = TypeVar("StrategyT")  # Strategy type (file helper class)

logger = logging.getLogger(__name__)


class BaseStrategyFactory(ABC, Generic[InputT, StrategyT]):
    """
    Universal base factory with dual-generic design for storage strategies.

    Generic Type Parameters:
        InputT: Type constraint for input (e.g., SettingsParameters)
        StrategyT: Strategy class type returned by factory (e.g., Base_FileHelper)

    Key Features:
        - Lazy loading: Strategies imported only when first used
        - Runtime detection: Auto-detect storage backend from input
        - Strategy caching: Once loaded, strategies cached for reuse
        - Zero import cost: String-based configuration, no imports until needed
    """

    # Class-level caches for lazy loading
    _strategy_cache: ClassVar[Dict[Enum, Type[StrategyT]]] = {}
    _strategy_modules: ClassVar[Dict[Enum, str]] = {}
    _strategy_classes: ClassVar[Dict[Enum, str]] = {}

    def __init__(self):
        """Initialize factory and configure strategy mappings."""
        if not self._strategy_modules:
            self._configure_strategy_mapping()

    @classmethod
    @abstractmethod
    def _configure_strategy_mapping(cls) -> None:
        """
        Configure strategy mappings using ONLY strings (no imports).

        Subclasses MUST implement this to define:
            cls._strategy_modules: {provider_type: "module.path"}
            cls._strategy_classes: {provider_type: "ClassName"}

        Example:
            cls._strategy_modules = {
                CONST_STORAGE_PROVIDER_TYPE.S3: "mountainash_utils_files.file_helpers",
            }
            cls._strategy_classes = {
                CONST_STORAGE_PROVIDER_TYPE.S3: "S3_FileHelper",
            }
        """
        pass

    @classmethod
    @abstractmethod
    def _get_strategy_key(cls, input_data: InputT, **kwargs) -> Optional[Enum]:
        """
        Determine strategy key from input data.

        This is implemented by mixin classes (e.g., SettingsTypeFactoryMixin)
        to detect storage provider from SettingsParameters.

        Args:
            input_data: Input data to analyze (e.g., SettingsParameters)
            **kwargs: Additional context for detection

        Returns:
            Strategy key (enum) or None if detection fails
        """
        pass

    @classmethod
    def _lazy_load_strategy_class(cls, strategy_key: Enum) -> Type[StrategyT]:
        """
        Lazy load strategy class using runtime import.

        Args:
            strategy_key: Storage provider type enum

        Returns:
            Strategy class (not instance)

        Raises:
            KeyError: If strategy not configured
            ImportError: If module import fails
        """
        # Check cache first
        if strategy_key in cls._strategy_cache:
            return cls._strategy_cache[strategy_key]

        # Ensure mappings are configured
        if not cls._strategy_modules:
            cls._configure_strategy_mapping()

        # Get module and class name
        if strategy_key not in cls._strategy_modules:
            raise KeyError(
                f"No strategy configured for {strategy_key}. "
                f"Available: {list(cls._strategy_modules.keys())}"
            )

        module_path = cls._strategy_modules[strategy_key]
        class_name = cls._strategy_classes[strategy_key]

        # Runtime import
        try:
            module = importlib.import_module(module_path)
            strategy_class = getattr(module, class_name)

            # Cache for future use
            cls._strategy_cache[strategy_key] = strategy_class

            logger.debug(
                f"Loaded strategy {class_name} from {module_path} for {strategy_key}"
            )

            return strategy_class

        except ImportError as e:
            raise ImportError(
                f"Failed to import {class_name} from {module_path} for {strategy_key}: {e}"
            ) from e

    @classmethod
    def get_strategy(cls, input_data: InputT, **kwargs) -> StrategyT:
        """
        Get appropriate strategy instance for input data.

        This is the main entry point for factory usage.

        Args:
            input_data: Input to analyze (e.g., SettingsParameters)
            **kwargs: Additional arguments passed to strategy constructor

        Returns:
            Strategy instance ready to use

        Raises:
            ValueError: If storage provider cannot be detected
            ImportError: If strategy import fails
        """
        # Detect storage provider type
        strategy_key = cls._get_strategy_key(input_data, **kwargs)

        if strategy_key is None:
            raise ValueError(
                f"Could not determine strategy for input: {input_data}"
            )

        # Load strategy class
        strategy_class = cls._lazy_load_strategy_class(strategy_key)

        # Return class (file helpers are instantiated differently)
        return strategy_class  # type: ignore

    @classmethod
    def clear_cache(cls) -> None:
        """Clear strategy cache (mainly for testing)."""
        cls._strategy_cache.clear()
        logger.debug(f"Cleared strategy cache for {cls.__name__}")
